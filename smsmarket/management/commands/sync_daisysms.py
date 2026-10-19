from django.core.management.base import BaseCommand

from countries.models import Country
from pricing.models import Pricing, PricingConfiguration
from smsmarket.models import Service
from smsmarket.providers import get_provider


class Command(BaseCommand):
    help = "Sync DaisySMS (Server 1, USA) catalog + prices — ONE API call."

    def handle(self, *args, **options):
        p = get_provider('daisysms')

        config = PricingConfiguration.objects.first()
        if not config:
            self.stdout.write(self.style.ERROR('Create a PricingConfiguration row first (admin).'))
            return

        country, _ = Country.objects.get_or_create(
            code='US', defaults={'name': 'United States'})

        catalog = p.get_all_prices()   # single API call
        self.stdout.write(f'DaisySMS returned {len(catalog)} services')

        created = updated = unavailable = 0
        for code, info in catalog.items():
            service, _ = Service.objects.get_or_create(
                provider='daisysms', code=code,
                defaults={'name': p.service_display_name(code), 'is_active': True})

            cost = info['price']
            sell = config.price_for(cost)
            available = info['count'] > 0 and cost > 0

            pricing, was_created = Pricing.objects.get_or_create(
                provider='daisysms', service=service, country=country,
                defaults={'cost_usd': cost, 'sell_price': sell, 'is_available': available})
            if was_created:
                created += 1
            else:
                pricing.cost_usd = cost
                pricing.sell_price = sell
                pricing.is_available = available
                pricing.save(update_fields=['cost_usd', 'sell_price', 'is_available'])
                updated += 1
            if not available:
                unavailable += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done: {created} created, {updated} updated, {unavailable} out of stock'))