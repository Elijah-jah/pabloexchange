"""DaisySMS provider — SERVER 1 (USA only).
API docs: https://daisysms.io/docs/api  (sms-activate compatible)
"""
import requests
from decouple import config

BASE_URL = config('DAISYSMS_BASE_URL', default='https://daisysms.io/stubs/handler_api.php')
API_KEY = config('DAISYSMS_API_KEY', default='')

# Friendly names for common Daisy shortcodes (fallback = uppercased code)
SERVICE_NAMES = {
    'wa': 'WhatsApp', 'tg': 'Telegram', 'ig': 'Instagram', 'fb': 'Facebook',
    'go': 'Google/Gmail', 'tw': 'Twitter / X', 'lf': 'TikTok', 'ds': 'Discord',
    'am': 'Amazon', 'nf': 'Netflix', 'pm': 'ProtonMail', 'nv': 'Naver',
    'ka': 'KakaoTalk', 'ok': 'OK.ru', 'vk': 'VK', 'vb': 'Viber', 'sn': 'Snapchat',
    'dr': 'DoorDash', 'ub': 'Uber', 'ly': 'Lyft', 'ai': 'Airbnb', 'np': 'PayPal',
    'ym': 'Yahoo', 'ms': 'Microsoft', 'bl': 'Blizzard', 'dc': 'Dating sites',
}


class DaisySmsProvider:
    name = 'daisysms'

    def _get(self, **params):
        params['api_key'] = API_KEY
        r = requests.get(BASE_URL, params=params, timeout=30)
        r.raise_for_status()
        return r

    # ---------------- Catalog ----------------
    def get_countries(self):
        # DaisySMS is USA-only
        return [{'ID': '187', 'name': 'United States', 'short_name': 'US'}]

    @staticmethod
    def _normalize_entry(info):
        """Handles both shapes: flat {'count','price'} or nested {'187': {...}}"""
        if isinstance(info, dict):
            if 'price' in info or 'cost' in info:
                try:
                    price = float(info.get('price', info.get('cost')) or 0)
                except (TypeError, ValueError):
                    price = 0.0
                try:
                    count = int(info.get('count', info.get('available')) or 0)
                except (TypeError, ValueError):
                    count = 0
                return {'price': price, 'count': count}
            for v in info.values():
                if isinstance(v, dict):
                    return DaisySmsProvider._normalize_entry(v)
        return {'price': 0.0, 'count': 0}

    def get_all_prices(self):
        """ONE API call: every service's USA price + stock."""
        data = self._get(action='getPricesVerification').json()
        return {code: self._normalize_entry(info) for code, info in data.items()}

    def get_services(self):
        return [{'ID': code, 'name': self.service_display_name(code)}
                for code in self.get_all_prices()]

    def service_display_name(self, code):
        return SERVICE_NAMES.get(code, code.upper())

    def get_price(self, service_code, country_code=None):
        data = self._get(action='getPricesVerification', service=service_code).json()
        info = data.get(service_code)
        if not info:
            raise Exception('No numbers are currently available')
        entry = self._normalize_entry(info)
        if entry['price'] <= 0:
            raise Exception('No numbers are currently available')
        return {'price_usd': entry['price'], 'available': entry['count']}

    # ---------------- Orders ----------------
    def purchase(self, service_code, country_code=None):
        r = self._get(action='getNumber', service=service_code, max_price=50)
        text = r.text.strip()
        if text.startswith('ACCESS_NUMBER:'):
            _, order_id, phone = text.split(':')
            return {'phone_number': phone, 'order_id': order_id}
        raise Exception(text)  # NO_NUMBERS / NO_MONEY / MAX_PRICE_EXCEEDED / TOO_MANY_ACTIVE_RENTALS

    def check_sms(self, order_id):
        text = self._get(action='getStatus', id=order_id, text=1).text.strip()
        if text.startswith('STATUS_OK'):
            parts = text.split(':', 2)
            return {'status': 'ok',
                    'sms': parts[1] if len(parts) > 1 else '',
                    'full_sms': parts[2] if len(parts) > 2 else ''}
        if text.startswith('STATUS_WAIT'):
            return {'status': 'waiting'}
        if text.startswith('STATUS_CANCEL'):
            return {'status': 'cancelled'}
        raise Exception(text)

    def cancel(self, order_id):
        text = self._get(action='setStatus', id=order_id, status=8).text.strip()
        return text in ('ACCESS_CANCEL', 'ACCESS_ACTIVATION')