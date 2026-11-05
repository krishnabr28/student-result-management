import mysql.connector
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .auth import hash_password, roles_required
from .db import execute_query, fetch_all, fetch_one
from .rules import ValidationError, check_password, clean_person_name, clean_username

bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_only = roles_required("admin")
STAFF_ROLES = {"faculty": "Faculty", "admin": "Administrator"}


def _staff():
    return fetch_all(
        "SELECT u.id, u.username, u.full_name, u.role, u.is_active, u.created_at,"
        " (SELECT COUNT(*) FROM results r WHERE r.entered_by = u.id) AS results_entered"
        " FROM users u WHERE u.role IN ('faculty', 'admin') ORDER BY u.role, u.full_name"
    )


def _get_staff(user_id):
    user = fetch_one(
        "SELECT id, username, full_name, role, is_active FROM users WHERE id = %s AND role IN ('faculty', 'admin')",
        (user_id,),
    )
    if user is None:
        abort(404)
    return user


@bp.route("/users", methods=["GET", "POST"])
@admin_only
def users():
    form, status = {}, 200
    if request.method == "POST":
        form = request.form
        try:
            username = clean_username(form.get("username"))
            full_name = clean_person_name(form.get("full_name"), "Full name")
            role = form.get("role")
            if role not in STAFF_ROLES:
                raise ValidationError("Choose a valid role.")
            password = check_password(form.get("password"), form.get("confirm_password") or "")
            if fetch_one("SELECT id FROM users WHERE username = %s", (username,)):
                raise ValidationError(f"Username {username} is already taken.")
            execute_query(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (%s, %s, %s, %s)",
                (username, hash_password(password), full_name, role),
            )
        except ValidationError as exc:
            flash(str(exc), "error")
            status = 400
        except mysql.connector.IntegrityError:
            flash("That username is already taken.", "error")
            status = 409
        else:
            flash(f"{STAFF_ROLES[role]} account '{username}' created.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/users.html", staff=_staff(), form=form, roles=STAFF_ROLES), status


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_only
def toggle_active(user_id):
    user = _get_staff(user_id)
    if user["id"] == g.user["id"]:
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin.users"))
    execute_query("UPDATE users SET is_active = NOT is_active WHERE id = %s", (user_id,))
    flash(f"Account '{user['username']}' {'deactivated' if user['is_active'] else 'activated'}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/password", methods=["POST"])
@admin_only
def reset_password(user_id):
    user = _get_staff(user_id)
    try:
        password = check_password(request.form.get("password"), request.form.get("confirm_password") or "")
    except ValidationError as exc:
        flash(f"Password not changed for '{user['username']}': {exc}", "error")
        return redirect(url_for("admin.users"))
    execute_query("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(password), user_id))
    flash(f"Password reset for '{user['username']}'.", "success")
    return redirect(url_for("admin.users"))
