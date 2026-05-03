from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func
from datetime import date, datetime
from app import db
from app.models import Client, TimeEntry, Invoice

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/")
@login_required
def summary():
    # Default date range: current year
    current_year = date.today().year
    start_str = request.args.get("start", f"{current_year}-01-01")
    end_str = request.args.get("end", f"{current_year}-12-31")

    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
    except ValueError:
        start = date(current_year, 1, 1)
        end = date(current_year, 12, 31)

    clients = Client.query.order_by(Client.name).all()

    rows = []
    totals = {"hours": 0.0, "billable_hours": 0.0, "revenue": 0.0}

    for client in clients:
        entries = (
            TimeEntry.query
            .filter(
                TimeEntry.client_id == client.id,
                TimeEntry.ended_at.isnot(None),
                func.date(TimeEntry.started_at) >= start,
                func.date(TimeEntry.started_at) <= end,
            )
            .all()
        )

        if not entries:
            continue

        total_hours = sum(e.duration_hours for e in entries)
        billable_hours = sum(e.duration_hours for e in entries if e.invoice_id is not None)

        if client.billing_mode == "hourly":
            revenue = billable_hours * float(client.hourly_rate or 0)

        elif client.billing_mode == "retainer":
            # Count distinct billed months for retainer fee
            billed_months = set()
            for e in entries:
                if e.invoice_id is not None:
                    billed_months.add((e.started_at.year, e.started_at.month))
            retainer_revenue = len(billed_months) * float(client.retainer_amount or 0)

            # Overage: hours beyond cap per billed month
            overage_revenue = 0.0
            if client.retainer_hours and client.overage_rate:
                billed_entries = [e for e in entries if e.invoice_id is not None]
                month_map = {}
                for e in billed_entries:
                    key = (e.started_at.year, e.started_at.month)
                    month_map.setdefault(key, 0.0)
                    month_map[key] += e.duration_hours
                for hrs in month_map.values():
                    if hrs > float(client.retainer_hours):
                        overage_revenue += (hrs - float(client.retainer_hours)) * float(client.overage_rate)

            revenue = retainer_revenue + overage_revenue

        else:
            revenue = 0.0

        rows.append({
            "client": client,
            "total_hours": total_hours,
            "billable_hours": billable_hours,
            "revenue": revenue,
        })

        totals["hours"] += total_hours
        totals["billable_hours"] += billable_hours
        totals["revenue"] += revenue

    return render_template(
        "reports/summary.html",
        rows=rows,
        totals=totals,
        start=start,
        end=end,
    )


@reports_bp.route("/unbilled/")
@login_required
def unbilled():
    clients = Client.query.order_by(Client.name).all()

    rows = []
    total_hours = 0.0

    for client in clients:
        entries = (
            TimeEntry.query
            .filter(
                TimeEntry.client_id == client.id,
                TimeEntry.ended_at.isnot(None),
                TimeEntry.invoice_id.is_(None),
            )
            .order_by(TimeEntry.started_at.desc())
            .all()
        )

        if not entries:
            continue

        hours = sum(e.duration_hours for e in entries)
        rows.append({
            "client": client,
            "entries": entries,
            "hours": hours,
        })
        total_hours += hours

    return render_template(
        "reports/unbilled.html",
        rows=rows,
        total_hours=total_hours,
    )
