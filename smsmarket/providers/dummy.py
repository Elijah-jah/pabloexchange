import random
import string
import uuid
from datetime import timedelta

from django.utils import timezone


class DummyProvider:
    """Dev provider: fake number, OTP arrives ~10s after purchase."""

    name = 'dummy'
    delivery_delay = timedelta(seconds=10)

    def get_balance(self):
        return {'success': True, 'balance': 999.99}

    def get_countries(self):
        return {'success': True, 'countries': []}

    def get_services(self, country=None):
        return {'success': True, 'services': []}

    def get_price(self, service, country):
        return {'success': True, 'price': 0.5}

    def check_stock(self, service, country):
        return {'success': True, 'stock': 999}

    def purchase(self, service, country):
        return {
            'success': True,
            'order_id': f'dummy-{uuid.uuid4().hex[:12]}',
            'phone_number': '+2347' + ''.join(random.choices('0123456789', k=8)),
        }

    def check_sms(self, order_id):
        # OTP "arrives" 10s after the order row was created
        from ..models import NumberOrder
        try:
            order = NumberOrder.objects.get(provider_order_id=order_id)
        except NumberOrder.DoesNotExist:
            return {'status': 'waiting', 'sms': '', 'full_sms': ''}
        if timezone.now() < order.reserved_at + self.delivery_delay:
            return {'status': 'waiting', 'sms': '', 'full_sms': ''}
        return {
            'status': 'finished',
            'sms': ''.join(random.choices(string.digits, k=6)),
            'full_sms': f'Your code is {random.randint(100000, 999999)}',
        }

    def cancel(self, order_id):
        return {'success': True}