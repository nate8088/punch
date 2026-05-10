from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from app.services.audit import log_event

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    # First-run: no users exist yet
    if User.query.count() == 0:
        return redirect(url_for("auth.setup"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            log_event(
                "auth.login_success",
                f"User '{user.username}' logged in.",
                entity_type="user",
                entity_id=user.id,
                user_id=user.id,  # explicit because current_user wasn't set when log_event was called
            )
            db.session.commit()
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.index"))
        else:
            log_event(
                "auth.login_failure",
                f"Failed login attempt for username '{username}'.",
                meta={"username_attempted": username},
            )
            db.session.commit()
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First-run setup: create the initial user account."""
    if User.query.count() > 0:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # so user.id is available for the audit row
            log_event(
                "auth.account_created",
                f"Initial account '{user.username}' created.",
                entity_type="user",
                entity_id=user.id,
                user_id=user.id,
            )
            db.session.commit()
            login_user(user)
            flash("Account created. Fill in your business details to get started.", "success")
            return redirect(url_for("settings.index"))

    return render_template("setup.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_event(
        "auth.logout",
        f"User '{current_user.username}' logged out.",
        entity_type="user",
        entity_id=current_user.id,
    )
    db.session.commit()
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if not current_user.check_password(current_pw):
            flash("Current password is incorrect.", "error")
        elif new_pw != confirm:
            flash("New passwords do not match.", "error")
        elif len(new_pw) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            current_user.set_password(new_pw)
            log_event(
                "auth.password_changed",
                f"User '{current_user.username}' changed their password.",
                entity_type="user",
                entity_id=current_user.id,
            )
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(url_for("dashboard.index"))

    return render_template("change_password.html")
