class BaseProvider:
    """Interface every SMS provider must implement."""

    name = None

    def get_balance(self):
        raise NotImplementedError

    def get_countries(self):
        raise NotImplementedError

    def get_services(self, country=None):
        raise NotImplementedError

    def get_price(self, service, country):
        raise NotImplementedError

    def check_stock(self, service, country):
        raise NotImplementedError

    def purchase(self, service, country):
        """Buy a number. Returns the raw API dict."""
        raise NotImplementedError

    def check_sms(self, order_id):
        """Returns {'status': 'waiting'} or {'status': 'finished', 'sms': code}."""
        raise NotImplementedError

    def cancel(self, order_id):
        raise NotImplementedError