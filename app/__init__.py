"""Flask application factory with security hardening."""
import os
from flask import Flask, request, redirect, url_for, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import config as app_config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(user_id)


login_manager.login_view = "auth.login"
login_manager.session_protection = "strong"


def create_app():
    app = Flask(__name__)
    app.config.update(app_config.CONFIG)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from app.auth import auth_bp
    from app.views import views_bp
    from app.admin import admin_bp
    from app.hrms import hrms_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(views_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(hrms_bp)

    @app.before_request
    def enforce_password_change():
        # Force first-login password change for every authenticated user.
        if current_user.is_authenticated:
            allowed = {"auth.change_password", "auth.logout", "static"}
            if current_user.must_change_password and request.endpoint not in allowed:
                return redirect(url_for("auth.change_password"))
            g.user = current_user

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Conservative CSP: same-origin only, no inline scripts needed by templates.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; frame-ancestors 'none'"
        )
        return response

    @app.context_processor
    def inject_globals():
        return {
            "company_name": app_config.COMPANY_NAME,
            "trade_name": app_config.TRADE_NAME,
        }

    with app.app_context():
        db.create_all()
        # Lightweight idempotent migration for columns added after the
        # original schema was created (e.g. v2.1 UAE fields). create_all()
        # does not add columns to existing tables, so upgrade them here.
        try:
            from sqlalchemy import inspect, text
            cols = {c["name"] for c in inspect(db.engine).get_columns("users")}
            for col, ddl in [
                ("emirates_id_expiry_date", "DATE"),
                ("iban", "VARCHAR(60)"),
                ("bank_name", "VARCHAR(80)"),
            ]:
                if col not in cols:
                    db.session.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))
            db.session.commit()
        except Exception:
            app.logger.exception("Column migration failed")
            db.session.rollback()
        # Free-sample mode only: auto-create fake demo users on startup
        # (hosts like Render free have no shell to run seed_demo.py).
        if os.environ.get("ESS_SEED_DEMO") == "1":
            try:
                from app.demo_seed import ensure_demo_users
                ensure_demo_users()
            except Exception:
                app.logger.exception("Demo seed failed")

    return app
