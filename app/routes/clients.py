from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models import Client, TimeEntry, Invoice
from datetime import datetime
import calendar

clients_bp = Blueprint("clients", __name__, url_prefix="/clients")


@clients_bp.route("/")
@login_required
def index():
    clients = Client.query.order_by(Client.is_active.desc(), Client.name).all()
    return render_template("clients/index.html", clients=clients)


@clients_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        client = Client(
            name=request.form.get("name", "").strip(),
            contact_name=request.form.get("contact_name", "").strip(),
            contact_email=request.form.get("contact_email", "").strip(),
            address=request.form.get("address", "").strip(),
            phone=request.form.get("phone", "").strip(),
            billing_mode=request.form.get("billing_mode", "hourly"),
            notes=request.form.get("notes", "").strip(),
        )

        if client.billing_mode == "retainer":
            client.retainer_amount = request.form.get("retainer_amount") or None
            client.retainer_hours = request.form.get("retainer_hours") or None
            client.overage_rate = request.form.get("overage_rate") or None
        else:
            client.hourly_rate = request.form.get("hourly_rate") or None

        if not client.name:
            flash("Client name is required.", "error")
        else:
            db.session.add(client)
            db.session.commit()
            flash(f"Client '{client.name}' created.", "success")
            return redirect(url_for("clients.index"))

    return render_template("clients/form.html", client=None)


@clients_bp.route("/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
def edit(client_id):
    client = db.get_or_404(Client, client_id)

    if request.method == "POST":
        client.name = request.form.get("name", "").strip()
        client.contact_name = request.form.get("contact_name", "").strip()
        client.contact_email = request.form.get("contact_email", "").strip()
        client.address = request.form.get("address", "").strip()
        client.phone = request.form.get("phone", "").strip()
        client.billing_mode = request.form.get("billing_mode", "hourly")
        client.notes = request.form.get("notes", "").strip()
        client.is_active = request.form.get("is_active") == "on"
        client.auto_invoice = request.form.get("auto_invoice") == "on"

        if client.billing_mode == "retainer":
            client.retainer_amount = request.form.get("retainer_amount") or None
            client.retainer_hours = request.form.get("retainer_hours") or None
            client.overage_rate = request.form.get("overage_rate") or None
            client.hourly_rate = None
        else:
            client.hourly_rate = request.form.get("hourly_rate") or None
            client.retainer_amount = None
            client.retainer_hours = None
            client.overage_rate = None

        if not client.name:
            flash("Client name is required.", "error")
        else:
            db.session.commit()
            flash(f"Client '{client.name}' updated.", "success")
            return redirect(url_for("clients.index"))

    return render_template("clients/form.html", client=client)


@clients_bp.route("/<int:client_id>")
@login_required
def detail(client_id):
    client = db.get_or_404(Client, client_id)

    # Get year/month filter from query params, default to current month
    from datetime import date
    today = date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))

    month_start = datetime(year, month, 1)
    month_end = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)

    entries = TimeEntry.query.filter(
        TimeEntry.client_id == client_id,
        TimeEntry.started_at >= month_start,
        TimeEntry.started_at <= month_end,
    ).order_by(TimeEntry.started_at.desc()).all()

    total_minutes = sum(e.duration_minutes or 0 for e in entries if e.ended_at)
    total_hours = total_minutes / 60

    overage_hours = 0
    if client.billing_mode == "retainer" and client.retainer_hours:
        overage_hours = max(0, total_hours - float(client.retainer_hours))

    invoices = Invoice.query.filter_by(client_id=client_id).order_by(
        Invoice.issued_date.desc()
    ).all()

    # Build month navigation
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    return render_template(
        "clients/detail.html",
        client=client,
        entries=entries,
        total_hours=round(total_hours, 2),
        overage_hours=round(overage_hours, 2),
        invoices=invoices,
        year=year,
        month=month,
        month_name=datetime(year, month, 1).strftime("%B %Y"),
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
    )
