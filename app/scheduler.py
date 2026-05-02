"""
APScheduler configuration for Punch.
Runs auto-invoicing on the 1st of each month.
"""
from flask_apscheduler import APScheduler

scheduler = APScheduler()


def init_scheduler(app):
    scheduler.init_app(app)

    @scheduler.task("cron", id="auto_invoice", day=1, hour=0, minute=5)
    def auto_invoice_job():
        from app.services.auto_invoice import run_auto_invoicing
        run_auto_invoicing(app)

    scheduler.start()