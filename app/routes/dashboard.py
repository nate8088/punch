from flask import Blueprint, render_template
from flask_login import login_required
from datetime import datetime, date, timezone
from app.models import Client, TimeEntry, Invoice
from app import db
import calendar

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    today = date.today()
    month_start = today.replace(day=1)
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])

    # Running timer (if any)
    running_entry = TimeEntry.query.filter_by(ended_at=None).first()

    # Active clients
    clients = Client.query.filter_by(is_active=True).order_by(Client.name).all()

    # This month's hours per client
    month_summaries = []
    for client in clients:
        entries = TimeEntry.query.filter(
            TimeEntry.client_id == client.id,
            TimeEntry.started_at >= datetime.combine(month_start, datetime.min.time()),
            TimeEntry.started_at <= datetime.combine(month_end, datetime.max.time()),
            TimeEntry.ended_at.isnot(None)
        ).all()

        total_minutes = sum(e.duration_minutes or 0 for e in entries)
        total_hours = total_minutes / 60

        overage_hours = 0
        if client.billing_mode == "retainer" and client.retainer_hours:
            overage_hours = max(0, total_hours - float(client.retainer_hours))

        month_summaries.append({
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
        month_summaries=month_summaries,
        unpaid_invoices=unpaid_invoices,
        today=today,
        month_name=today.strftime("%B %Y"),
    )
