from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
import math


class User(UserMixin, db.Model):
    """Single user for the app. Multi-user is supported by the schema
    but Punch is primarily designed for solo freelancers."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Client(db.Model):
    """A client. Can be a retainer client (fixed monthly rate) or
    a standard hourly client."""
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    contact_name = db.Column(db.String(128))
    contact_email = db.Column(db.String(128))
    billing_mode = db.Column(db.String(16), nullable=False, default="hourly")
    # billing_mode: "retainer" or "hourly"

    # Retainer settings
    retainer_amount = db.Column(db.Numeric(10, 2))      # Fixed monthly fee
    retainer_hours = db.Column(db.Numeric(6, 2))         # Included hours (soft cap)
    overage_rate = db.Column(db.Numeric(10, 2))          # Hourly rate above cap

    # Hourly settings (also used for overage on retainer clients)
    hourly_rate = db.Column(db.Numeric(10, 2))
    address = db.Column(db.Text)
    phone = db.Column(db.String(32))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    auto_invoice = db.Column(db.Boolean, default=False)

    # Per-client invoice email overrides. If set, these take priority over the
    # global default in Settings. Leave blank to fall back to the global default.
    # Supports template variables: {invoice_number}, {business_name}, {client_name},
    # {contact_name}, {amount}, {due_date}, {period}
    invoice_email_subject = db.Column(db.Text)
    invoice_email_body = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    time_entries = db.relationship("TimeEntry", back_populates="client", lazy="dynamic")
    invoices = db.relationship("Invoice", back_populates="client", lazy="dynamic")

    def __repr__(self):
        return f"<Client {self.name}>"


class TimeEntry(db.Model):
    """A single logged block of work."""
    __tablename__ = "time_entries"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=True)

    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Duration stored in minutes, rounded to 15-min blocks
    duration_minutes = db.Column(db.Integer)

    description = db.Column(db.Text)
    is_billable = db.Column(db.Boolean, default=True)

    # For retainer clients: was this entry counted as overage?
    is_overage = db.Column(db.Boolean, default=False)

    # Import tracking
    imported_from = db.Column(db.String(64))  # e.g. "harvest"
    external_id = db.Column(db.String(64))    # original ID from import source

    # Set when a "you have a long-running timer" reminder email is sent.
    # NULL = no reminder sent yet. Prevents repeated nagging for the same entry.
    long_running_notified_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    client = db.relationship("Client", back_populates="time_entries")
    invoice = db.relationship("Invoice", back_populates="time_entries")

    @property
    def is_running(self):
        return self.ended_at is None

    @property
    def duration_hours(self):
        if self.duration_minutes is None:
            return 0
        return self.duration_minutes / 60

    @property
    def duration_display(self):
        """Human-friendly duration string, e.g. '1h 30m'"""
        if self.duration_minutes is None:
            return "running"
        h = self.duration_minutes // 60
        m = self.duration_minutes % 60
        if h and m:
            return f"{h}h {m}m"
        elif h:
            return f"{h}h"
        else:
            return f"{m}m"

    @staticmethod
    def round_to_15(minutes):
        """Round a raw minute count up to the nearest 15-minute block."""
        return math.ceil(minutes / 15) * 15

    def stop_timer(self):
        """Stop the running timer and compute rounded duration."""
        if self.ended_at is None:
            now = datetime.utcnow()
            self.ended_at = now
            started = self.started_at.replace(tzinfo=None) if self.started_at.tzinfo else self.started_at
            raw = (self.ended_at - started).total_seconds() / 60
            self.duration_minutes = TimeEntry.round_to_15(raw)

    def __repr__(self):
        return f"<TimeEntry {self.id} client={self.client_id} {self.duration_display}>"


class Invoice(db.Model):
    """An invoice. Can be a monthly retainer invoice or a manual/project invoice."""
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)

    invoice_number = db.Column(db.String(32), unique=True, nullable=False)
    invoice_type = db.Column(db.String(16), default="monthly")
    # invoice_type: "monthly" or "project"

    # Billing period
    period_start = db.Column(db.Date)
    period_end = db.Column(db.Date)

    # Line items stored as JSON list of dicts:
    # [{"description": "...", "quantity": 1, "unit_price": 500.00, "amount": 500.00}]
    line_items = db.Column(db.JSON, default=list)

    subtotal = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)

    status = db.Column(db.String(16), default="draft")
    # status: "draft", "sent", "paid"

    issued_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    paid_date = db.Column(db.Date)

    show_time_detail = db.Column(db.Boolean, default=False)

    notes = db.Column(db.Text)

    # Import tracking
    imported_from = db.Column(db.String(64))
    external_id = db.Column(db.String(64))

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    client = db.relationship("Client", back_populates="invoices")
    time_entries = db.relationship("TimeEntry", back_populates="invoice")

    def __repr__(self):
        return f"<Invoice {self.invoice_number} {self.status}>"


class AuditLog(db.Model):
    """A timestamped record of an auditable event in Punch.

    Events are written via app.services.audit.log_event() which is called from
    routes / services. Records are append-only from the app's perspective
    (no edit UI), but can be pruned by the retention job in scheduler.py.
    """
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, index=True,
                          default=lambda: datetime.now(timezone.utc))

    # Short dotted identifier, e.g. 'invoice.sent', 'time_entry.created'
    event_type = db.Column(db.String(64), nullable=False, index=True)

    # Human-readable description for display in the audit log UI
    description = db.Column(db.Text, nullable=False)

    # Optional reference to the affected record
    entity_type = db.Column(db.String(32))   # e.g. 'invoice', 'client', 'time_entry'
    entity_id = db.Column(db.Integer)

    # Who did it (null = system event, e.g. scheduler)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    # Event-specific structured data (recipients, before/after values, etc.)
    meta = db.Column(db.JSON)

    user = db.relationship("User")

    def __repr__(self):
        return f"<AuditLog {self.event_type} @ {self.timestamp.isoformat()}>"
