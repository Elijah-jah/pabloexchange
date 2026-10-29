import logging
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone

from .models import Wallet, WalletTransaction


logger = logging.getLogger(__name__)


class InsufficientBalance(ValueError):
    """Raised when a wallet cannot cover a requested debit."""


def _decimal_amount(amount):
    """Convert an amount to a finite, positive Decimal."""
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Invalid wallet amount.') from exc

    if not value.is_finite() or value <= Decimal('0'):
        raise ValueError('Wallet amount must be greater than zero.')
    return value


def get_wallet(user):
    """Return the user's wallet, creating it on first use."""
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def _locked_wallet(user):
    """Return a row-locked wallet. Call inside transaction.atomic()."""
    wallet = get_wallet(user)
    return Wallet.objects.select_for_update().get(pk=wallet.pk)


def balance(user):
    """Return the current available wallet balance as a Decimal."""
    return get_wallet(user).balance


def can_afford(user, amount):
    """Return True when the wallet can cover the requested amount."""
    try:
        value = _decimal_amount(amount)
    except ValueError:
        return False
    return balance(user) >= value


def credit(user, amount, description='Wallet credit', meta=None, method='wallet'):
    """Atomically credit the wallet and create a confirmed ledger entry."""
    value = _decimal_amount(amount)

    with transaction.atomic():
        wallet = _locked_wallet(user)
        txn = WalletTransaction.objects.create(
            user=user,
            type='credit',
            amount=value,
            status='confirmed',
            method=method,
            description=description,
            meta=meta or {},
        )
        Wallet.objects.filter(pk=wallet.pk).update(
            balance=models.F('balance') + value,
            updated_at=timezone.now(),
        )

    return txn


def debit(user, amount, description='Wallet debit', meta=None, method='wallet'):
    """Atomically debit the wallet and create a confirmed ledger entry."""
    value = _decimal_amount(amount)

    with transaction.atomic():
        # Locking the wallet serializes purchases for this user. A second
        # request cannot spend the same balance after the first debit commits.
        wallet = _locked_wallet(user)
        if wallet.balance < value:
            raise InsufficientBalance('Insufficient wallet balance.')

        txn = WalletTransaction.objects.create(
            user=user,
            type='debit',
            amount=value,
            status='confirmed',
            method=method,
            description=description,
            meta=meta or {},
        )
        Wallet.objects.filter(pk=wallet.pk).update(
            balance=models.F('balance') - value,
            updated_at=timezone.now(),
        )

    return txn


class VirtualAccountError(Exception):
    """Raised when PocketFi cannot provide a permanent virtual account."""


def ensure_virtual_account(user):
    """Return the user's existing account or create one permanent account."""
    User = get_user_model()

    # Serialize account creation for this user. A repeated visit returns the
    # saved account instead of requesting another one from PocketFi.
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)

        existing_number = str(
            getattr(locked_user, 'pocketfi_account_number', '') or ''
        ).strip()
        if existing_number:
            return locked_user

        first_name = str(locked_user.first_name or '').strip()
        last_name = str(locked_user.last_name or '').strip()
        phone = str(getattr(locked_user, 'phone', '') or '').strip()
        email = str(locked_user.email or '').strip()

        if not (first_name and last_name and phone and email):
            raise VirtualAccountError(
                'First name, last name, phone number and email are required.'
            )
        if not phone.isdigit() or len(phone) != 11:
            raise VirtualAccountError(
                'A valid 11-digit phone number is required.'
            )
        if not settings.POCKETFI_BASE_URL:
            raise VirtualAccountError('PocketFi API URL is not configured yet.')
        if not settings.POCKETFI_SECRET_KEY:
            raise VirtualAccountError('PocketFi is not configured yet.')
        if not settings.POCKETFI_BUSINESS_ID:
            raise VirtualAccountError(
                'PocketFi business ID is not configured yet.'
            )

        # POCKETFI_BANK is optional and defaults to Kuda. PalmPay accounts
        # require additional KYC fields, so do not select PalmPay without
        # extending the payload to collect and validate those fields.
        bank = str(
            getattr(settings, 'POCKETFI_BANK', 'kuda') or 'kuda'
        ).strip().lower()
        payload = {
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'email': email,
            'businessId': str(settings.POCKETFI_BUSINESS_ID),
            'bank': bank,
        }

        try:
            response = requests.post(
                (
                    f"{settings.POCKETFI_BASE_URL.rstrip('/')}"
                    '/virtual-accounts/create'
                ),
                json=payload,
                headers={
                    'Authorization': (
                        f'Bearer {settings.POCKETFI_SECRET_KEY}'
                    ),
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                timeout=30,
            )
            result = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.exception(
                'PocketFi virtual-account request failed for user %s',
                locked_user.pk,
            )
            raise VirtualAccountError(
                'Could not reach PocketFi. Please try again.'
            ) from exc

        provider_status = (
            result.get('status') if isinstance(result, dict) else None
        )
        request_succeeded = (
            provider_status is True
            or str(provider_status or '').strip().lower()
            in {'success', 'successful'}
        )

        if (
            not response.ok
            or not isinstance(result, dict)
            or not request_succeeded
        ):
            message = (
                result.get('message', '')
                if isinstance(result, dict)
                else ''
            )
            # Never log the authorization header, secret key or user payload.
            logger.error(
                'PocketFi virtual-account creation rejected for user %s: '
                'HTTP %s, %s',
                locked_user.pk,
                response.status_code,
                message,
            )
            raise VirtualAccountError(
                message or 'PocketFi could not create the virtual account.'
            )

        banks = result.get('banks') or []
        if not banks and isinstance(result.get('data'), dict):
            banks = result['data'].get('banks') or []

        account = next(
            (
                item for item in banks
                if isinstance(item, dict)
                and (
                    item.get('accountNumber')
                    or item.get('account_number')
                )
            ),
            None,
        )
        if not account:
            logger.error(
                'PocketFi returned no account number for user %s',
                locked_user.pk,
            )
            raise VirtualAccountError(
                'PocketFi returned no account number.'
            )

        account_number = str(
            account.get('accountNumber')
            or account.get('account_number')
        ).strip()
        bank_name = str(
            account.get('bankName')
            or account.get('bank_name')
            or bank
        ).strip()
        account_name = str(
            account.get('accountName')
            or account.get('account_name')
            or f'{first_name} {last_name}'
        ).strip()

        locked_user.pocketfi_account_number = account_number
        locked_user.pocketfi_bank_name = bank_name
        update_fields = [
            'pocketfi_account_number',
            'pocketfi_bank_name',
        ]

        # The current user model needs only the two fields above. If an
        # optional pocketfi_account_name field exists, populate it as well.
        if hasattr(locked_user, 'pocketfi_account_name'):
            locked_user.pocketfi_account_name = account_name
            update_fields.append('pocketfi_account_name')

        locked_user.save(update_fields=update_fields)
        return locked_user