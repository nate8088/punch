from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app import db
from app.settings import Setting, SETTING_FIELDS

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        for key, *_ in SETTING_FIELDS:
            value = request.form.get(key, "").strip()
            Setting.set(key, value)
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("settings.index"))

    current = Setting.all_as_dict()
    return render_template("settings.html", fields=SETTING_FIELDS, current=current)
