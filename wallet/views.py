import hashlib
import hmac
import json
import logging
import uuid
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from marketplace.models import LogOrder
from smsmarket.models import NumberOrder

from .models import Wallet, WalletTransaction
from .payments.pocketfi import create_payment
from .services import balance, ensure_virtual_account


logger = logging.getLogger(__name__)


def _meta_dict(t):
    """Return transaction metadata as a dictionary."""
    meta = getattr(t, 'meta', None) or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def _account_number(user):
    return str(getattr(user, 'pocketfi_account_number', '') or '').strip()


def _has_account_details(user):
    return all([
        str(getattr(user, 'first_name', '') or '').strip(),
        str(getattr(user, 'last_name', '') or '').strip(),
        str(getattr(user, 'phone', '') or '').strip(),
    ])


def _fund_context(request, **extra):
    user = request.user
    account_number = _account_number(user)
    full_name = f'{user.first_name} {user.last_name}'.strip()

    context = {
        'min_amount': settings.MIN_FUND_AMOUNT,
        'max_amount': settings.MAX_FUND_AMOUNT,
        'needs_account_details': not bool(account_number),
        'account_number': account_number,
        'bank_name': getattr(user, 'pocketfi_bank_name', '') or '',
        'account_name': (
            getattr(user, 'pocketfi_account_name', '')
            or full_name
            or f'PabloExchange - {user.username}'
        ),
        'recent_fundings': WalletTransaction.objects.filter(
            user=user,
            type='credit',
        ).order_by('-created_at')[:5],
        'form_first_name': user.first_name,
        'form_last_name': user.last_name,
        'form_phone': getattr(user, 'phone', '') or '',
        'error': '',
    }
    context.update(extra)
    return context


def _locked_wallet(user):
    """Return a row-locked wallet. Call inside transaction.atomic()."""
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return Wallet.objects.select_for_update().get(pk=wallet.pk)


def _increase_wallet_balance(wallet, amount):
    Wallet.objects.filter(pk=wallet.pk).update(
        balance=models.F('balance') + amount,
        updated_at=timezone.now(),
    )


@login_required
def transactions(request):
    txns = list(
        WalletTransaction.objects.filter(user=request.user).order_by('-created_at')
    )

    # Collect order IDs referenced by transaction metadata.
    log_ids, num_ids = set(), set()
    for t in txns:
        meta = _meta_dict(t)
        oid = meta.get('order_id')
        if not oid:
            continue
        if meta.get('group_id'):
            log_ids.add(oid)
        elif meta.get('provider_order_id'):
            num_ids.add(oid)

    logs = {
        o.pk: o
        for o in LogOrder.objects.filter(pk__in=log_ids).select_related('group')
    }
    numbers = {
        o.pk: o
        for o in NumberOrder.objects.filter(pk__in=num_ids)
        .select_related('service', 'country')
    }

    for t in txns:
        t.related = None
        meta = _meta_dict(t)
        oid = meta.get('order_id')
        if not oid:
            continue
        if oid in logs and logs[oid].group:
            t.related = {
                'kind': 'log',
                'image_url': logs[oid].group.image.url if logs[oid].group.image else '',
                'title': logs[oid].group.name,
            }
        elif oid in numbers:
            order = numbers[oid]
            t.related = {
                'kind': 'number',
                'image_url': '',
                'title': order.service.name if order.service else 'Number',
                'extra': order.country.name if order.country else '',
            }

    return render(request, 'wallet/transactions.html', {'transactions': txns})


@login_required
def wallet_balance_json(request):
    return JsonResponse({'balance': str(balance(request.user))})


# ---------------- Virtual-account onboarding ----------------

@login_required
def add_account_details(request):
    """Collect the customer's details and assign a PocketFi virtual account."""
    user = request.user

    if _account_number(user):
        return redirect('wallet:fund')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        error = ''

        if not (first_name and last_name and phone):
            error = 'All fields are required.'
        elif not phone.isdigit() or len(phone) != 11:
            error = 'Enter a valid 11-digit phone number, for example 08012345678.'
        else:
            user.first_name = first_name
            user.last_name = last_name
            user.phone = phone
            user.save(update_fields=['first_name', 'last_name', 'phone'])

            try:
                ensure_virtual_account(user)
                user.refresh_from_db()
            except Exception:
                logger.exception('PocketFi virtual-account creation failed for user %s', user.pk)
                error = 'We could not create your account right now. Please try again shortly.'
            else:
                if _account_number(user):
                    return redirect('wallet:fund')
                error = 'PocketFi did not return an account number. Please try again.'

        return render(
            request,
            'wallet/fund.html',
            _fund_context(
                request,
                error=error,
                form_first_name=first_name,
                form_last_name=last_name,
                form_phone=phone,
            ),
        )

    # Existing profile details can be used without making the user retype them.
    if _has_account_details(user):
        return fund_wallet(request)

    return render(request, 'wallet/fund.html', _fund_context(request))


# ---------------- Fund wallet ----------------

@login_required
def fund_wallet(request):
    user = request.user

    if request.method == 'POST':
        # Account setup uses its own action, separate from legacy checkout.
        if request.POST.get('action') == 'create_account':
            return add_account_details(request)

        # Legacy hosted-checkout path. Bank-transfer funding does not use it.
        try:
            amount = Decimal(request.POST.get('amount', '0'))
        except (InvalidOperation, TypeError, ValueError):
            return HttpResponseBadRequest('Invalid amount')

        minimum = Decimal(str(settings.MIN_FUND_AMOUNT))
        maximum = Decimal(str(settings.MAX_FUND_AMOUNT))
        if not amount.is_finite() or not (minimum <= amount <= maximum):
            return HttpResponseBadRequest(
                f'Amount must be between {minimum} and {maximum}'
            )

        reference = str(uuid.uuid4())
        txn = WalletTransaction.objects.create(
            user=user,
            type='credit',
            amount=amount,
            status='pending',
            method='pocketfi',
            reference=reference,
            description='Wallet funding via PocketFi checkout',
            meta={'checkout_reference': reference},
        )

        try:
            # The existing payment helper accepts a numeric amount.
            result = create_payment(user, float(amount), reference)
        except Exception:
            logger.exception('PocketFi checkout initialization failed for user %s', user.pk)
            txn.status = 'failed'
            txn.save(update_fields=['status', 'updated_at'])
            return render(
                request,
                'wallet/fund.html',
                _fund_context(request, error='Could not initialize payment. Please try again.'),
            )

        payment_id = result.get('payment_id')
        if payment_id:
            txn.meta = {**_meta_dict(txn), 'payment_id': payment_id}
            txn.save(update_fields=['meta', 'updated_at'])

        if result.get('dev_mode'):
            return redirect('wallet:pocketfi_dev_confirm', reference=reference)

        checkout_url = result.get('checkout_url') or result.get('payment_link')
        if not checkout_url:
            txn.status = 'failed'
            txn.save(update_fields=['status', 'updated_at'])
            return render(
                request,
                'wallet/fund.html',
                _fund_context(request, error='PocketFi did not return a checkout link.'),
            )
        return redirect(checkout_url)

    # Match the sample behavior: users with saved details get an account on
    # their first funding-page visit. New users see the account setup form.
    error = ''
    if not _account_number(user) and _has_account_details(user):
        try:
            ensure_virtual_account(user)
            user.refresh_from_db()
        except Exception:
            logger.exception('PocketFi virtual-account creation failed for user %s', user.pk)
            error = 'We could not create your account right now. Please try again shortly.'

    return render(request, 'wallet/fund.html', _fund_context(request, error=error))


# ---------------- Hosted-checkout verification ----------------

def _confirm_checkout_transaction(txn, amount, extra_meta):
    """Atomically confirm a checkout and credit its wallet exactly once."""
    with transaction.atomic():
        locked_txn = WalletTransaction.objects.select_for_update().get(pk=txn.pk)
        if locked_txn.status == 'confirmed':
            return False
        if locked_txn.status != 'pending':
            return False

        wallet = _locked_wallet(locked_txn.user)
        _increase_wallet_balance(wallet, amount)

        locked_txn.status = 'confirmed'
        locked_txn.meta = {**_meta_dict(locked_txn), **extra_meta}
        locked_txn.save(update_fields=['status', 'meta', 'updated_at'])
        return True


@login_required
def verify_payment(request):
    """Verify PocketFi hosted checkout before crediting the user's wallet."""
    raw_reference = request.GET.get('reference', '').strip()
    if not raw_reference:
        return redirect('wallet:fund')

    # PocketFi may append a second '?payment_id=...' to the redirect.
    reference, _, appended_query = raw_reference.partition('?')
    appended = parse_qs(appended_query)
    redirect_payment_id = appended.get('payment_id', [''])[0]

    try:
        uuid.UUID(reference)
    except (ValueError, AttributeError):
        return redirect('wallet:fund')

    txn = WalletTransaction.objects.filter(
        reference=reference,
        user=request.user,
    ).first()
    if not txn:
        return redirect('wallet:fund')

    if txn.status == 'confirmed':
        return redirect('wallet:fund')

    meta = _meta_dict(txn)
    payment_id = meta.get('payment_id') or redirect_payment_id or request.GET.get('payment_id')
    if not payment_id:
        return render(
            request,
            'wallet/fund.html',
            _fund_context(request, error='Payment ID is missing. Please contact support.'),
        )

    try:
        response = requests.post(
            f"{settings.POCKETFI_BASE_URL}/checkout/confirm",
            json={'payment_id': payment_id},
            headers={
                'Authorization': f'Bearer {settings.POCKETFI_SECRET_KEY}',
                'Content-Type': 'application/json',
            },
            timeout=30,
        )
        result = response.json()
    except (requests.RequestException, ValueError):
        logger.exception('PocketFi checkout verification failed for transaction %s', txn.pk)
        return render(
            request,
            'wallet/fund.html',
            _fund_context(request, error='Could not verify payment yet. Please try again.'),
        )

    if result.get('status') != 'success':
        # A pending/provider-error response is not a failed payment. Keep the
        # transaction pending so a later callback refresh can verify it again.
        provider_status = str(
            result.get('payment_status')
            or result.get('transaction_status')
            or result.get('status')
            or ''
        ).strip().lower()
        if provider_status in {'failed', 'failure', 'cancelled', 'canceled', 'expired'}:
            txn.status = 'failed'
        txn.meta = {**meta, 'verification_response': result}
        txn.save(update_fields=['status', 'meta', 'updated_at'])
        return render(
            request,
            'wallet/fund.html',
            _fund_context(request, error='PocketFi has not confirmed this payment yet.'),
        )

    try:
        amount = Decimal(str(result['amount']))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return render(
            request,
            'wallet/fund.html',
            _fund_context(request, error='PocketFi returned an invalid payment amount.'),
        )

    # Never credit an amount different from the pending ledger row.
    if not amount.is_finite() or amount != txn.amount:
        txn.status = 'failed'
        txn.meta = {**meta, 'verification_response': result}
        txn.save(update_fields=['status', 'meta', 'updated_at'])
        return render(
            request,
            'wallet/fund.html',
            _fund_context(request, error='Payment amount mismatch. Please contact support.'),
        )

    _confirm_checkout_transaction(
        txn,
        amount,
        {'payment_id': payment_id, 'verification_response': result},
    )
    return redirect('wallet:fund')


# ---------------- PocketFi bank-transfer webhook ----------------

def _signature_valid(raw_body, signature):
    if not settings.POCKETFI_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        settings.POCKETFI_WEBHOOK_SECRET.encode('utf-8'),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature or '')


@csrf_exempt
@require_POST
def pocketfi_callback(request):
    """Credit the Wallet and ledger after a PocketFi bank transfer."""
    raw_body = request.body
    signature = request.headers.get('X-PocketFi-Signature', '')

    if not _signature_valid(raw_body, signature):
        return JsonResponse({'error': 'invalid signature'}, status=401)

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid json'}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({'error': 'invalid payload'}, status=400)

    order = payload.get('order') or {}
    provider_transaction = payload.get('transaction') or {}
    if not isinstance(order, dict) or not isinstance(provider_transaction, dict):
        return JsonResponse({'error': 'invalid payload'}, status=400)

    account_number = str(payload.get('account_number') or '').strip()
    amount_value = order.get('amount')
    provider_reference = str(provider_transaction.get('reference') or '').strip()

    if not (account_number and amount_value is not None and provider_reference):
        return JsonResponse({'error': 'incomplete payload'}, status=400)

    event_status = str(
        payload.get('status')
        or provider_transaction.get('status')
        or order.get('status')
        or ''
    ).strip().lower()
    successful_statuses = {'success', 'successful', 'completed', 'confirmed'}
    if event_status and event_status not in successful_statuses:
        return JsonResponse({'ok': True, 'note': 'transfer not successful'})

    try:
        amount = Decimal(str(amount_value))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({'error': 'invalid amount'}, status=400)

    if not amount.is_finite() or amount <= Decimal('0'):
        return JsonResponse({'error': 'invalid amount'}, status=400)

    User = get_user_model()
    user = User.objects.filter(pocketfi_account_number=account_number).first()
    if not user:
        # Acknowledge unknown accounts so PocketFi stops retrying them.
        return HttpResponse(status=200)

    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)

        # WalletTransaction.reference is a UUIDField, so the provider reference
        # is stored in meta instead of being forced into that UUID field.
        if WalletTransaction.objects.filter(
            meta__pocketfi_reference=provider_reference
        ).exists():
            return JsonResponse({'ok': True, 'note': 'already processed'})

        wallet = _locked_wallet(locked_user)
        WalletTransaction.objects.create(
            user=locked_user,
            type='credit',
            amount=amount,
            status='confirmed',
            method='pocketfi',
            description='Wallet funding via bank transfer',
            meta={
                'pocketfi_reference': provider_reference,
                'pocketfi_webhook': payload,
            },
        )
        _increase_wallet_balance(wallet, amount)

    return JsonResponse({'ok': True, 'status': 'success'})


# ---------------- Development-only checkout confirmation ----------------

@login_required
def dev_confirm(request, reference):
    if not settings.DEBUG or settings.POCKETFI_SECRET_KEY:
        return HttpResponseBadRequest(
            'Only available in DEBUG mode with no PocketFi keys set'
        )

    txn = get_object_or_404(
        WalletTransaction,
        reference=reference,
        user=request.user,
    )
    _confirm_checkout_transaction(txn, txn.amount, {'dev_confirmed': True})

    return HttpResponse(f'''
        <h2>Payment confirmed (development mode)</h2>
        <p>Reference: {txn.reference}</p>
        <p>Amount: {settings.CURRENCY_SYMBOL}{txn.amount}</p>
        <p>New balance: {settings.CURRENCY_SYMBOL}{balance(request.user)}</p>
        <p><a href="/wallet/fund/">Back to fund wallet</a></p>
    ''')