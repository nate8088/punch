from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from datetime import datetime, timezone, date, timedelta
from app import db
from app.models import TimeEntry, Client
import math

time_bp = Blueprint("time", __name__, url_prefix="/time")


def parse_local_datetime(dt_string):
    """Parse a datetime-local input value as naive UTC."""
    if not dt_string:
        return None
    return datetime.strptime(dt_string, "%Y-%m-%dT%H:%M")


@time_bp.route("/")
@login_required
def index():
    """Recent time entries across all clients."""
    page = request.args.get("page", 1, type=int)
    entries = TimeEntry.query.order_by(
        TimeEntry.started_at.desc()
    ).paginate(page=page, per_page=50)
    clients = Client.query.filter_by(is_active=True).order_by(Client.name).all()
    return render_template("time/index.html", entries=entries, clients=clients)


@time_bp.route("/punch")
@login_required
def punch():
    """The mobile-friendly punch in/out screen."""
    clients = Client.query.filter_by(is_active=True).order_by(Client.name).all()
    running = TimeEntry.query.filter_by(ended_at=None).first()
    return render_template("time/punch.html", clients=clients, running=running)


@time_bp.route("/punch/in", methods=["POST"])
@login_required
def punch_in():
    client_id = request.form.get("client_id", type=int)
    if not client_id:
        flash("Please select a client.", "error")
        return redirect(url_for("time.punch"))

    # Don't allow two running timers
    existing = TimeEntry.query.filter_by(ended_at=None).first()
    if existing:
        flash("A timer is already running. Punch out first.", "error")
        return redirect(url_for("time.punch"))

    entry = TimeEntry(
        client_id=client_id,
        started_at=datetime.utcnow(),
        is_billable=True,
    )
    db.session.add(entry)
    db.session.commit()
    return redirect(url_for("time.punch"))


@time_bp.route("/punch/out", methods=["POST"])
@login_required
def punch_out():
    entry = TimeEntry.query.filter_by(ended_at=None).first()
    if not entry:
        flash("No timer is running.", "error")
        return redirect(url_for("time.punch"))

    entry.stop_timer()
    db.session.commit()
    flash(f"Punched out. {entry.duration_display} logged.", "success")
    return redirect(url_for("time.edit", entry_id=entry.id))


@time_bp.route("/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit(entry_id):
    entry = db.get_or_404(TimeEntry, entry_id)
    clients = Client.query.filter_by(is_active=True).order_by(Client.name).all()

    if request.method == "POST":
        entry.description = request.form.get("description", "").strip()
        entry.is_billable = request.form.get("is_billable") == "on"

        # Prefer UTC-converted values from JS; fall back to raw inputs
        started_str = request.form.get("started_at_utc") or request.form.get("started_at")
        ended_str = request.form.get("ended_at_utc") or request.form.get("ended_at")
        manual_duration = request.form.get("duration_minutes")

        if started_str:
            entry.started_at = parse_local_datetime(started_str)
        if ended_str:
            entry.ended_at = parse_local_datetime(ended_str)
        else:
            entry.ended_at = None

        # Manual duration wins if explicitly provided
        if manual_duration:
            try:
                entry.duration_minutes = TimeEntry.round_to_15(int(manual_duration))
            except ValueError:
                pass
        elif entry.started_at and entry.ended_at:
            # Fall back to calculating from timestamps
            started = entry.started_at.replace(tzinfo=None) if entry.started_at.tzinfo else entry.started_at
            ended = entry.ended_at.replace(tzinfo=None) if entry.ended_at.tzinfo else entry.ended_at
            raw = (ended - started).total_seconds() / 60
            entry.duration_minutes = TimeEntry.round_to_15(max(0, raw))

        client_id = request.form.get("client_id", type=int)
        if client_id:
            entry.client_id = client_id

        db.session.commit()
        flash("Time entry updated.", "success")
        return redirect(url_for("clients.detail", client_id=entry.client_id))

    return render_template("time/edit.html", entry=entry, clients=clients)


@time_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    """Manually create a time entry (for non-timer clients or back-entry)."""
    clients = Client.query.filter_by(is_active=True).order_by(Client.name).all()
    preselect_client = request.args.get("client_id", type=int)

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        started_str = request.form.get("started_at_utc") or request.form.get("started_at")
        ended_str = request.form.get("ended_at_utc") or request.form.get("ended_at")
        description = request.form.get("description", "").strip()
        is_billable = request.form.get("is_billable") == "on"

        if not client_id or not started_str:
            flash("Client and start time are required.", "error")
        else:
            started_at = parse_local_datetime(started_str)
            ended_at = parse_local_datetime(ended_str) if ended_str else None

            duration_minutes = None
            if started_at and ended_at:
                raw = (ended_at - started_at).total_seconds() / 60
                duration_minutes = TimeEntry.round_to_15(max(0, raw))

            # Allow direct hour entry if no end time
            manual = request.form.get("duration_hours")
            if manual and not ended_at:
                try:
                    duration_minutes = TimeEntry.round_to_15(float(manual) * 60)
                    ended_at = started_at + timedelta(minutes=duration_minutes)
                except ValueError:
                    pass

            entry = TimeEntry(
                client_id=client_id,
                started_at=started_at,
                ended_at=ended_at,
                duration_minutes=duration_minutes,
                description=description,
                is_billable=is_billable,
            )
            db.session.add(entry)
            db.session.commit()
            flash("Time entry added.", "success")
            return redirect(url_for("clients.detail", client_id=client_id))

    # Send UTC ISO so JS can convert to local for the input
    now_utc = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return render_template("time/new.html", clients=clients, preselect_client=preselect_client, now_utc=now_utc)


@time_bp.route("/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete(entry_id):
    entry = db.get_or_404(TimeEntry, entry_id)
    client_id = entry.client_id
    db.session.delete(entry)
    db.session.commit()
    flash("Time entry deleted.", "success")
    return redirect(url_for("clients.detail", client_id=client_id))


@time_bp.route("/status")
@login_required
def status():
    """JSON endpoint for the punch screen timer display."""
    running = TimeEntry.query.filter_by(ended_at=None).first()
    if running:
        started = running.started_at.replace(tzinfo=None) if running.started_at.tzinfo else running.started_at
        elapsed = (datetime.utcnow() - started).total_seconds()
        return jsonify({
            "running": True,
            "entry_id": running.id,
            "client_name": running.client.name,
            "elapsed_seconds": int(elapsed),
            "started_at": running.started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return jsonify({"running": False})