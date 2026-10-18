from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from countries.models import Country
from pricing.models import Pricing
from wallet.services import can_afford, debit

from .models import NumberOrder, Service, SmsMessage
from .providers import get_provider

ORDER_TIMEOUT = timedelta(minutes=15)


class InsufficientFunds(Exception):
    pass


class PricingNotAvailable(Exception):
    pass


@transaction.atomic
def reserve_number(user, service_code, country_code=None):
    """Purchase a number using the pre-synced Pricing row only.
    Wallet is NOT charged — charge happens on OTP delivery."""
    service = Service.objects.get(code=service_code, is_active=True)
    country = Country.objects.get(code=country_code, is_active=True)
    provider = get_provider()

    # Price comes ONLY from the Pricing table — no live provider calls
    pricing = (Pricing.objects
               .filter(service=service, country=country, is_available=True)
               .first())
    if not pricing or pricing.sell_price <= 0:
        raise PricingNotAvailable(
            f'{service.name} is not available for {country.name} yet.')

    if not can_afford(user, pricing.sell_price):
        raise InsufficientFunds(
            f'You need {settings.CURRENCY_SYMBOL}{pricing.sell_price} to buy this number.')

    data = provider.purchase(service.code, country.code)

    phone = data.get('phone_number') or data.get('number') or ''
    provider_order_id = str(data.get('order_id') or data.get('id') or '')

    return NumberOrder.objects.create(
        user=user,
        service=service,
        country=country,
        price=pricing.sell_price,
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

    result = get_provider().check_sms(order.provider_order_id)
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
            get_provider().cancel(order.provider_order_id)
        except Exception:
            # Logged by the provider; local release is still safe —
            # charge-on-delivery means nothing was taken.
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