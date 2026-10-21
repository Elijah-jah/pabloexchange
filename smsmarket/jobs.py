import logging
from datetime import timedelta

from django.utils import timezone

from .models import NumberOrder
from .services import cancel_user_order, maybe_deliver

logger = logging.getLogger(__name__)


def deliver_pending_sms_job():
    """Server-side sweep: poll active orders, deliver OTPs, charge once.

    Runs every 30s via APScheduler — works even when every user's tab is
    closed. maybe_deliver is idempotent (charges exactly once), so repeated
    runs are safe.
    """
    qs = NumberOrder.objects.filter(status='active')
    delivered = 0
    for order in qs:
        try:
            had_sms = order.messages.exists()
            maybe_deliver(order)
            order.refresh_from_db()
            if not had_sms and order.messages.exists():
                delivered += 1
                logger.info('Delivery sweep: SMS delivered for order %s', order.id)
        except Exception:
            logger.exception('Delivery sweep failed for order %s', order.id)
    logger.info('>>> SMS DELIVERY SWEEP — %d active, %d delivered <<<',
                qs.count(), delivered)


def expire_stale_orders_job():
    """Cancel active orders whose rental window has passed (no charge)."""
    qs = NumberOrder.objects.filter(status='active',
                                    expires_at__lt=timezone.now())
    expired = 0
    for order in qs:
        try:
            if cancel_user_order(order):
                expired += 1
        except Exception:
            logger.exception('Expire failed for order %s', order.id)
    if expired:
        logger.info('Expired %d stale orders', expired)