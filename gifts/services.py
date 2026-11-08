import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from wallet.services import balance as get_balance, can_afford, debit

from .models import GiftOrder, GiftProduct

logger = logging.getLogger(__name__)


class GiftOrderError(Exception):
    pass


def send_gift_order_email(order_pk):
    """Send a saved order to support. A mail failure never removes the order."""
    try:
        order = GiftOrder.objects.select_related("user").get(pk=order_pk)
    except GiftOrder.DoesNotExist:
        return False

    support_email = (
        getattr(settings, "SUPPORT_EMAIL", "")
        or getattr(settings, "DEFAULT_FROM_EMAIL", "")
    )
    if not support_email:
        logger.error("Gift order %s has no SUPPORT_EMAIL configured", order.order_id)
        return False

    subject = f"New gift order {order.order_id} — {order.product_name}"
    message = f"""A new gift order has been placed on PabloExchange.

ORDER
Order reference: {order.order_id}
Status: {order.get_status_display()}
Product: {order.product_name}
Category: {order.category_name}
Price: NGN {order.price:,.2f}
Placed: {order.created_at:%B %d, %Y at %H:%M}

CUSTOMER
Username: {order.user.username}
Email: {order.user.email or 'Not provided'}

RECIPIENT
Full name: {order.recipient_full_name}
Address: {order.recipient_address}
Postal / ZIP code: {order.recipient_postal_code}
Country: {order.recipient_country}
Phone: {order.recipient_phone}
Delivery note: {order.customer_note or 'None'}

Open Django admin → Gifts → Gift orders to process this order.
"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[support_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Support email failed for gift order %s", order.order_id)
        return False

    GiftOrder.objects.filter(pk=order.pk).update(
        support_email_sent_at=timezone.now()
    )
    return True


@transaction.atomic
def create_gift_order(user, product_id, recipient_data):
    product = (
        GiftProduct.objects.select_for_update()
        .select_related("category")
        .filter(pk=product_id, is_active=True, category__is_active=True)
        .first()
    )
    if product is None:
        raise GiftOrderError("This gift is no longer available.")

    if not can_afford(user, product.price):
        balance = get_balance(user)
        raise GiftOrderError(
            f"Insufficient balance. This gift costs \u20A6{product.price:,.2f}, "
            f"but your wallet balance is \u20A6{balance:,.2f}."
        )

    image_url = ""
    if product.image:
        try:
            image_url = product.image.url
        except (ValueError, AttributeError):
            image_url = ""

    order = GiftOrder.objects.create(
        user=user,
        product=product,
        product_name=product.name,
        category_name=product.category.name,
        product_image_url=image_url,
        price=product.price,
        status="pending",
        **recipient_data,
    )

    try:
        debit(
            user,
            product.price,
            description=f"Gift order {order.order_id} — {product.name}",
            meta={"gift_order_id": order.id, "order_id": order.order_id},
        )
    except Exception as exc:
        logger.exception("Wallet charge failed for gift order %s", order.order_id)
        raise GiftOrderError(
            "We could not complete the wallet charge. No gift order was placed; please try again."
        ) from exc

    transaction.on_commit(
        lambda order_pk=order.pk: send_gift_order_email(order_pk)
    )
    return order