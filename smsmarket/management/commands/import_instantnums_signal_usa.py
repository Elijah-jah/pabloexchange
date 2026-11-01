from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from countries.models import Country
from pricing.models import Pricing, PricingConfiguration
from smsmarket.models import Service
from smsmarket.providers import get_provider


class Command(BaseCommand):
    help = 'Import or update InstantNums Signal USA pricing only.'

    def handle(self, *args, **options):
        pricing_config = PricingConfiguration.objects.filter(pk=1).first()

        if pricing_config is None:
            raise CommandError(
                'Pricing configuration not found. Set your exchange rate '
                'and fixed profit in Django admin first.'
            )

        country = Country.objects.filter(
            code='US',
            is_active=True,
        ).first()

        if country is None:
            raise CommandError(
                'No active USA country with code US was found.'
            )

        service_code = '829'
        provider = get_provider('instantnums')

        self.stdout.write(
            'Fetching InstantNums Signal USA price '
            f'(service: {service_code})...'
        )

        price_data = provider.get_price(
            service_code,
            country.code,
        )

        if not price_data.get('success'):
            raise CommandError(
                f'InstantNums price request failed: {price_data}'
            )

        try:
            cost_usd = Decimal(str(price_data.get('price_usd')))
        except (InvalidOperation, TypeError):
            raise CommandError(
                f'Invalid or missing price_usd value: {price_data}'
            )

        if cost_usd <= 0:
            raise CommandError(
                f'InstantNums returned an invalid price: {cost_usd}'
            )

        # Use your existing PricingConfiguration conversion:
        # USD cost × exchange rate + fixed profit.
        sell_price = pricing_config.price_for(cost_usd)

        with transaction.atomic():
            service, _ = Service.objects.update_or_create(
                provider='instantnums',
                code=service_code,
                defaults={
                    'name': 'Signal',
                    'is_active': True,
                },
            )

            pricing, created = Pricing.objects.update_or_create(
                provider='instantnums',
                service=service,
                country=country,
                defaults={
                    'cost_usd': cost_usd,
                    'sell_price': sell_price,
                    'is_available': True,
                },
            )

        action = 'Created' if created else 'Updated'

        self.stdout.write(
            self.style.SUCCESS(
                f'{action}: Signal | United States | '
                f'Provider cost: ${cost_usd} | '
                f'Exchange rate: ₦{pricing_config.exchange_rate}/$ | '
                f'Fixed profit: ₦{pricing_config.fixed_profit} | '
                f'Selling price: ₦{sell_price}'
            )
        )
