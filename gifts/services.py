
import logging
import time
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

from wallet.services import balance as get_balance, can_afford, debit

from .models import GiftOrder, GiftOrderImage, GiftProduct

logger = logging.getLogger(__name__)

MAX_GIFT_IMAGES = 5
MAX_GIFT_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB per photo
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class GiftOrderError(Exception):
    """Order placement failed. ``field`` optionally points at a form field."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field


def validate_gift_images(images):
    """Validate customer photos before any wallet charge happens."""
    images = [image for image in (images or []) if image]
    if len(images) > MAX_GIFT_IMAGES:
        raise GiftOrderError(
            f"You can attach at most {MAX_GIFT_IMAGES} photos to one gift order.",
            field="images",
        )
    for image in images:
        content_type = getattr(image, "content_type", "") or ""
        if content_type and content_type.lower() not in ALLOWED_IMAGE_TYPES:
            raise GiftOrderError(
                f"{image.name} is not a supported image. Please upload JPG, PNG, WEBP or GIF photos.",
                field="images",
            )
        if image.size > MAX_GIFT_IMAGE_SIZE:
            raise GiftOrderError(
                f"{image.name} is larger than 5 MB. Please choose a smaller photo.",
                field="images",
            )
    return images


def _support_email_html(order, photo_cids):
    """Branded HTML version of the support email, photos embedded inline."""
    e = escape
    rows = [
        ("Order reference", order.order_id),
        ("Status", order.get_status_display()),
        ("Product", order.product_name),
        ("Category", order.category_name),
        ("Price", f"NGN {order.price:,.2f}"),
        ("Placed", f"{order.created_at:%B %d, %Y at %H:%M}"),
    ]
    customer_rows = [
        ("Username", order.user.username),
        ("Email", order.user.email or "Not provided"),
    ]
    recipient_rows = [
        ("Full name", order.recipient_full_name),
        ("Address", order.recipient_address),
        ("Postal / ZIP code", order.recipient_postal_code),
        ("Country", order.recipient_country),
        ("Phone", order.recipient_phone),
        ("Delivery note", order.customer_note or "None"),
    ]

    def table(rows_data):
        cells = "".join(
            f'<tr>'
            f'<td style="padding:8px 0;color:#71867e;font-size:13px;width:140px;'
            f'vertical-align:top;">{e(label)}</td>'
            f'<td style="padding:8px 0;color:#12211c;font-size:13px;font-weight:600;'
            f'overflow-wrap:anywhere;">{e(str(value))}</td>'
            f'</tr>'
            for label, value in rows_data
        )
        return (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="border-collapse:collapse;">' + cells + "</table>"
        )

    def section(title, content):
        return (
            f'<p style="margin:22px 0 4px;color:#047857;font-size:11px;font-weight:800;'
            f'letter-spacing:.09em;text-transform:uppercase;">{e(title)}</p>'
            f"{content}"
        )

    if photo_cids:
        photos_html = ""
        total = len(photo_cids)
        for index, cid in enumerate(photo_cids, start=1):
            photos_html += (
                f'<p style="margin:14px 0 6px;color:#71867e;font-size:12px;">'
                f"Photo {index} of {total} — also attached to this email as a file.</p>"
                f'<img src="cid:{cid}" alt="Customer photo {index}" width="520" '
                f'style="display:block;width:100%;max-width:520px;height:auto;'
                f'border-radius:12px;border:1px solid #e0ebe6;">'
            )
    else:
        photos_html = (
            '<p style="margin:14px 0 0;color:#71867e;font-size:13px;">'
            "The customer did not attach any photos.</p>"
        )

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">
<tr><td align="center" style="padding:26px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
       style="width:100%;max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;
              border:1px solid #e5e7eb;">

  <tr><td style="background:#0b1220;padding:22px 26px;">
    <span style="color:#34d399;font-size:12px;font-weight:800;letter-spacing:.12em;
                 text-transform:uppercase;">PabloExchange</span>
    <p style="margin:6px 0 0;color:#ffffff;font-size:20px;font-weight:800;">
      New gift order {e(order.order_id)}</p>
    <p style="margin:4px 0 0;color:#a9b8c8;font-size:13px;">{e(order.product_name)}</p>
  </td></tr>

  <tr><td style="padding:22px 26px 6px;">
    {section("Order", table(rows))}
    {section("Customer", table(customer_rows))}
    {section("Recipient", table(recipient_rows))}
    {section("Customer photos", photos_html)}
  </td></tr>

  <tr><td style="padding:18px 26px 26px;">
    <p style="margin:0;color:#8aa098;font-size:12px;line-height:1.6;">
      Process this order in Django admin → Gifts → Gift orders.
      The photos above are also stored on the order and attached to this email as files.</p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def send_gift_order_email(order_pk):
    """Send a saved order to support. A mail failure never removes the order."""
    try:
        order = (
            GiftOrder.objects.select_related("user")
            .prefetch_related("images")
            .get(pk=order_pk)
        )
    except GiftOrder.DoesNotExist:
        return False

    support_email = (
        getattr(settings, "SUPPORT_EMAIL", "")
        or getattr(settings, "DEFAULT_FROM_EMAIL", "")
    )
    if not support_email:
        logger.error("Gift order %s has no SUPPORT_EMAIL configured", order.order_id)
        return False

    order_images = list(order.images.all())
    photo_line = (
        f"{len(order_images)} photo(s) — shown inline and attached to this email"
        if order_images
        else "None"
    )

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

CUSTOMER PHOTOS
{photo_line}
The photos are also stored on the order in Django admin.

Open Django admin → Gifts → Gift orders to process this order.
"""

    email = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[support_email],
    )

    # Read every photo once; each one is embedded in the HTML body AND
    # attached as a regular downloadable file.
    photo_cids = []
    photo_payloads = []
    for index, order_image in enumerate(order_images, start=1):
        try:
            with order_image.image.open("rb") as handle:
                content = handle.read()
        except Exception:
            logger.exception(
                "Could not read photo %s for gift order %s",
                order_image.pk,
                order.order_id,
            )
            continue
        filename = (
            order_image.image.name.rsplit("/", 1)[-1]
            or f"photo-{index}.jpg"
        )
        cid = f"gift-photo-{order.pk}-{index}"
        photo_cids.append(cid)
        photo_payloads.append((cid, filename, content))

    email.attach_alternative(_support_email_html(order, photo_cids), "text/html")
    email.mixed_subtype = "related"  # keep cid images linked to the HTML part

    for cid, filename, content in photo_payloads:
        inline = MIMEImage(content)
        inline.add_header("Content-ID", f"<{cid}>")
        inline.add_header("Content-Disposition", "inline", filename=filename)
        email.attach(inline)
    for cid, filename, content in photo_payloads:
        email.attach(filename, content)  # downloadable copy, MIME type from filename

    if order_images and len(photo_payloads) < len(order_images):
        logger.warning(
            "Only %s of %s photos were attached for gift order %s",
            len(photo_payloads),
            len(order_images),
            order.order_id,
        )

    try:
        email.send(fail_silently=False)
    except Exception:
        logger.exception("Support email failed for gift order %s", order.order_id)
        return False

    GiftOrder.objects.filter(pk=order.pk).update(
        support_email_sent_at=timezone.now()
    )
    return True


def send_gift_completion_email(order_pk, max_attempts=3):
    """Send the customer completion email, trying at most three times."""
    try:
        order = GiftOrder.objects.select_related("user").get(pk=order_pk)
    except GiftOrder.DoesNotExist:
        return False

    if order.status != "completed":
        logger.warning("Completion email skipped for non-completed order %s", order.order_id)
        return False

    customer_email = (order.user.email or "").strip()
    if not customer_email:
        logger.warning("Completion email skipped for %s: customer has no email", order.order_id)
        return False

    site_url = getattr(settings, "SITE_URL", "https://pabloexchange.com").rstrip("/")
    subject = "Your gift order has been sent successfully"
    message = f"""Hello {order.user.username},

Your gift order has been sent successfully.

ORDER DETAILS
Order reference: {order.order_id}
Gift: {order.product_name}
Recipient: {order.recipient_full_name}
Status: Completed
Price: NGN {order.price:,.2f}

You can view the order in My Purchases:
{site_url}/purchases/

Thank you for using PabloExchange.
"""

    for attempt in range(1, max_attempts + 1):
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[customer_email],
                fail_silently=False,
            )
            try:
                GiftOrder.objects.filter(pk=order.pk).update(
                    completion_email_sent_at=timezone.now()
                )
            except Exception:
                logger.exception(
                    "Completion email timestamp could not be saved for %s",
                    order.order_id,
                )
            logger.info(
                "Completion email sent for %s on attempt %s",
                order.order_id,
                attempt,
            )
            return True
        except Exception:
            logger.exception(
                "Completion email attempt %s/%s failed for %s",
                attempt,
                max_attempts,
                order.order_id,
            )
            if attempt < max_attempts:
                time.sleep(attempt)

    return False


@transaction.atomic
def create_gift_order(user, product_id, recipient_data, images=None):
    images = validate_gift_images(images)

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
            f"Insufficient balance. This gift costs ₦{product.price:,.2f}, "
            f"but your wallet balance is ₦{balance:,.2f}."
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

    for image in images:
        GiftOrderImage.objects.create(order=order, image=image)

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
