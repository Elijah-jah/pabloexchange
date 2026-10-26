import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class SmsmarketConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'smsmarket'

    def ready(self):
        # In-memory jobstore on purpose: job definitions are code — they
        # re-register on every boot, so persisting them in the DB
        # (DjangoJobStore) caused lock errors for zero benefit.
        try:
            from apscheduler.schedulers.background import BackgroundScheduler

            from .jobs import deliver_pending_sms_job, expire_stale_orders_job

            scheduler = BackgroundScheduler()
            scheduler.add_job(
                deliver_pending_sms_job, 'interval', seconds=5,
                id='deliver_pending_sms', replace_existing=True,
                max_instances=1, coalesce=True,
            )
            scheduler.add_job(
                expire_stale_orders_job, 'interval', seconds=60,
                id='expire_stale_orders', replace_existing=True,
                max_instances=1, coalesce=True,
            )
            scheduler.start()
            print('APScheduler started (memory jobstore)')   # instead of logger.info(...)
        except Exception:
            logger.exception('APScheduler failed to start')