"""
Auto-invoice service.
Generates monthly invoices for clients with auto_invoice enabled.
Handles catch-up if the app was down on the 1st.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
import calendar
import logging

from app import db
from app.models import Client, Invoice, TimeEntry
from app.settings import Setting
from app.routes.invoices import next_invoice_number

log = logging.getLogger(__name__)


def generate_monthly_invoice(client, year, month):
    """
    Generate a monthly invoice for a client for the given year/month.
    Returns the Invoice object, or None if one already exists for that period.
    """
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    # Check if invoice already exists for this period
    existing = Invoice.query.filter_by(
        client_id=client.id,
        invoice_type="monthly",
        period_start=month_start,
    ).first()
    if existing:
        log.info(f"Invoice already exists for {client.name} {month_start.strftime('%B %Y')}, skipping.")
        return None

    entries = TimeEntry.query.filter(
        TimeEntry.client_id == client.id,
        TimeEntry.started_at >= datetime.combine(month_start, datetime.min.time()),
        TimeEntry.started_at <= datetime.combine(month_end, datetime.max.time()),
        TimeEntry.ended_at.isnot(None),
    ).all()

    total_minutes = sum(e.duration_minutes or 0 for e in entries)
    total_hours = total_minutes / 60
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
            overage_amount = round(overage_hours * rate, 2)
            line_items.append({
                "description": f"Overage hours ({overage_hours}h @ ${rate}/hr)",
                "quantity": overage_hours,
                "unit_price": rate,
                "amount": overage_amount,
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
    today = date.today()
    due_days = int(Setting.get("default_due_days") or "30")

    invoice = Invoice(
        client_id=client.id,
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
    )
    db.session.add(invoice)
    db.session.flush()

    for entry in entries:
        entry.invoice_id = invoice.id

    db.session.commit()
    log.info(f"Created invoice {invoice.invoice_number} for {client.name} {month_start.strftime('%B %Y')}")
    return invoice


def maybe_send_invoice(invoice, client, app):
    """
    Send invoice email if mode is 'send', otherwise just notify owner of draft.
    """
    from app.services.email import smtp_configured, send_email
    if not smtp_configured():
        log.warning("SMTP not configured, skipping email.")
        return

    owner_email = Setting.get("business_email")
    mode = Setting.get("auto_invoice_mode", "draft")

    # Generate PDF
    pdf_bytes = None
    pdf_filename = None
    try:
        from weasyprint import HTML
        with app.app_context():
            from flask import render_template
            html = render_template("invoices/print.html", invoice=invoice, pdf_mode=True)
        pdf_bytes = HTML(string=html).write_pdf()
        pdf_filename = f"invoice-{invoice.invoice_number}.pdf"
    except Exception as e:
        log.error(f"PDF generation failed: {e}")

    if mode == "send" and client.contact_email:
        # Auto-send to client, CC owner
        subject = f"Invoice {invoice.invoice_number} from {Setting.get('business_name')}"
        body = (
            f"Hi {client.contact_name or client.name},\n\n"
            f"Please find attached invoice {invoice.invoice_number} "
            f"for {invoice.period_start.strftime('%B %Y')}.\n\n"
            f"Amount due: ${invoice.total}\n"
            f"Due date: {invoice.due_date.strftime('%B %d, %Y')}\n\n"
            f"Thank you for your business.\n\n"
            f"{Setting.get('business_name')}"
        )
        send_email(
            to_addresses=client.contact_email,
            subject=subject,
            body=body,
            cc_addresses=owner_email if owner_email else None,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
        )
        invoice.status = "sent"
        db.session.commit()
        log.info(f"Sent invoice {invoice.invoice_number} to {client.contact_email}")
    else:
        # Draft mode — notify owner
        if owner_email:
            subject = f"Invoice {invoice.invoice_number} ready for review — {client.name}"
            body = (
                f"A draft invoice has been generated for {client.name}.\n\n"
                f"Invoice: {invoice.invoice_number}\n"
                f"Period: {invoice.period_start.strftime('%B %Y')}\n"
                f"Amount: ${invoice.total}\n\n"
                f"Review and send it from your Punch dashboard."
            )
            send_email(
                to_addresses=owner_email,
                subject=subject,
                body=body,
                pdf_bytes=pdf_bytes,
                pdf_filename=pdf_filename,
            )
        log.info(f"Draft invoice {invoice.invoice_number} created, owner notified.")


def run_auto_invoicing(app):
    """
    Main entry point for the scheduler.
    Checks for missed months and generates invoices for all auto_invoice clients.
    """
    with app.app_context():
        today = date.today()

        # Determine which months need processing
        last_run_str = Setting.get("auto_invoice_last_run", "")
        if last_run_str:
            last_run = date.fromisoformat(last_run_str)
        else:
            # First run — only process the previous month
            last_run = date(today.year, today.month, 1) - timedelta(days=1)

        # Build list of (year, month) tuples that need invoicing
        months_to_process = []
        cursor = date(last_run.year, last_run.month, 1)
        while True:
            # Advance to next month
            if cursor.month == 12:
                cursor = date(cursor.year + 1, 1, 1)
            else:
                cursor = date(cursor.year, cursor.month + 1, 1)
            # Don't invoice the current month — it's not over yet
            if cursor >= date(today.year, today.month, 1):
                break
            months_to_process.append((cursor.year, cursor.month))

        if not months_to_process:
            log.info("Auto-invoicing: nothing to process.")
            Setting.set("auto_invoice_last_run", today.isoformat())
            db.session.commit()
            return

        clients = Client.query.filter_by(is_active=True, auto_invoice=True).all()
        if not clients:
            log.info("Auto-invoicing: no clients with auto_invoice enabled.")
            Setting.set("auto_invoice_last_run", today.isoformat())
            db.session.commit()
            return

        for year, month in months_to_process:
            for client in clients:
                invoice = generate_monthly_invoice(client, year, month)
                if invoice:
                    maybe_send_invoice(invoice, client, app)

        Setting.set("auto_invoice_last_run", today.isoformat())
        db.session.commit()
        log.info(f"Auto-invoicing complete. Processed {len(months_to_process)} month(s) for {len(clients)} client(s).")