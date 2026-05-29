"""
APScheduler configuration for Punch.
Runs auto-invoicing on the 1st of each month, prunes the audit log nightly,
and checks for long-running timers every 15 minutes.
"""
import logging
from flask_apscheduler import APScheduler

scheduler = APScheduler()
log = logging.getLogger(__name__)


def init_scheduler(app):
    scheduler.init_app(app)

    @scheduler.task("cron", id="auto_invoice", day=1, hour=0, minute=5)
    def auto_invoice_job():
        from app.services.auto_invoice import run_auto_invoicing
        run_auto_invoicing(app)

    @scheduler.task("cron", id="audit_prune", hour=3, minute=0)
    def audit_prune_job():
        # Respects the audit_log_retention_days setting (0 = keep forever).
        from app.services.audit import prune_old_entries
        with app.app_context():
            prune_old_entries()

    @scheduler.task("interval", id="long_running_timer_check", minutes=15)
    def long_running_timer_job():
        from app.services.long_running_timer import check_long_running_timers
        with app.app_context():
            check_long_running_timers()

    scheduler.start()

    # Catch-up: run once at startup so an open timer that crossed the
    # threshold while the app was down still gets a reminder.
    # Failures here are non-fatal — the scheduled job will retry shortly.
    # This protects against partial-deploy states (e.g. new code, old schema).
    try:
        from app.services.long_running_timer import check_long_running_timers
        with app.app_context():
            check_long_running_timers()
    except Exception as e:
        log.warning(
            "Startup catch-up for long-running timer check failed (will retry on schedule): %s",
            e,
        )
