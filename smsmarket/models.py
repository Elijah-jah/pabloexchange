from django.conf import settings
from django.db import models

from countries.models import Country


class Service(models.Model):
    """An SMS-receivable service, e.g. WhatsApp, Telegram, Google.
    Same service can exist on both servers (Server 1 = DaisySMS USA,
    Server 2 = InstantNums all countries)."""
    PROVIDER_CHOICES = [
        ('daisysms', 'Server 1 — USA (DaisySMS)'),
        ('instantnums', 'Server 2 — All Countries (InstantNums)'),
    ]

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES,
                                default='instantnums', db_index=True)
    code = models.SlugField()                               # 'whatsapp' or Daisy 'wa'
    name = models.CharField(max_length=100)                 # 'WhatsApp'
    icon = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)   # legacy NGN field
    price_usd = models.DecimalField(max_digits=8, decimal_places=3, default=0)  # provider cost
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('provider', 'code')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_provider_display()})'


class NumberOrder(models.Model):
    STATUSES = [
        ('reserved', 'Reserved'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name='number_orders')
    service = models.ForeignKey(Service, on_delete=models.PROTECT,
                                related_name='orders')
    country = models.ForeignKey(Country, on_delete=models.PROTECT,
                                related_name='orders', null=True, blank=True)
    provider = models.CharField(max_length=20, default='instantnums', db_index=True)
    phone_number = models.CharField(max_length=20, blank=True)
    provider_order_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default='reserved')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    reserved_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.service} — {self.phone_number or "awaiting number"} ({self.status})'


class SmsMessage(models.Model):
    order = models.ForeignKey(NumberOrder, on_delete=models.CASCADE,
                              related_name='messages')
    sender = models.CharField(max_length=100, blank=True)
    text = models.TextField()
    otp_code = models.CharField(max_length=12, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['received_at']

    def __str__(self):
        return f'SMS to {self.order}: {self.otp_code or self.text[:30]}'