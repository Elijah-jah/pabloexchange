import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from countries.models import Country
from pricing.models import Pricing
from wallet.services import can_afford, debit

from .models import NumberOrder, Service, SmsMessage
from .providers import get_provider

logger = logging.getLogger(__name__)

ORDER_TIMEOUT = timedelta(minutes=15)
LIVE_CACHE_TTL = 600  # 10 minutes


class InsufficientFunds(Exception):
    pass


class PricingNotAvailable(Exception):
    pass


# ----------------------------------------------------------------------
# Pricing: DB Pricing rows win; otherwise price live from provider + margin
# ----------------------------------------------------------------------

def _margin():
    return Decimal(str(getattr(settings, 'SMS_MARGIN_MULTIPLIER', 1.4)))


def _extract_cost(data):
    """Pull a numeric cost out of the provider's price response."""
    if not isinstance(data, dict):
        return None
    sources = [data]
    inner = data.get('data')
    if isinstance(inner, dict):
        sources.append(inner)
    for d in sources:
        for key in ('price', 'cost', 'rate', 'amount'):
            if d.get(key) is not None:
                try:
                    return Decimal(str(d[key]))
                except InvalidOperation:
                    continue
    return None


def _extract_catalog(payload):
    """Provider catalogs come in several shapes — normalize to (code, name)."""
    if isinstance(payload, dict):
        for key in ('services', 'data', 'result'):
            if key in payload:
                return _extract_catalog(payload[key])
        items = []
        for code, val in payload.items():
            if isinstance(val, str):
                items.append((str(code), val))
            elif isinstance(val, dict):
                name = val.get('name') or val.get('title') or code
                items.append((str(val.get('code') or code), str(name)))
        return items
    items = []
    for s in payload or []:
        if isinstance(s, dict):
            code = s.get('code') or s.get('service') or s.get('id')
            name = s.get('name') or s.get('title') or code
            if code:
                items.append((str(code), str(name)))
        elif isinstance(s, str):
            items.append((s, s))
    return items


def live_sell_price(provider_name, service_code, country_code):
    """Sell price from the provider's live cost, cached 10 min.
    Returns Decimal or None if the provider has no price for it."""
    key = f'live_sell:{provider_name}:{service_code}:{country_code}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        cost = _extract_cost(
            get_provider(provider_name).get_price(service_code, country_code))
    except Exception as e:
        logger.warning('Live price failed %s/%s/%s: %s',
                       provider_name, service_code, country_code, e)
        return None
    if not cost or cost <= 0:
        return None
    sell = (cost * _margin()).quantize(Decimal('0.01'))
    cache.set(key, sell, LIVE_CACHE_TTL)
    return sell


def resolve_sell_price(provider_name, service, country):
    """The one place a price is decided. DB row wins; else live + margin."""
    pricing = (Pricing.objects
               .filter(provider=provider_name, service=service, country=country,
                       is_available=True)
               .first())
    if pricing and pricing.sell_price > 0:
        return pricing.sell_price
    return live_sell_price(provider_name, service.code, country.code)


def live_catalog(provider_name, country_code, exclude_codes=()):
    """Everything else the provider offers for this country, priced live.
    Codes in exclude_codes are already covered by DB Pricing and win."""
    provider = get_provider(provider_name)
    if not hasattr(provider, 'get_services'):
        return []
    key = f'live_catalog:{provider_name}:{country_code}'
    cached = cache.get(key)
    if cached is not None:
        items = cached
    else:
        try:
            items = _extract_catalog(provider.get_services(country_code))
        except Exception as e:
            logger.warning('Live catalog failed %s/%s: %s',
                           provider_name, country_code, e)
            return []
        cache.set(key, items, LIVE_CACHE_TTL)

    out = []
    for code, name in items:
        if code in exclude_codes:
            continue
        sell = live_sell_price(provider_name, code, country_code)
        if sell:
            out.append({'code': code, 'name': name, 'price': str(sell)})
    return out


# ----------------------------------------------------------------------
# Order flow
# ----------------------------------------------------------------------

@transaction.atomic
def reserve_number(user, service_code, country_code=None, provider_name='instantnums'):
    """Reserve a number. Price comes from DB Pricing if present, else live.
    Wallet is NOT charged — charge happens on OTP delivery."""
    provider = get_provider(provider_name)

    service, _ = Service.objects.get_or_create(
        code=service_code, provider=provider_name,
        defaults={'name': service_code, 'is_active': True})
    country = Country.objects.get(code=country_code, is_active=True)

    sell_price = resolve_sell_price(provider_name, service, country)
    if not sell_price:
        raise PricingNotAvailable(
            f'{service.name} is not available for {country.name} yet.')

    if not can_afford(user, sell_price):
        raise InsufficientFunds(
            f'You need {settings.CURRENCY_SYMBOL}{sell_price} to buy this number.')

    data = provider.purchase(service.code, country.code)

    phone = data.get('phone_number') or data.get('number') or ''
    provider_order_id = str(data.get('order_id') or data.get('id') or '')

    return NumberOrder.objects.create(
        user=user,
        service=service,
        country=country,
        provider=provider_name,
        price=sell_price,
        status='active',
        phone_number=phone,
        provider_order_id=provider_order_id,
        expires_at=timezone.now() + ORDER_TIMEOUT,
    )


@transaction.atomic
def maybe_deliver(order):
    """Poll the provider for the OTP. Charges the wallet ONCE, in the same
    transaction as marking completed — money and state can never disagree."""
    order = NumberOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != 'active':
        return None

    result = get_provider(order.provider).check_sms(order.provider_order_id)
    if result.get('status') == 'waiting':
        return None

    code = str(result.get('sms') or '').strip()
    if not code:
        return None

    debit(order.user, order.price,
          description=f'{order.service.name} number {order.phone_number}',
          meta={'order_id': order.id, 'provider_order_id': order.provider_order_id})
    order.status = 'completed'
    order.save(update_fields=['status'])

    return SmsMessage.objects.create(
        order=order,
        sender=order.service.name,
        text=result.get('full_sms') or f'Your {order.service.name} verification code is {code}',
        otp_code=code,
    )


@transaction.atomic
def cancel_user_order(order):
    """User-initiated cancel. Best-effort provider cancel (we never charged,
    so even if the provider call fails we can release locally)."""
    order = NumberOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != 'active':
        return False

    if order.provider_order_id:
        try:
            get_provider(order.provider).cancel(order.provider_order_id)
        except Exception:
            pass

    order.status = 'cancelled'
    order.save(update_fields=['status'])
    return True


@transaction.atomic
def expire_order(order):
    """Timeout path: release the order. Nothing was charged, so no refund."""
    order = NumberOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != 'active':
        return False
    order.status = 'expired'
    order.save(update_fields=['status'])
    return True