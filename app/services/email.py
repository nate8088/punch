"""
Email sending service for Punch.
Handles SMTP connection and optional PDF attachment.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
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

    if isinstance(to_addresses, str):
        to_addresses = [to_addresses]
    if isinstance(cc_addresses, str):
        cc_addresses = [cc_addresses]

    msg = MIMEMultipart()
    msg["From"] = s["from"]
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