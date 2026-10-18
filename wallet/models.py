import uuid

from django.conf import settings
from django.db import models


class Wallet(models.Model):
    """Per-user wallet. Balance updated transactionally alongside ledger rows."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user} — ₦{self.balance}'


class WalletTransaction(models.Model):
    STATUSES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name='wallet_transactions')
    type = models.CharField(max_length=10, choices=[('credit', 'Credit'), ('debit', 'Debit')])
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUSES, default='confirmed')
    method = models.CharField(max_length=20, blank=True)
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    description = models.CharField(max_length=255, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.type} ₦{self.amount} ({self.status})'