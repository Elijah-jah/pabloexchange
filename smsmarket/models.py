from django.conf import settings
from django.db import models

from countries.models import Country


class Service(models.Model):
    """An SMS-receivable service, e.g. WhatsApp, Telegram, Google."""
    code = models.SlugField(unique=True)                    # 'whatsapp'
    name = models.CharField(max_length=100)                 # 'WhatsApp'
    icon = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)   # NGN sell price
    price_usd = models.DecimalField(max_digits=8, decimal_places=3, default=0)  # InstantNums cost
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class NumberOrder(models.Model):
    STATUSES = [
        ('reserved', 'Reserved'),        # number held, wallet not yet charged
        ('active', 'Active'),            # OTP expected
        ('completed', 'Completed'),      # OTP delivered, user charged
        ('expired', 'Expired'),          # timed out, auto-released (never charged)
        ('cancelled', 'Cancelled'),      # user cancelled, released (never charged)
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name='number_orders')
    service = models.ForeignKey(Service, on_delete=models.PROTECT,
                                related_name='orders')
    country = models.ForeignKey(Country, on_delete=models.PROTECT,
                                related_name='orders', null=True, blank=True)
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