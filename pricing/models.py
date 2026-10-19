from django.db import models

from countries.models import Country
from smsmarket.models import Service


class PricingConfiguration(models.Model):
    """Singleton — global pricing knobs (edit in admin).

    Sell price = provider USD cost × exchange_rate + fixed_profit
    """
    exchange_rate = models.DecimalField(max_digits=8, decimal_places=2, default=1650)
    fixed_profit = models.DecimalField(max_digits=8, decimal_places=2, default=800)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pricing configuration'
        verbose_name_plural = 'Pricing configuration'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def price_for(self, cost_usd):
        from decimal import Decimal
        return (Decimal(str(cost_usd)) * self.exchange_rate + self.fixed_profit).quantize(Decimal('0.01'))

    def __str__(self):
        return f'₦{self.exchange_rate}/$ + ₦{self.fixed_profit} profit'


class Pricing(models.Model):
    """Price per provider+service+country (synced from DaisySMS / InstantNums)."""
    PROVIDER_CHOICES = Service.PROVIDER_CHOICES

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES,
                                default='instantnums', db_index=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='pricings')
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='pricings')
    cost_usd = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_available = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('provider', 'service', 'country')
        ordering = ['service__name']

    def __str__(self):
        return f'{self.service} / {self.country} — ₦{self.sell_price}'