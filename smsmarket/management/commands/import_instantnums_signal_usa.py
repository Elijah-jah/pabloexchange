from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from countries.models import Country
from pricing.models import Pricing
from smsmarket.models import Service
from smsmarket.providers import get_provider
from smsmarket.services import _margin


class Command(BaseCommand):
    help = 'Import or update the InstantNums Signal price for USA only.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--usd-ngn-rate',
            type=Decimal,
            required=True,
            help='Exchange rate: how many NGN equal 1 USD.',
        )

    def handle(self, *args, **options):
        usd_ngn_rate = options['usd_ngn_rate']

        if usd_ngn_rate <= 0:
            raise CommandError('The USD-to-NGN rate must be greater than zero.')

        country = Country.objects.filter(
            code='US',
            is_active=True,
        ).first()

        if country is None:
            raise CommandError(
                'No active USA country with code US was found.'
            )

        # Confirmed by the previous successful InstantNums catalog request.
        service_code = '829'
        provider = get_provider('instantnums')

        self.stdout.write(
            f'Fetching InstantNums Signal USA price '
            f'(service: {service_code})...'
        )

        price_data = provider.get_price(
            service_code,
            country.code,
        )

        if not price_data.get('success'):
            raise CommandError(
                'InstantNums price request failed: '
                f'{price_data}'
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

        cost_ngn = cost_usd * usd_ngn_rate
        sell_price = (cost_ngn * _margin()).quantize(Decimal('0.01'))

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
                    'sell_price': sell_price,
                    'is_available': True,
                },
            )

        action = 'Created' if created else 'Updated'

        self.stdout.write(
            self.style.SUCCESS(
                f'{action}: Signal | United States | '
                f'Provider cost: ${cost_usd} | '
                f'Cost in NGN: ₦{cost_ngn.quantize(Decimal("0.01"))} | '
                f'Selling price: ₦{sell_price}'
            )
        )
