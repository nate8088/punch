"""
APScheduler configuration for Punch.
Runs auto-invoicing on the 1st of each month and prunes the audit log nightly.
"""
from flask_apscheduler import APScheduler

scheduler = APScheduler()


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

    scheduler.start()
