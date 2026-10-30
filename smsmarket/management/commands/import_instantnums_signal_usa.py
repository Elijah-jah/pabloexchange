from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from countries.models import Country
from pricing.models import Pricing
from smsmarket.models import Service
from smsmarket.providers import get_provider
from smsmarket.services import _extract_catalog, _extract_cost, _margin


class Command(BaseCommand):
    help = 'Import or update the InstantNums Signal price for USA only.'

    def handle(self, *args, **options):
        country = Country.objects.filter(is_active=True).filter(
            Q(code__iexact='US')
            | Q(code__iexact='USA')
            | Q(name__iexact='USA')
            | Q(name__icontains='United States')
        ).first()

        if country is None:
            raise CommandError(
                'No active USA country was found in the Country table.'
            )

        provider = get_provider('instantnums')

        self.stdout.write(
            f'Fetching InstantNums services for {country.name} '
            f'({country.code})...'
        )

        catalog = _extract_catalog(
            provider.get_services(country.code)
        )

        matches = [
            (code, name)
            for code, name in catalog
            if 'signal' in name.lower()
        ]

        exact_matches = [
            (code, name)
            for code, name in matches
            if name.strip().lower() == 'signal'
        ]

        if exact_matches:
            matches = exact_matches

        if len(matches) != 1:
            raise CommandError(
                'Expected exactly one Signal service for USA, '
                f'but found: {matches}'
            )

        service_code, service_name = matches[0]

        self.stdout.write(
            f'Fetching price for {service_name} '
            f'(service code: {service_code})...'
        )

        price_data = provider.get_price(
            service_code,
            country.code,
        )
        cost = _extract_cost(price_data)

        if cost is None or cost <= 0:
            raise CommandError(
                'InstantNums returned no valid Signal USA price: '
                f'{price_data}'
            )

        sell_price = (cost * _margin()).quantize(Decimal('0.01'))

        with transaction.atomic():
            service, _ = Service.objects.update_or_create(
                provider='instantnums',
                code=service_code,
                defaults={
                    'name': service_name or 'Signal',
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
                f'{action}: {service.name} | {country.name} | '
                f'Provider cost: {cost} | '
                f'Selling price: {sell_price}'
            )
        )
