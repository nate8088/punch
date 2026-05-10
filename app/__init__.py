import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate, upgrade as migrate_upgrade
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

log = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["SCHEDULER_API_ENABLED"] = False

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access Punch."

    from app.routes.auth import auth_bp
    from app.routes.clients import clients_bp
    from app.routes.time_entries import time_bp
    from app.routes.invoices import invoices_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.settings import settings_bp
    from app.routes.reports import reports_bp
    from app.routes.audit import audit_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(time_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(audit_bp)

    @app.context_processor
    def inject_business():
        from app.settings import get_business
        return {"business": get_business()}

    # Run any pending Alembic migrations on startup. This replaces the old
    # db.create_all() call: on a fresh install it builds the schema from
    # 0001 forward; on an existing install it applies any new migrations
    # since the last boot. Failures here halt startup loudly rather than
    # being silently papered over (which is what create_all() did).
    # Skipped when FLASK_SKIP_MIGRATE=1 so CLI tools like `flask db ...`
    # can run without recursion.
    if os.environ.get("FLASK_SKIP_MIGRATE") != "1":
        with app.app_context():
            try:
                migrate_upgrade()
            except Exception as e:
                log.exception("Alembic upgrade failed at startup: %s", e)
                raise

    # Start scheduler (skip in migration/CLI contexts)
    if os.environ.get("FLASK_SKIP_SCHEDULER") != "1":
        from app.scheduler import init_scheduler
        init_scheduler(app)

    return app
