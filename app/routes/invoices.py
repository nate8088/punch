from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response, current_app
from flask_login import login_required
from datetime import date, datetime, timedelta
from decimal import Decimal
from app import db
from app.models import Invoice, Client, TimeEntry
from app.services.audit import log_event
import calendar
import json

invoices_bp = Blueprint("invoices", __name__, url_prefix="/invoices")


def next_invoice_number():
    """Generate the next sequential invoice number."""
    from app.settings import Setting
    # Find the highest existing invoice number numerically
    invoices = Invoice.query.all()
    max_n = 0
    for inv in invoices:
        try:
            n = int(inv.invoice_number.replace("INV-", ""))
            if n > max_n:
                max_n = n
        except (ValueError, AttributeError):
            pass
    if max_n > 0:
        candidate = max_n + 1
    else:
        candidate = int(Setting.get("invoice_start_number", "1001"))
    # Safety check — keep incrementing until we find a free number
    while Invoice.query.filter_by(invoice_number=f"INV-{candidate}").first():
        candidate += 1
    return f"INV-{candidate}"


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
            show_time_detail=request.form.get("show_time_detail") == "on",
        )
        db.session.add(invoice)
        db.session.flush()  # get invoice.id before commit

        # Link time entries to this invoice
        for entry in entries:
            entry.invoice_id = invoice.id

        log_event(
            "invoice.created",
            f"Created monthly invoice {invoice.invoice_number} for {client.name} ({month_start.strftime('%B %Y')}, ${invoice.total}).",
            entity_type="invoice",
            entity_id=invoice.id,
        )
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
        db.session.flush()
        client = db.session.get(Client, client_id)
        log_event(
            "invoice.created",
            f"Created manual invoice {invoice.invoice_number} for {client.name} (${invoice.total}).",
            entity_type="invoice",
            entity_id=invoice.id,
        )
        db.session.commit()
        flash(f"Invoice {invoice.invoice_number} created.", "success")
        return redirect(url_for("invoices.detail", invoice_id=invoice.id))

    return render_template("invoices/new_manual.html", clients=clients)


@invoices_bp.route("/<int:invoice_id>")
@login_required
def detail(invoice_id):
    invoice = db.get_or_404(Invoice, invoice_id)
    from app.services.email import smtp_configured
    return render_template(
        "invoices/detail.html",
        invoice=invoice,
        smtp_ok=smtp_configured(),
    )


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
        old_status = invoice.status
        invoice.status = new_status
        if new_status == "paid" and not invoice.paid_date:
            invoice.paid_date = date.today()
        if old_status != new_status:
            log_event(
                "invoice.status_changed",
                f"Invoice {invoice.invoice_number} status changed: {old_status} → {new_status}.",
                entity_type="invoice",
                entity_id=invoice.id,
                meta={"from": old_status, "to": new_status},
            )
        db.session.commit()
        flash(f"Invoice marked as {new_status}.", "success")
    return redirect(url_for("invoices.detail", invoice_id=invoice_id))


@invoices_bp.route("/<int:invoice_id>/send", methods=["GET", "POST"])
@login_required
def send_to_client(invoice_id):
    """Review and send an invoice to the client via email."""
    from app.services.email import smtp_configured, send_email, build_invoice_email
    from app.settings import Setting

    invoice = db.get_or_404(Invoice, invoice_id)
    client = invoice.client

    # Hard guards — these shouldn't be reachable since the button is disabled,
    # but a direct URL hit could land here.
    if not smtp_configured():
        flash("SMTP is not fully configured. Fill in email settings first.", "error")
        return redirect(url_for("invoices.detail", invoice_id=invoice.id))

    if not client.contact_email:
        flash(f"{client.name} has no contact email set. Add one on the client record first.", "error")
        return redirect(url_for("invoices.detail", invoice_id=invoice.id))

    owner_email = Setting.get("business_email")

    if request.method == "POST":
        to_address = request.form.get("to_address", "").strip()
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "").strip()
        send_copy = request.form.get("send_copy") == "on"
        attach_pdf = request.form.get("attach_pdf") == "on"

        if not to_address or not subject or not body:
            flash("To, Subject, and Body are all required.", "error")
            return redirect(url_for("invoices.send_to_client", invoice_id=invoice.id))

        # Generate PDF if requested
        pdf_bytes = None
        pdf_filename = None
        if attach_pdf:
            try:
                from weasyprint import HTML
                html = render_template("invoices/print.html", invoice=invoice, pdf_mode=True)
                pdf_bytes = HTML(string=html).write_pdf()
                pdf_filename = f"invoice-{invoice.invoice_number}.pdf"
            except Exception as e:
                flash(f"PDF generation failed: {e}", "error")
                return redirect(url_for("invoices.send_to_client", invoice_id=invoice.id))

        cc = owner_email if (send_copy and owner_email) else None

        try:
            send_email(
                to_addresses=to_address,
                subject=subject,
                body=body,
                cc_addresses=cc,
                pdf_bytes=pdf_bytes,
                pdf_filename=pdf_filename,
            )
        except Exception as e:
            flash(f"Email failed: {e}", "error")
            return redirect(url_for("invoices.send_to_client", invoice_id=invoice.id))

        # Flip status to sent (only if not already paid — don't downgrade a paid invoice)
        if invoice.status != "paid":
            invoice.status = "sent"

        recipients_meta = {"to": to_address}
        if cc:
            recipients_meta["cc"] = cc

        log_event(
            "email.invoice_sent",
            f"Sent invoice {invoice.invoice_number} to {to_address}" + (f" (CC {cc})" if cc else "") + ".",
            entity_type="invoice",
            entity_id=invoice.id,
            meta=recipients_meta,
        )
        db.session.commit()

        flash(f"Invoice {invoice.invoice_number} sent to {to_address}.", "success")
        return redirect(url_for("invoices.detail", invoice_id=invoice.id))

    # GET — render the review page with defaults
    defaults = build_invoice_email(invoice)
    return render_template(
        "invoices/send.html",
        invoice=invoice,
        client=client,
        owner_email=owner_email,
        default_to=client.contact_email,
        default_subject=defaults["subject"],
        default_body=defaults["body"],
    )


@invoices_bp.route("/<int:invoice_id>/delete", methods=["POST"])
@login_required
def delete(invoice_id):
    invoice = db.get_or_404(Invoice, invoice_id)
    audit_desc = f"Deleted invoice {invoice.invoice_number} for {invoice.client.name} (${invoice.total})."
    # Unlink time entries
    for entry in invoice.time_entries:
        entry.invoice_id = None
    log_event(
        "invoice.deleted",
        audit_desc,
        entity_type="invoice",
        entity_id=invoice.id,
    )
    db.session.delete(invoice)
    db.session.commit()
    flash("Invoice deleted.", "success")
    return redirect(url_for("invoices.index"))
