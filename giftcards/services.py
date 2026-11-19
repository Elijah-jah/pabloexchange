import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import quote

from django.conf import settings
from django.db import transaction

from pricing.models import PricingConfiguration
from wallet.services import balance as get_balance, can_afford, debit

from .models import GiftCard, GiftCardOrder

logger = logging.getLogger(__name__)

DEFAULT_EXCHANGE_RATE = Decimal("1650")  # fallback if no PricingConfiguration exists
MAX_QUANTITY = 99


class GiftCardOrderError(Exception):
    """Purchase failed. ``field`` optionally points at a form field."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field


def get_exchange_rate():
    """Gift card NGN/USD rate — uses the Pricing configuration set in admin."""
    config = PricingConfiguration.objects.first()
    if config and config.exchange_rate:
        return Decimal(str(config.exchange_rate))
    return DEFAULT_EXCHANGE_RATE


def total_ngn_for(amount_usd, quantity, rate):
    """Total wallet charge: USD amount x quantity x exchange rate."""
    return (
        Decimal(str(amount_usd)) * int(quantity) * rate
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_whatsapp_url(order):
    """Prefilled WhatsApp DM so the buyer can claim their card from support."""
    message = (
        f"Hello, I just purchased {order.card_name} "
        f"(${order.amount_usd:,.2f} x {order.quantity} \u2014 NGN {order.total_ngn:,.2f}) "
        f"from your website. Kindly send my gift card details. "
        f"Order reference: {order.order_id}. Thank you."
    )
    number = getattr(settings, "GIFT_CARD_WHATSAPP_NUMBER", "2348071599540")
    return f"https://wa.me/{number}?text={quote(message)}"


@transaction.atomic
def create_giftcard_order(user, card_id, amount_usd, quantity, buyer_name):
    """Validate, charge the wallet and create the order.

    Everything runs in one transaction: if the wallet charge fails,
    no order row is left behind.
    """
    card = (
        GiftCard.objects.select_for_update()
        .select_related("category", "country")
        .filter(
            pk=card_id,
            is_active=True,
            category__is_active=True,
            country__is_active=True,
        )
        .first()
    )
    if card is None:
        raise GiftCardOrderError("This gift card is no longer available.")

    try:
        amount = Decimal(str(amount_usd)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise GiftCardOrderError("Enter a valid amount in dollars.", field="amount_usd")

    if amount < card.min_amount_usd or amount > card.max_amount_usd:
        raise GiftCardOrderError(
            f"Amount must be between ${card.min_amount_usd:,.2f} "
            f"and ${card.max_amount_usd:,.2f}.",
            field="amount_usd",
        )

    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        raise GiftCardOrderError("Enter a valid quantity.", field="quantity")
    if qty < 1 or qty > MAX_QUANTITY:
        raise GiftCardOrderError(
            f"Quantity must be between 1 and {MAX_QUANTITY}.", field="quantity",
        )

    buyer_name = (buyer_name or "").strip()
    if not buyer_name:
        raise GiftCardOrderError("Please enter your name.", field="buyer_name")
    if len(buyer_name) > 150:
        raise GiftCardOrderError("Name is too long (150 characters max).", field="buyer_name")

    rate = get_exchange_rate()
    total = total_ngn_for(amount, qty, rate)

    if not can_afford(user, total):
        balance = get_balance(user)
        raise GiftCardOrderError(
            f"Insufficient balance. This purchase costs \u20A6{total:,.2f}, "
            f"but your wallet balance is \u20A6{balance:,.2f}."
        )

    order = GiftCardOrder.objects.create(
        user=user,
        card=card,
        card_name=card.name,
        category_name=card.category.name,
        country_name=card.country.name,
        buyer_name=buyer_name,
        amount_usd=amount,
        quantity=qty,
        exchange_rate=rate,
        total_ngn=total,
        status="pending",
    )

    try:
        debit(
            user,
            total,
            description=(
                f"Gift card {order.order_id} \u2014 {card.name} "
                f"(${amount:,.2f} x {qty})"
            ),
            meta={"giftcard_order_id": order.id, "order_id": order.order_id},
        )
    except Exception as exc:
        logger.exception("Wallet charge failed for gift card order %s", order.order_id)
        raise GiftCardOrderError(
            "We could not complete the wallet charge. No order was placed; please try again."
        ) from exc

    return order
