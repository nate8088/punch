"""
Settings are stored as key-value pairs in the database.
"""
from app import db


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, default="")

    @staticmethod
    def get(key, default=""):
        row = db.session.get(Setting, key)
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = db.session.get(Setting, key)
        if row:
            row.value = value
        else:
            row = Setting(key=key, value=value)
            db.session.add(row)

    @staticmethod
    def all_as_dict():
        rows = Setting.query.all()
        return {r.key: r.value for r in rows}


SETTING_FIELDS = [
    # (key, label, input_type, placeholder)
    ("business_name",           "Business / your name",           "text",   "Acme Consulting"),
    ("business_address",        "Street address",                  "text",   "123 Main Street"),
    ("business_city_state_zip", "City, state, zip",                "text",   "Springfield, MA 01101"),
    ("business_email",          "Email",                           "email",  "you@example.com"),
    ("business_phone",          "Phone",                           "text",   "413-555-1234"),
    ("invoice_start_number",    "Invoice starting number",         "number", "1001"),
    ("default_due_days",        "Default payment terms (days)",    "number", "30"),
    ("timezone",                "Timezone",                        "text",   "America/New_York"),
]

SMTP_FIELDS = [
    ("smtp_host",     "SMTP host",         "text",   "smtp.gmail.com"),
    ("smtp_port",     "SMTP port",         "number", "587"),
    ("smtp_username", "SMTP username",     "email",  "you@gmail.com"),
    ("smtp_password", "SMTP password",     "password", ""),
    ("smtp_from",     "From address",      "email",  "you@gmail.com"),
]


def get_business():
    return {
        "name":           Setting.get("business_name"),
        "address":        Setting.get("business_address"),
        "city_state_zip": Setting.get("business_city_state_zip"),
        "email":          Setting.get("business_email"),
        "phone":          Setting.get("business_phone"),
    }