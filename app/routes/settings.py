from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app import db
from app.settings import Setting, SETTING_FIELDS, SMTP_FIELDS, TIMER_ALERT_FIELDS, EMAIL_TEMPLATE_KEYS
from app.services.audit import log_event

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

ALL_KEYS = (
    [key for key, *_ in SETTING_FIELDS] +
    [key for key, *_ in SMTP_FIELDS] +
    [key for key, *_ in TIMER_ALERT_FIELDS] +
    EMAIL_TEMPLATE_KEYS +
    ["auto_invoice_mode"]
)

# Password-type SMTP fields — skip on save when empty so we don't
# wipe stored credentials every time the user saves other settings.
PASSWORD_KEYS = {key for key, _label, input_type, *_ in SMTP_FIELDS if input_type == "password"}


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        for key in ALL_KEYS:
            value = request.form.get(key)
            if value is None:
                continue
            value = value.strip()
            # Don't overwrite a stored password with an empty submission —
            # password fields are intentionally rendered blank in the form.
            if key in PASSWORD_KEYS and value == "":
                continue
            Setting.set(key, value)
        # Intentionally vague: don't log specific values (e.g. SMTP creds).
        log_event("settings.updated", "Settings updated.")
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("settings.index"))

    current = Setting.all_as_dict()
    return render_template(
        "settings.html",
        fields=SETTING_FIELDS,
        smtp_fields=SMTP_FIELDS,
        timer_alert_fields=TIMER_ALERT_FIELDS,
        current=current,
    )


@settings_bp.route("/test-email", methods=["POST"])
@login_required
def test_email():
    from app.services.email import smtp_configured, send_email
    if not smtp_configured():
        flash("SMTP is not fully configured. Fill in all email settings first.", "error")
        return redirect(url_for("settings.index"))

    owner_email = Setting.get("business_email")
    if not owner_email:
        flash("No business email set. Add one in Business Details first.", "error")
        return redirect(url_for("settings.index"))

    try:
        send_email(
            to_addresses=owner_email,
            subject="Punch — test email",
            body="This is a test email from Punch. Your SMTP settings are working correctly.",
        )
        log_event(
            "email.test_sent",
            f"Test email sent to {owner_email}.",
            meta={"to": owner_email},
        )
        db.session.commit()
        flash(f"Test email sent to {owner_email}.", "success")
    except Exception as e:
        log_event(
            "email.test_failed",
            f"Test email failed: {e}",
            meta={"to": owner_email, "error": str(e)},
        )
        db.session.commit()
        flash(f"Email failed: {e}", "error")

    return redirect(url_for("settings.index"))
