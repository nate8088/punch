"""
Long-running timer notification service.
Sends a one-time email reminder when a timer has been running longer than
the configured threshold (default 8 hours). Prevents repeat nags by
stamping long_running_notified_at on the TimeEntry once notified.

Callers must invoke this inside an app context.
"""
from datetime import datetime, timezone, timedelta
import logging

from app import db
from app.models import TimeEntry
from app.settings import Setting
from app.services.audit import log_event

log = logging.getLogger(__name__)


def check_long_running_timers():
    """
    Find open timers older than the threshold that haven't been notified yet.
    Send one email per matching entry, stamp notified_at, commit.
    Must be called inside an app context.
    """
    from app.services.email import smtp_configured, send_email

    if not smtp_configured():
        log.info("Long-running timer check: SMTP not configured, skipping.")
        return

    owner_email = Setting.get("business_email")
    if not owner_email:
        log.info("Long-running timer check: no business_email set, skipping.")
        return

    try:
        threshold_hours = float(Setting.get("long_running_timer_hours", "8"))
    except (TypeError, ValueError):
        threshold_hours = 8.0

    # Threshold of 0 disables the feature
    if threshold_hours <= 0:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)

    candidates = TimeEntry.query.filter(
        TimeEntry.ended_at.is_(None),
        TimeEntry.long_running_notified_at.is_(None),
        TimeEntry.started_at < cutoff,
    ).all()

    if not candidates:
        return

    for entry in candidates:
        try:
            _send_reminder(entry, owner_email, send_email)
            entry.long_running_notified_at = datetime.now(timezone.utc)
            log_event(
                "timer.long_running_notified",
                f"Sent long-running timer reminder for entry {entry.id} "
                f"({entry.client.name}, started {entry.started_at.isoformat()}).",
                entity_type="time_entry",
                entity_id=entry.id,
                meta={"to": owner_email, "threshold_hours": threshold_hours},
            )
            db.session.commit()
            log.info(f"Sent long-running timer reminder for entry {entry.id}")
        except Exception as e:
            # One bad entry shouldn't block the rest. Roll back, keep going.
            db.session.rollback()
            log.error(f"Failed to send long-running timer reminder for entry {entry.id}: {e}")


def _send_reminder(entry, owner_email, send_email):
    """Build and send the reminder email for a single entry."""
    business_name = Setting.get("business_name") or "Punch"
    client_name = entry.client.name

    # Elapsed time, rounded to nearest minute for display
    now_utc = datetime.now(timezone.utc)
    started = entry.started_at if entry.started_at.tzinfo else entry.started_at.replace(tzinfo=timezone.utc)
    elapsed = now_utc - started
    elapsed_hours = int(elapsed.total_seconds() // 3600)
    elapsed_minutes = int((elapsed.total_seconds() % 3600) // 60)
    elapsed_str = f"{elapsed_hours}h {elapsed_minutes}m"

    # Start time in the configured local timezone for display.
    # Falls back to UTC if no zone is set or zoneinfo lookup fails.
    started_display = _format_local(started)

    subject = f"\u23f1 {business_name}: Timer still running ({elapsed_str})"
    body = (
        f"Heads up \u2014 you have a Punch timer that's been running for {elapsed_str}.\n\n"
        f"Client: {client_name}\n"
        f"Started: {started_display}\n"
        f"Elapsed: {elapsed_str}\n\n"
        f"If you forgot to punch out, head over to Punch and stop the timer.\n"
        f"(This is a one-time reminder \u2014 you won't get another email for this entry.)\n"
    )

    send_email(to_addresses=owner_email, subject=subject, body=body)


def _format_local(dt_aware):
    """
    Format an aware UTC datetime in the configured local timezone, if any.
    Falls back to UTC if conversion fails.
    """
    tz_name = Setting.get("timezone")
    if tz_name:
        try:
            from zoneinfo import ZoneInfo
            local = dt_aware.astimezone(ZoneInfo(tz_name))
            return local.strftime("%Y-%m-%d %I:%M %p %Z")
        except Exception:
            pass
    return dt_aware.strftime("%Y-%m-%d %H:%M UTC")
