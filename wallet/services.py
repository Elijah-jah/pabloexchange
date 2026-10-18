from django.conf import settings
from django.db import transaction
from django.db.models import F

from .models import Wallet, WalletTransaction


def get_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def balance(user):
    """Instant read from the Wallet row (ledger remains the audit trail)."""
    return get_wallet(user).balance


def can_afford(user, amount):
    return balance(user) >= amount


@transaction.atomic
def credit(user, amount, description='', status='confirmed',
           method='', meta=None):
    wallet = Wallet.objects.select_for_update().get_or_create(user=user)[0]
    wallet.balance = F('balance') + amount
    wallet.save(update_fields=['balance'])
    return WalletTransaction.objects.create(
        user=user, type='credit', amount=amount, status=status,
        method=method, description=description, meta=meta or {},
    )


@transaction.atomic
def debit(user, amount, description='', method='', meta=None):
    wallet = Wallet.objects.select_for_update().get_or_create(user=user)[0]
    if wallet.balance < amount:
        raise ValueError(f'Insufficient funds: have {wallet.balance}, need {amount}')
    wallet.balance = F('balance') - amount
    wallet.save(update_fields=['balance'])
    return WalletTransaction.objects.create(
        user=user, type='debit', amount=amount, status='confirmed',
        method=method, description=description, meta=meta or {},
    )