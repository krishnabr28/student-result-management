from functools import wraps
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import execute_query, fetch_one
from .demo import DEMO_ACCOUNTS
from .rules import ValidationError, check_password

bp = Blueprint("auth", __name__)

# Compared against when the username is unknown, so response time does not reveal valid usernames.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def hash_password(password):
    return generate_password_hash(password)


def load_current_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is None or request.endpoint == "static":
        return
    user = fetch_one("SELECT id, username, full_name, role FROM users WHERE id = %s AND is_active = TRUE", (user_id,))
    if user is None:
        session.clear()
        return
    g.user = user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def home_url(user):
    return url_for("student.dashboard" if user["role"] == "student" else "faculty.dashboard")


def safe_local_path(target):
    """Return target only if it is a path on this site; browsers treat '/\\' and stripped control chars as '//'."""
    if not target or not target.startswith("/") or target[1:2] in ("/", "\\"):
        return None
    if "\\" in target or any(ord(ch) < 32 or ord(ch) == 127 for ch in target):
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


@bp.route("/")
def index():
    if g.user:
        return redirect(home_url(g.user))
    return redirect(url_for("auth.login"))


def _login_page(username="", status=200):
    demo = DEMO_ACCOUNTS if current_app.config["SHOW_DEMO_ACCOUNTS"] else []
    return render_template("auth/login.html", username=username, demo_accounts=demo), status


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(home_url(g.user))
    username = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Enter both username and password.", "error")
            return _login_page(username, 400)
        user = fetch_one("SELECT id, password_hash, is_active, role FROM users WHERE username = %s", (username,))
        valid = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)
        if not user or not valid:
            flash("Invalid username or password.", "error")
            return _login_page(username, 401)
        if not user["is_active"]:
            flash("This account has been deactivated. Please contact the administrator.", "error")
            return _login_page(username, 403)
        csrf = session.get("csrf_token")
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        if csrf:
            session["csrf_token"] = csrf
        return redirect(safe_local_path(request.args.get("next")) or home_url(user))
    return _login_page(username)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        row = fetch_one("SELECT password_hash FROM users WHERE id = %s", (g.user["id"],))
        try:
            if not check_password_hash(row["password_hash"], current):
                raise ValidationError("Current password is incorrect.")
            check_password(new, confirm)
            if new == current:
                raise ValidationError("New password must be different from the current one.")
        except ValidationError as exc:
            flash(str(exc), "error")
            return render_template("auth/change_password.html"), 400
        execute_query("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new), g.user["id"]))
        flash("Password changed successfully.", "success")
        return redirect(home_url(g.user))
    return render_template("auth/change_password.html")
