import hashlib
import hmac
import json
import uuid
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import WalletTransaction
from .payments.pocketfi import create_payment
from .services import balance
from django.shortcuts import render
from marketplace.models import LogOrder
from smsmarket.models import NumberOrder


def _meta_dict(t):
    """meta may be a JSONField dict or a stored string — normalize to dict."""
    meta = getattr(t, 'meta', None) or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


@login_required
def transactions(request):
    txns = list(WalletTransaction.objects
                 .filter(user=request.user)
                 .order_by('-created_at'))

    # --- Collect order ids referenced in each transaction's meta ---
    log_ids, num_ids = set(), set()
    for t in txns:
        meta = _meta_dict(t)
        oid = meta.get('order_id')
        if not oid:
            continue
        if meta.get('group_id'):              # log purchase
            log_ids.add(oid)
        elif meta.get('provider_order_id'):   # number purchase
            num_ids.add(oid)

    # --- Two queries total, no N+1 ---
    logs = {
        o.pk: o for o in
        LogOrder.objects.filter(pk__in=log_ids).select_related('group')
    }
    numbers = {
        o.pk: o for o in
        NumberOrder.objects.filter(pk__in=num_ids)
        .select_related('service', 'country')
    }

    # --- Attach a small `related` payload each row can render ---
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
            o = numbers[oid]
            t.related = {
                'kind': 'number',
                'image_url': '',
                'title': o.service.name if o.service else 'Number',
                'extra': o.country.name if o.country else '',
            }

    return render(request, 'wallet/transactions.html', {
        'transactions': txns,
    })

# ---------------- Live balance (sidebar/topbar) ----------------

@login_required
def wallet_balance_json(request):
    return JsonResponse({'balance': str(balance(request.user))})


# ---------------- Fund wallet ----------------

@login_required
def fund_wallet(request):
    # POST path kept for the legacy checkout flow (harmless while unused).
    # With the assigned-account model, credits arrive via the PocketFi
    # transfer webhook instead — the page below is display-only.
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', '0'))
        except ValueError:
            return HttpResponseBadRequest('Invalid amount')

        if not (settings.MIN_FUND_AMOUNT <= amount <= settings.MAX_FUND_AMOUNT):
            return HttpResponseBadRequest(
                f'Amount must be between {settings.MIN_FUND_AMOUNT} and {settings.MAX_FUND_AMOUNT}'
            )

        reference = str(uuid.uuid4())
        WalletTransaction.objects.create(
            user=request.user,
            type='credit',
            amount=amount,
            status='pending',
            method='pocketfi',
            reference=reference,
            description='Wallet funding',
        )
        result = create_payment(request.user, amount, reference)
        if result.get('dev_mode'):
            return redirect('wallet:pocketfi_dev_confirm', reference=reference)
        return redirect(result['checkout_url'])

    # GET: assigned-account funding page
    return render(request, 'wallet/fund.html', {
        'min_amount': settings.MIN_FUND_AMOUNT,
        'max_amount': settings.MAX_FUND_AMOUNT,
        'account_number': request.user.pocketfi_account_number,
        'bank_name': request.user.pocketfi_bank_name,
        'account_name': f'PabloExchange - {request.user.username}',
        'recent_fundings': WalletTransaction.objects.filter(
            user=request.user, type='credit'
        )[:5],
    })


# ---------------- PocketFi webhook ----------------

def _signature_valid(raw_body, signature):
    if not settings.POCKETFI_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        settings.POCKETFI_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature or '')


@csrf_exempt
@require_POST
def pocketfi_callback(request):
    raw_body = request.body
    signature = request.headers.get('X-PocketFi-Signature', '')

    if not _signature_valid(raw_body, signature):
        return JsonResponse({'error': 'invalid signature'}, status=401)

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    reference = payload.get('reference')
    status = payload.get('status')  # 'success' or 'failed'

    try:
        txn = WalletTransaction.objects.get(reference=reference)
    except WalletTransaction.DoesNotExist:
        return JsonResponse({'error': 'unknown reference'}, status=404)

    with transaction.atomic():
        # Lock the row — two simultaneous webhooks can't both pass this check
        txn = WalletTransaction.objects.select_for_update().get(pk=txn.pk)
        if txn.status != 'pending':
            return JsonResponse({'ok': True, 'note': 'already processed'})  # idempotent

        if status == 'success':
            txn.status = 'confirmed'
        else:
            txn.status = 'failed'
        txn.meta = {**txn.meta, 'webhook': payload}
        txn.save(update_fields=['status', 'meta', 'updated_at'])

    return JsonResponse({'ok': True})


# ---------------- Dev-only: simulate PocketFi confirm ----------------

@login_required
def dev_confirm(request, reference):
    if settings.POCKETFI_SECRET_KEY:
        return HttpResponseBadRequest('Only available in dev mode (no PocketFi keys set)')

    txn = get_object_or_404(WalletTransaction, reference=reference, user=request.user)
    if txn.status == 'pending':
        txn.status = 'confirmed'
        txn.meta = {**txn.meta, 'dev_confirmed': True}
        txn.save(update_fields=['status', 'meta'])

    return HttpResponse(f'''
        <h2>Payment confirmed (dev mode)</h2>
        <p>Reference: {txn.reference}</p>
        <p>Amount: {settings.CURRENCY_SYMBOL}{txn.amount}</p>
        <p>New balance: {settings.CURRENCY_SYMBOL}{balance(request.user)}</p>
        <p><a href="/fund/">Back to fund wallet</a></p>
    ''')




