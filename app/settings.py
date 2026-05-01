"""
Settings are stored as key-value pairs in the database.
This lets users configure business details through the UI
rather than editing the .env file.
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
        # Caller is responsible for commit

    @staticmethod
    def all_as_dict():
        rows = Setting.query.all()
        return {r.key: r.value for r in rows}


# Keys and their human-readable labels, in display order
SETTING_FIELDS = [
    # (key, label, input_type, placeholder)
    ("business_name",         "Business / your name",     "text",  "Acme Consulting"),
    ("business_address",      "Street address",            "text",  "123 Main Street"),
    ("business_city_state_zip","City, state, zip",         "text",  "Springfield, MA 01101"),
    ("business_email",        "Email",                     "email", "you@example.com"),
    ("business_phone",        "Phone",                     "text",  "413-555-1234"),
    ("invoice_start_number",  "Invoice starting number",   "number","1001"),
    ("default_due_days",      "Default payment terms (days)","number","30"),
    ("timezone",              "Timezone",                  "text",  "America/New_York"),
]


def get_business():
    """Return a dict of business settings for use in templates."""
    return {
        "name":           Setting.get("business_name"),
        "address":        Setting.get("business_address"),
        "city_state_zip": Setting.get("business_city_state_zip"),
        "email":          Setting.get("business_email"),
        "phone":          Setting.get("business_phone"),
    }
