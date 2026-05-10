from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import datetime, date, timedelta
from app import db
from app.models import AuditLog

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


# Grouping for the filter dropdown — keys are filter values,
# values are lists of event_type prefixes that match.
EVENT_GROUPS = [
    ("all",       "All events",       None),
    ("auth",      "Authentication",   ["auth."]),
    ("time",      "Time entries",     ["time_entry."]),
    ("client",    "Clients",          ["client."]),
    ("invoice",   "Invoices",         ["invoice."]),
    ("email",     "Email",            ["email."]),
    ("auto",      "Auto-invoicing",   ["auto_invoice."]),
    ("settings",  "Settings",         ["settings."]),
]


@audit_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    group = request.args.get("group", "all")
    days = request.args.get("days", "30")

    query = AuditLog.query

    # Event-type group filter
    prefixes = next((p for k, _, p in EVENT_GROUPS if k == group), None)
    if prefixes:
        # SQL OR across the prefix matches
        from sqlalchemy import or_
        query = query.filter(or_(*[AuditLog.event_type.like(f"{p}%") for p in prefixes]))

    # Date range filter
    if days and days != "all":
        try:
            days_int = int(days)
            cutoff = datetime.utcnow() - timedelta(days=days_int)
            query = query.filter(AuditLog.timestamp >= cutoff)
        except ValueError:
            pass

    entries = query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=50)

    return render_template(
        "audit.html",
        entries=entries,
        groups=EVENT_GROUPS,
        active_group=group,
        active_days=days,
    )
