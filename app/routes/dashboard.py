from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import datetime, date, timedelta
from app.models import Client, TimeEntry, Invoice
from app import db
import calendar

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    today = date.today()

    # Range toggle: "month" (default) or "week".
    # Weeks run Monday through Sunday.
    range_type = request.args.get("range", "month")
    if range_type not in ("month", "week"):
        range_type = "month"

    # Anchor date: any date inside the period being viewed.
    # Defaults to today; garbage input also falls back to today.
    anchor_raw = request.args.get("anchor", "")
    try:
        anchor = date.fromisoformat(anchor_raw)
    except ValueError:
        anchor = today

    if range_type == "week":
        period_start = anchor - timedelta(days=anchor.weekday())  # Monday
        period_end = period_start + timedelta(days=6)              # Sunday
        period_label = f"Week of {period_start.strftime('%b %d, %Y')}"
        period_subtitle = "Weekly overview"
        prev_anchor = period_start - timedelta(days=7)
        next_anchor = period_start + timedelta(days=7)
        is_current = period_start <= today <= period_end
    else:
        period_start = anchor.replace(day=1)
        period_end = anchor.replace(day=calendar.monthrange(anchor.year, anchor.month)[1])
        period_label = anchor.strftime("%B %Y")
        period_subtitle = "Monthly overview"
        prev_anchor = (period_start - timedelta(days=1)).replace(day=1)
        next_anchor = period_end + timedelta(days=1)
        is_current = period_start <= today <= period_end

    # Running timer (if any)
    running_entry = TimeEntry.query.filter_by(ended_at=None).first()

    # Active clients
    clients = Client.query.filter_by(is_active=True).order_by(Client.name).all()

    # Hours per client for the selected period
    summaries = []
    for client in clients:
        entries = TimeEntry.query.filter(
            TimeEntry.client_id == client.id,
            TimeEntry.started_at >= datetime.combine(period_start, datetime.min.time()),
            TimeEntry.started_at <= datetime.combine(period_end, datetime.max.time()),
            TimeEntry.ended_at.isnot(None)
        ).all()

        total_minutes = sum(e.duration_minutes or 0 for e in entries)
        total_hours = total_minutes / 60

        # Overage is only meaningful against the monthly retainer cap,
        # so it's computed (and shown) only in month view.
        overage_hours = 0
        if range_type == "month" and client.billing_mode == "retainer" and client.retainer_hours:
            overage_hours = max(0, total_hours - float(client.retainer_hours))

        summaries.append({
            "client": client,
            "total_hours": round(total_hours, 2),
            "overage_hours": round(overage_hours, 2),
            "entry_count": len(entries),
        })

    # Recent unpaid invoices
    unpaid_invoices = Invoice.query.filter(
        Invoice.status.in_(["draft", "sent"])
    ).order_by(Invoice.issued_date.desc()).limit(5).all()

    return render_template(
        "dashboard.html",
        running_entry=running_entry,
        clients=clients,
        summaries=summaries,
        unpaid_invoices=unpaid_invoices,
        today=today,
        range_type=range_type,
        period_label=period_label,
        period_subtitle=period_subtitle,
        prev_anchor=prev_anchor.isoformat(),
        next_anchor=next_anchor.isoformat(),
        is_current=is_current,
    )
