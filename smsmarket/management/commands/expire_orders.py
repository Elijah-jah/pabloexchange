from django.core.management.base import BaseCommand
from django.utils import timezone

from smsmarket.services import ORDER_TIMEOUT, expire_order
from smsmarket.models import NumberOrder


class Command(BaseCommand):
    help = 'Expire active number orders past their timeout.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - ORDER_TIMEOUT
        stale = NumberOrder.objects.filter(status='active', reserved_at__lt=cutoff)
        count = 0
        for order in stale:
            if expire_order(order):
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Expired {count} order(s).'))