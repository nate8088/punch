"""
Email sending service for Punch.
Handles SMTP connection and optional PDF attachment.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr
from app.settings import Setting


def get_smtp_settings():
    return {
        "host":     Setting.get("smtp_host"),
        "port":     int(Setting.get("smtp_port", "587")),
        "username": Setting.get("smtp_username"),
        "password": Setting.get("smtp_password"),
        "from":     Setting.get("smtp_from"),
    }


def smtp_configured():
    s = get_smtp_settings()
    return all([s["host"], s["username"], s["password"], s["from"]])


def send_email(to_addresses, subject, body, cc_addresses=None, pdf_bytes=None, pdf_filename=None):
    """
    Send an email via SMTP.
    to_addresses: list of strings or single string
    cc_addresses: list of strings or None
    pdf_bytes: raw PDF bytes to attach, or None
    """
    s = get_smtp_settings()
    business_name = Setting.get("business_name") or ""

    if isinstance(to_addresses, str):
        to_addresses = [to_addresses]
    if isinstance(cc_addresses, str):
        cc_addresses = [cc_addresses]

    msg = MIMEMultipart()
    msg["From"] = formataddr((business_name, s["from"])) if business_name else s["from"]
    msg["To"] = ", ".join(to_addresses)
    msg["Subject"] = subject
    if cc_addresses:
        msg["Cc"] = ", ".join(cc_addresses)

    msg.attach(MIMEText(body, "plain"))

    if pdf_bytes and pdf_filename:
        part = MIMEApplication(pdf_bytes, Name=pdf_filename)
        part["Content-Disposition"] = f'attachment; filename="{pdf_filename}"'
        msg.attach(part)

    all_recipients = to_addresses + (cc_addresses or [])

    context = ssl.create_default_context()
    with smtplib.SMTP(s["host"], s["port"]) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(s["username"], s["password"])
        server.sendmail(s["from"], all_recipients, msg.as_string())


def build_invoice_email(invoice):
    """
    Build the subject and body for an invoice email.

    Priority order for subject and body:
      1. Per-client override (client.invoice_email_subject / invoice_email_body)
      2. Global default from Settings (invoice_email_subject / invoice_email_body)
      3. Hardcoded fallback (original behavior — unchanged)

    Template variables available in custom subject/body strings:
      {invoice_number}, {business_name}, {client_name}, {contact_name},
      {amount}, {due_date}, {period}

    Returns a dict: {"subject": str, "body": str}
    Used by both auto-invoicing and the manual send flow so copy stays consistent.
    """
    business_name = Setting.get("business_name") or "Punch"
    client = invoice.client

    period_label = invoice.period_start.strftime("%B %Y") if invoice.period_start else ""
    greeting_name = client.contact_name or client.name
    due_str = invoice.due_date.strftime("%B %d, %Y") if invoice.due_date else ""

    # Variables available for substitution in custom templates
    template_vars = {
        "invoice_number": invoice.invoice_number,
        "business_name":  business_name,
        "client_name":    client.name,
        "contact_name":   greeting_name,
        "amount":         invoice.total,
        "due_date":       due_str,
        "period":         period_label,
    }

    # ── Subject ──────────────────────────────────────────────────────────────
    subject_tmpl = (
        (client.invoice_email_subject or "").strip()
        or Setting.get("invoice_email_subject", "").strip()
        or "Invoice {invoice_number} from {business_name}"
    )
    try:
        subject = subject_tmpl.format_map(template_vars)
    except (KeyError, ValueError):
        subject = subject_tmpl

    # ── Body ─────────────────────────────────────────────────────────────────
    custom_body_tmpl = (
        (client.invoice_email_body or "").strip()
        or Setting.get("invoice_email_body", "").strip()
    )

    if custom_body_tmpl:
        try:
            body = custom_body_tmpl.format_map(template_vars)
        except (KeyError, ValueError):
            body = custom_body_tmpl
    else:
        # Hardcoded fallback — original behavior preserved exactly
        period_line = f"for {period_label}" if period_label else ""
        due_line = f"Due date: {due_str}\n" if due_str else ""
        body = (
            f"Hi {greeting_name},\n\n"
            f"Please find attached invoice {invoice.invoice_number}"
            f"{(' ' + period_line) if period_line else ''}.\n\n"
            f"Amount due: ${invoice.total}\n"
            f"{due_line}"
            f"\nThank you for your business.\n\n"
            f"{business_name}"
        )

    return {"subject": subject, "body": body}
