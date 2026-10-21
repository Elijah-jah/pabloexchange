from django.apps import AppConfig


class SmsmarketConfig(AppConfig):
    name = 'smsmarket'

class SmsmarketConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'smsmarket'

    def ready(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from django_apscheduler.jobstores import DjangoJobStore

        from .jobs import deliver_pending_sms_job, expire_stale_orders_job

        scheduler = BackgroundScheduler()
        scheduler.add_jobstore(DjangoJobStore(), 'default')
        scheduler.add_job(deliver_pending_sms_job, 'interval', seconds=30,
                          id='deliver_pending_sms', replace_existing=True)
        scheduler.add_job(expire_stale_orders_job, 'interval', minutes=1,
                          id='expire_stale_orders', replace_existing=True)
        scheduler.start()