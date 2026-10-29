import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum

from .models import WalletTransaction


logger = logging.getLogger(__name__)


def balance(user):
    """Return the user's available balance from confirmed ledger entries."""
    zero = Decimal('0.00')
    confirmed = WalletTransaction.objects.filter(
        user=user,
        status='confirmed',
    )

    credits = confirmed.filter(type='credit').aggregate(
        total=Sum('amount')
    )['total'] or zero
    debits = confirmed.filter(type='debit').aggregate(
        total=Sum('amount')
    )['total'] or zero

    return credits - debits


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
