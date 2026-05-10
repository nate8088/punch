"""
Audit log service.

Centralized helper for recording auditable events. Call `log_event()` from
routes / services to record a human-readable description of what happened.

Design notes:
- Events are committed in the same transaction as the action they're describing,
  so if the action rolls back, the audit row rolls back with it. Call sites
  should call log_event() *before* db.session.commit(), not after.
- For system events (scheduler, etc.) where there's no current_user,
  user_id is left None.
- The retention pruner runs daily and respects the audit_log_retention_days
  setting (0 = keep forever, the default).
"""
from datetime import datetime, timezone, timedelta
from flask_login import current_user
from app import db
from app.models import AuditLog
from app.settings import Setting
import logging

log = logging.getLogger(__name__)


def log_event(event_type, description, entity_type=None, entity_id=None, meta=None, user_id=None):
    """
    Record an audit event. Adds to the session — caller is responsible for commit.

    event_type: short dotted identifier, e.g. 'invoice.sent', 'client.created'
    description: human-readable string for the audit page
    entity_type / entity_id: optional link to the affected record
    meta: optional dict for event-specific data (will be JSON-encoded)
    user_id: override the actor; defaults to current_user when authenticated
    """
    # Resolve user_id: explicit override > current_user > None (system event)
    if user_id is None:
        try:
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
        except Exception:
            # Outside request context (e.g., scheduler) — leave as None
            user_id = None

    entry = AuditLog(
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        description=description,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        meta=meta,
    )
    db.session.add(entry)


def prune_old_entries():
    """
    Delete audit log entries older than `audit_log_retention_days` setting.
    No-op if the setting is unset, '0', or non-numeric (= keep forever).
    Returns the number of rows deleted.
    """
    raw = Setting.get("audit_log_retention_days", "0")
    try:
        days = int(raw)
    except (ValueError, TypeError):
        days = 0

    if days <= 0:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted = AuditLog.query.filter(AuditLog.timestamp < cutoff).delete(synchronize_session=False)
    db.session.commit()
    if deleted:
        log.info(f"Audit pruner removed {deleted} entries older than {days} days.")
    return deleted
