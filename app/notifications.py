from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .auth import login_required, roles_required, safe_local_path
from .db import execute_query, fetch_all, fetch_one, transaction
from .rules import ValidationError, clean_text

bp = Blueprint("notifications", __name__)

CATEGORIES = {
    "result": "Result",
    "announcement": "Announcement",
    "notice": "Notice",
    "exam": "Examination",
}
POSTABLE_CATEGORIES = ("announcement", "notice", "exam")
AUDIENCES = {"all": "Everyone", "students": "All students", "faculty": "Faculty only"}

# A notification is visible to a user when it is broadcast to their group or targeted at them.
_VISIBLE = (
    "(n.audience = 'all'"
    " OR (n.audience = 'students' AND %(role)s = 'student')"
    " OR (n.audience = 'faculty' AND %(role)s IN ('faculty', 'admin'))"
    " OR (n.audience = 'user' AND n.target_user_id = %(uid)s))"
)


def _params(user, **extra):
    return {"role": user["role"], "uid": user["id"], **extra}


def create_notification(
    cursor, *, title, message, category, audience, created_by, target_user_id=None, priority="normal"
):
    if (audience == "user") != (target_user_id is not None):
        raise ValueError("target_user_id is required exactly when audience is 'user'")
    cursor.execute(
        "INSERT INTO notifications (title, message, category, priority, audience, target_user_id, created_by)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (title, message, category, priority, audience, target_user_id, created_by),
    )


def unread_count(user):
    row = fetch_one(
        "SELECT COUNT(*) AS c FROM notifications n"
        " LEFT JOIN notification_reads r ON r.notification_id = n.id AND r.user_id = %(uid)s"
        f" WHERE r.notification_id IS NULL AND {_VISIBLE}",
        _params(user),
    )
    return row["c"]


def visible_notifications(user, *, unread_only=False, category=None, limit=200):
    where = [_VISIBLE]
    if unread_only:
        where.append("r.notification_id IS NULL")
    if category:
        where.append("n.category = %(category)s")
    return fetch_all(
        "SELECT n.id, n.title, n.message, n.category, n.priority, n.created_at,"
        " u.full_name AS author, r.read_at"
        " FROM notifications n"
        " LEFT JOIN notification_reads r ON r.notification_id = n.id AND r.user_id = %(uid)s"
        " LEFT JOIN users u ON u.id = n.created_by"
        f" WHERE {' AND '.join(where)}"
        " ORDER BY n.created_at DESC, n.id DESC LIMIT %(limit)s",
        _params(user, category=category, limit=limit),
    )


def _get_visible(notification_id):
    row = fetch_one(
        "SELECT n.id, n.title, n.message, n.category, n.priority, n.created_at,"
        " u.full_name AS author, r.read_at"
        " FROM notifications n"
        " LEFT JOIN notification_reads r ON r.notification_id = n.id AND r.user_id = %(uid)s"
        " LEFT JOIN users u ON u.id = n.created_by"
        f" WHERE n.id = %(nid)s AND {_VISIBLE}",
        _params(g.user, nid=notification_id),
    )
    if row is None:
        abort(404)
    return row


def _mark_read(notification_id):
    execute_query(
        "INSERT IGNORE INTO notification_reads (notification_id, user_id) VALUES (%s, %s)",
        (notification_id, g.user["id"]),
    )


def _back(default):
    return safe_local_path(request.form.get("next")) or default


@bp.route("/notifications")
@login_required
def inbox():
    show = request.args.get("show", "all")
    category = request.args.get("category") or None
    if category not in CATEGORIES:
        category = None
    items = visible_notifications(g.user, unread_only=(show == "unread"), category=category)
    return render_template("notifications/inbox.html", items=items, show=show, category=category, categories=CATEGORIES)


@bp.route("/notifications/<int:notification_id>")
@login_required
def detail(notification_id):
    item = _get_visible(notification_id)
    _mark_read(notification_id)
    return render_template("notifications/detail.html", item=item, categories=CATEGORIES)


@bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    _get_visible(notification_id)
    _mark_read(notification_id)
    return redirect(_back(url_for("notifications.inbox")))


@bp.route("/notifications/<int:notification_id>/unread", methods=["POST"])
@login_required
def mark_unread(notification_id):
    _get_visible(notification_id)
    execute_query(
        "DELETE FROM notification_reads WHERE notification_id = %s AND user_id = %s",
        (notification_id, g.user["id"]),
    )
    return redirect(_back(url_for("notifications.inbox")))


@bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    execute_query(
        "INSERT IGNORE INTO notification_reads (notification_id, user_id)"
        f" SELECT n.id, %(uid)s FROM notifications n WHERE {_VISIBLE}",
        _params(g.user),
    )
    flash("All notifications marked as read.", "success")
    return redirect(_back(url_for("notifications.inbox")))


@bp.route("/api/notifications/summary")
@login_required
def summary():
    latest = visible_notifications(g.user, limit=5)
    return {
        "unread": unread_count(g.user),
        "latest": [
            {
                "id": n["id"],
                "title": n["title"],
                "category": CATEGORIES[n["category"]],
                "important": n["priority"] == "important",
                "unread": n["read_at"] is None,
                "created_at": n["created_at"].isoformat() + "Z",
                "url": url_for("notifications.detail", notification_id=n["id"]),
            }
            for n in latest
        ],
    }


@bp.route("/announcements", methods=["GET", "POST"])
@roles_required("faculty", "admin")
def announcements():
    form = {}
    status = 200
    if request.method == "POST":
        form = request.form
        try:
            title = clean_text(form.get("title"), "Title", min_len=3, max_len=150)
            message = (form.get("message") or "").strip()
            if len(message) < 5:
                raise ValidationError("Message must be at least 5 characters.")
            if len(message) > 5000:
                raise ValidationError("Message must be at most 5000 characters.")
            category = form.get("category")
            if category not in POSTABLE_CATEGORIES:
                raise ValidationError("Choose a valid category.")
            audience = form.get("audience")
            if audience not in AUDIENCES:
                raise ValidationError("Choose who should receive this notification.")
            priority = "important" if form.get("important") else "normal"
        except ValidationError as exc:
            flash(str(exc), "error")
            status = 400
        else:
            with transaction() as cur:
                create_notification(
                    cur,
                    title=title,
                    message=message,
                    category=category,
                    audience=audience,
                    created_by=g.user["id"],
                    priority=priority,
                )
            flash(f"Notification sent to {AUDIENCES[audience].lower()}.", "success")
            return redirect(url_for("notifications.announcements"))

    sent = fetch_all(
        "SELECT n.id, n.title, n.message, n.category, n.priority, n.audience, n.created_at,"
        " n.created_by, u.full_name AS author,"
        " (SELECT COUNT(*) FROM notification_reads r WHERE r.notification_id = n.id) AS read_count"
        " FROM notifications n LEFT JOIN users u ON u.id = n.created_by"
        " WHERE n.audience <> 'user' ORDER BY n.created_at DESC, n.id DESC LIMIT 100"
    )
    return render_template(
        "notifications/announcements.html",
        sent=sent,
        form=form,
        categories=CATEGORIES,
        postable=POSTABLE_CATEGORIES,
        audiences=AUDIENCES,
    ), status


@bp.route("/announcements/<int:notification_id>/delete", methods=["POST"])
@roles_required("faculty", "admin")
def delete_announcement(notification_id):
    row = fetch_one("SELECT id, created_by FROM notifications WHERE id = %s AND audience <> 'user'", (notification_id,))
    if row is None:
        abort(404)
    if g.user["role"] != "admin" and row["created_by"] != g.user["id"]:
        abort(403)
    execute_query("DELETE FROM notifications WHERE id = %s", (notification_id,))
    flash("Notification deleted.", "success")
    return redirect(url_for("notifications.announcements"))
