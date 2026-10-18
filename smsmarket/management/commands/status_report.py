import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from countries.models import Country
from pricing.models import Pricing, PricingConfiguration
from smsmarket.models import NumberOrder, Service, SmsMessage
from wallet.models import Wallet, WalletTransaction


class Command(BaseCommand):
    help = 'Full health report for PabloExchange — run this and paste the output.'

    def section(self, title):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'=== {title} ==='))

    def handle(self, *args, **options):
        U = get_user_model()

        self.section('COUNTS')
        self.stdout.write(f'Users:              {U.objects.count()}')
        self.stdout.write(f'Wallets:            {Wallet.objects.count()}  (users without: {U.objects.filter(wallet__isnull=True).count()})')
        self.stdout.write(f'Countries:          {Country.objects.count()}  (active: {Country.objects.filter(is_active=True).count()})')
        self.stdout.write(f'Services:           {Service.objects.count()}  (active: {Service.objects.filter(is_active=True).count()})')
        self.stdout.write(f'Pricings:           {Pricing.objects.count()}')
        self.stdout.write(f'  sellable (avail+price>0): {Pricing.objects.filter(is_available=True, sell_price__gt=0).count()}')
        self.stdout.write(f'  zero-cost/junk rows:      {Pricing.objects.filter(cost_usd=0).count()}')
        self.stdout.write(f'Number orders:      {NumberOrder.objects.count()}')
        for st, _ in NumberOrder.STATUSES:
            n = NumberOrder.objects.filter(status=st).count()
            if n:
                self.stdout.write(f'  {st}: {n}')
        self.stdout.write(f'SMS messages:       {SmsMessage.objects.count()}')
        self.stdout.write(f'Wallet txns:        {WalletTransaction.objects.count()}')

        self.section('PRICING COVERAGE (countries with sellable rows)')
        rows = (Pricing.objects.filter(is_available=True, sell_price__gt=0)
                .values_list('country__code', flat=True))
        from collections import Counter
        cov = Counter(rows)
        if cov:
            for code, n in sorted(cov.items(), key=lambda x: -x[1])[:15]:
                self.stdout.write(f'  {code}: {n} services priced')
        else:
            self.stdout.write(self.style.ERROR('  NONE — Buy Number page will be empty!'))

        self.section('PRICING CONFIGURATION')
        c = PricingConfiguration.objects.first()
        if c:
            self.stdout.write(f'  exchange_rate: {c.exchange_rate} | fixed_profit: {c.fixed_profit}')
        else:
            self.stdout.write(self.style.ERROR('  MISSING — create in /admin/pricing/'))

        self.section('PROVIDER CONNECTIVITY (live test)')
        key = settings.INSTANTNUMS_API_KEY
        self.stdout.write(f'API key set: {"yes (" + key[:10] + "...)" if key else "NO — check .env"}')
        self.stdout.write(f'Base URL: {settings.INSTANTNUMS_BASE_URL}')
        try:
            r = requests.get(
                f'{settings.INSTANTNUMS_BASE_URL}/v1/price',
                headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'},
                params={'service': 'whatsapp', 'country': 'US'},
                timeout=25,
            )
            data = r.json()
            if data.get('success'):
                self.stdout.write(self.style.SUCCESS(
                    f'  LIVE OK — whatsapp/US costs ${data.get("price_usd")}, stock {data.get("available")}'))
            else:
                self.stdout.write(self.style.ERROR(f'  API error: {data}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  UNREACHABLE: {type(e).__name__}: {e}'))

        self.section('WALLET SPOT-CHECK')
        u = U.objects.filter(email='test@pablo.com').first()
        if u:
            w = Wallet.objects.filter(user=u).first()
            self.stdout.write(f'  test@pablo.com balance: {w.balance if w else "NO WALLET"}')
        else:
            self.stdout.write('  test user not found')

        self.section('PENDING / STUCK ORDERS')
        stuck = NumberOrder.objects.filter(status='active')
        self.stdout.write(f'  active orders right now: {stuck.count()}')
        self.stdout.write('')

        self.stdout.write(self.style.MIGRATE_HEADING('=== END REPORT — paste everything above ==='))