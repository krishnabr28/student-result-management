import hmac
import secrets
from datetime import datetime, timezone

import mysql.connector
from flask import Flask, abort, g, render_template, request, session

from .config import load_config
from .db import DatabaseUnavailable, close_connection
from .rules import format_number


def _local(value):
    """MySQL sessions run in UTC (see db.py); show times in the server's local zone."""
    return value.replace(tzinfo=timezone.utc).astimezone()


def format_datetime(value):
    if value is None:
        return ""
    return _local(value).strftime("%d %b %Y, %I:%M %p")


def time_ago(value):
    if value is None:
        return ""
    seconds = int((datetime.now(timezone.utc) - value.replace(tzinfo=timezone.utc)).total_seconds())
    if seconds < 60:
        return "just now"
    for size, unit in ((86400 * 30, "month"), (86400, "day"), (3600, "hour"), (60, "minute")):
        if seconds >= size:
            n = seconds // size
            if unit == "month" and n > 11:
                break
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    return _local(value).strftime("%d %b %Y")


def _csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def _check_csrf():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
        abort(400, description="Your session expired or the form was submitted twice. Please try again.")


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.update(load_config())
    if config_overrides:
        app.config.update(config_overrides)

    from . import admin, auth, faculty, notifications, student

    app.register_blueprint(auth.bp)
    app.register_blueprint(faculty.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(student.bp)
    app.register_blueprint(notifications.bp)

    app.add_template_filter(format_number, "num")
    app.add_template_filter(format_datetime, "datetime")
    app.add_template_filter(time_ago, "ago")
    app.teardown_appcontext(close_connection)
    app.before_request(_check_csrf)
    app.before_request(auth.load_current_user)

    @app.context_processor
    def inject_globals():
        user = g.get("user")
        unread = notifications.unread_count(user) if user else 0
        return {"current_user": user, "csrf_token": _csrf_token, "unread_count": unread}

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "frame-ancestors 'none'; form-action 'self'; base-uri 'self'",
        )
        if g.get("user"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    from .auth import safe_local_path

    app.add_template_global(safe_local_path)

    def _error(code, title, message):
        if request.path.startswith("/api/"):
            return {"error": message}, code
        return render_template("errors/error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(err):
        return _error(400, "Request could not be processed", err.description)

    @app.errorhandler(403)
    def forbidden(_err):
        return _error(403, "Access denied", "Your account does not have permission to open this page.")

    @app.errorhandler(404)
    def not_found(_err):
        return _error(404, "Page not found", "The page or record you are looking for does not exist.")

    @app.errorhandler(DatabaseUnavailable)
    @app.errorhandler(mysql.connector.errors.InterfaceError)
    @app.errorhandler(mysql.connector.errors.OperationalError)
    def database_down(err):
        app.logger.error("Database unavailable: %s", err)
        g.pop("db", None)
        g.pop("user", None)
        return _error(
            503,
            "Database not reachable",
            "The application cannot connect to MySQL. Check that the MySQL server is running "
            "and the settings in .env are correct, then reload this page.",
        )

    @app.errorhandler(500)
    def server_error(_err):
        return _error(500, "Something went wrong", "An unexpected error occurred. Please try again.")

    return app
