from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response, current_app
from flask_login import login_required
from datetime import date, datetime, timedelta
from decimal import Decimal
from app import db
from app.models import Invoice, Client, TimeEntry
import calendar
import json

invoices_bp = Blueprint("invoices", __name__, url_prefix="/invoices")


def next_invoice_number():
    """Generate the next sequential invoice number."""
    from app.settings import Setting
    last = Invoice.query.order_by(Invoice.id.desc()).first()
    if last:
        try:
            n = int(last.invoice_number.replace("INV-", ""))
            return f"INV-{n + 1}"
        except (ValueError, AttributeError):
            pass
    start = int(Setting.get("invoice_start_number", "1001"))
    return f"INV-{start}"


@invoices_bp.route("/")
@login_required
def index():
    invoices = Invoice.query.order_by(Invoice.issued_date.desc()).all()
    return render_template("invoices/index.html", invoices=invoices)


@invoices_bp.route("/new/monthly/<int:client_id>", methods=["GET", "POST"])
@login_required
def new_monthly(client_id):
    """Generate a monthly retainer invoice for a client."""
    client = db.get_or_404(Client, client_id)

    today = date.today()
    # Default to previous month
    if today.month == 1:
        default_year, default_month = today.year - 1, 12
    else:
        default_year, default_month = today.year, today.month - 1

    year = int(request.args.get("year", default_year))
    month = int(request.args.get("month", default_month))

    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    # Pull time entries for this period
    entries = TimeEntry.query.filter(
        TimeEntry.client_id == client_id,
        TimeEntry.started_at >= datetime.combine(month_start, datetime.min.time()),
        TimeEntry.started_at <= datetime.combine(month_end, datetime.max.time()),
        TimeEntry.ended_at.isnot(None),
    ).all()

    total_minutes = sum(e.duration_minutes or 0 for e in entries)
    total_hours = total_minutes / 60
    overage_hours = 0
    overage_amount = Decimal("0")

    line_items = []

    if client.billing_mode == "retainer":
        line_items.append({
            "description": f"Monthly retainer — {month_start.strftime('%B %Y')}",
            "quantity": 1,
            "unit_price": float(client.retainer_amount or 0),
            "amount": float(client.retainer_amount or 0),
        })
        if client.retainer_hours and total_hours > float(client.retainer_hours):
            overage_hours = round(total_hours - float(client.retainer_hours), 2)
            rate = float(client.overage_rate or client.hourly_rate or 0)
            overage_amount = Decimal(str(round(overage_hours * rate, 2)))
            line_items.append({
                "description": f"Overage hours ({overage_hours}h @ ${rate}/hr)",
                "quantity": overage_hours,
                "unit_price": rate,
                "amount": float(overage_amount),
            })
    else:
        rate = float(client.hourly_rate or 0)
        amount = round(total_hours * rate, 2)
        line_items.append({
            "description": f"Services — {month_start.strftime('%B %Y')} ({round(total_hours, 2)}h @ ${rate}/hr)",
            "quantity": round(total_hours, 2),
            "unit_price": rate,
            "amount": amount,
        })

    subtotal = sum(item["amount"] for item in line_items)

    if request.method == "POST":
        notes = request.form.get("notes", "").strip()
        due_days = int(request.form.get("due_days", 30))

        invoice = Invoice(
            client_id=client_id,
            invoice_number=next_invoice_number(),
            invoice_type="monthly",
            period_start=month_start,
            period_end=month_end,
            line_items=line_items,
            subtotal=subtotal,
            total=subtotal,
            status="draft",
            issued_date=today,
            due_date=today + timedelta(days=due_days),
            notes=notes,
        )
        db.session.add(invoice)

        # Link time entries to this invoice
        for entry in entries:
            entry.invoice_id = invoice.id

        db.session.commit()
        flash(f"Invoice {invoice.invoice_number} created.", "success")
        return redirect(url_for("invoices.detail", invoice_id=invoice.id))

    return render_template(
        "invoices/new_monthly.html",
        client=client,
        entries=entries,
        total_hours=round(total_hours, 2),
        overage_hours=overage_hours,
        line_items=line_items,
        subtotal=subtotal,
        year=year,
        month=month,
        month_name=month_start.strftime("%B %Y"),
        month_start=month_start,
        month_end=month_end,
    )


@invoices_bp.route("/new/manual", methods=["GET", "POST"])
@login_required
def new_manual():
    """Create a manual or project invoice."""
    clients = Client.query.filter_by(is_active=True).order_by(Client.name).all()

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        notes = request.form.get("notes", "").strip()
        due_days = int(request.form.get("due_days", 30))
        today = date.today()

        # Parse line items from form (submitted as parallel arrays)
        descriptions = request.form.getlist("item_description")
        quantities = request.form.getlist("item_quantity")
        unit_prices = request.form.getlist("item_unit_price")

        line_items = []
        for desc, qty, price in zip(descriptions, quantities, unit_prices):
            try:
                q = float(qty)
                p = float(price)
                line_items.append({
                    "description": desc.strip(),
                    "quantity": q,
                    "unit_price": p,
                    "amount": round(q * p, 2),
                })
            except (ValueError, TypeError):
                continue

        if not client_id or not line_items:
            flash("Client and at least one line item are required.", "error")
            return render_template("invoices/new_manual.html", clients=clients)

        subtotal = sum(item["amount"] for item in line_items)

        invoice = Invoice(
            client_id=client_id,
            invoice_number=next_invoice_number(),
            invoice_type="project",
            line_items=line_items,
            subtotal=subtotal,
            total=subtotal,
            status="draft",
            issued_date=today,
            due_date=today + timedelta(days=due_days),
            notes=notes,
        )
        db.session.add(invoice)
        db.session.commit()
        flash(f"Invoice {invoice.invoice_number} created.", "success")
        return redirect(url_for("invoices.detail", invoice_id=invoice.id))

    return render_template("invoices/new_manual.html", clients=clients)


@invoices_bp.route("/<int:invoice_id>")
@login_required
def detail(invoice_id):
    invoice = db.get_or_404(Invoice, invoice_id)
    return render_template("invoices/detail.html", invoice=invoice)


@invoices_bp.route("/<int:invoice_id>/print")
@login_required
def print_view(invoice_id):
    """Clean printable/PDF-ready view."""
    invoice = db.get_or_404(Invoice, invoice_id)
    return render_template("invoices/print.html", invoice=invoice)


@invoices_bp.route("/<int:invoice_id>/pdf")
@login_required
def download_pdf(invoice_id):
    """Generate and download a PDF of the invoice."""
    invoice = db.get_or_404(Invoice, invoice_id)
    html = render_template("invoices/print.html", invoice=invoice, pdf_mode=True)

    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
        response = make_response(pdf)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = (
            f"attachment; filename=invoice-{invoice.invoice_number}.pdf"
        )
        return response
    except Exception as e:
        flash(f"PDF generation failed: {e}", "error")
        return redirect(url_for("invoices.print_view", invoice_id=invoice_id))


@invoices_bp.route("/<int:invoice_id>/status", methods=["POST"])
@login_required
def update_status(invoice_id):
    invoice = db.get_or_404(Invoice, invoice_id)
    new_status = request.form.get("status")
    if new_status in ("draft", "sent", "paid"):
        invoice.status = new_status
        if new_status == "paid" and not invoice.paid_date:
            invoice.paid_date = date.today()
        db.session.commit()
        flash(f"Invoice marked as {new_status}.", "success")
    return redirect(url_for("invoices.detail", invoice_id=invoice_id))


@invoices_bp.route("/<int:invoice_id>/delete", methods=["POST"])
@login_required
def delete(invoice_id):
    invoice = db.get_or_404(Invoice, invoice_id)
    # Unlink time entries
    for entry in invoice.time_entries:
        entry.invoice_id = None
    db.session.delete(invoice)
    db.session.commit()
    flash("Invoice deleted.", "success")
    return redirect(url_for("invoices.index"))
