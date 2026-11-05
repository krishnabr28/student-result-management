from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, flash, g, redirect, render_template, url_for

from .auth import roles_required
from .db import fetch_one
from .notifications import CATEGORIES, visible_notifications
from .result_card import SESSION, pdf_response
from .rules import GRADE_BANDS, PASS_PERCENTAGE, result_status

bp = Blueprint("student", __name__, url_prefix="/student")


def _own_record():
    """The logged-in student's record; looked up by session user id only, never by a URL parameter."""
    record = fetch_one(
        "SELECT s.roll_no, s.student_name, s.course, s.company, s.topic, s.created_at,"
        " r.marks_obtained, r.total_marks, r.percentage, r.grade, r.remarks, r.updated_at,"
        " u.full_name AS entered_by_name"
        " FROM students s LEFT JOIN results r ON r.student_id = s.id LEFT JOIN users u ON u.id = r.entered_by"
        " WHERE s.user_id = %s",
        (g.user["id"],),
    )
    if record:
        record["status"] = result_status(record["percentage"])
    return record


def grade_scale(percentage):
    """Bands from lowest to highest for the score bar, with the student's band and the gap to the next one."""
    edges = [Decimal(0)] + [minimum for minimum, _ in reversed(GRADE_BANDS)] + [Decimal(100)]
    grades = ["F"] + [grade for _, grade in reversed(GRADE_BANDS)]
    bands = []
    for index, grade in enumerate(grades):
        start, end = edges[index], edges[index + 1]
        bands.append({"grade": grade, "start": start, "width": end - start, "current": False})
    standing = {"bands": bands, "next_grade": None, "gap": None, "above_pass": None}
    if percentage is None:
        return standing
    percentage = Decimal(percentage)
    current = max(i for i, band in enumerate(bands) if percentage >= band["start"])
    bands[current]["current"] = True
    if current + 1 < len(bands):
        standing["next_grade"] = bands[current + 1]["grade"]
        standing["gap"] = bands[current + 1]["start"] - percentage
    standing["above_pass"] = percentage - PASS_PERCENTAGE
    return standing


def _require_published(record):
    if not record:
        flash("Your login is not linked to a student record yet. Please contact your faculty.", "error")
        return redirect(url_for("student.dashboard"))
    if record["percentage"] is None:
        flash("Your result has not been published yet. You will be notified when it is available.", "info")
        return redirect(url_for("student.dashboard"))
    return None


@bp.route("/")
@roles_required("student")
def dashboard():
    record = _own_record()
    return render_template(
        "student/dashboard.html",
        record=record,
        standing=grade_scale(record["percentage"]) if record else None,
        recent=visible_notifications(g.user, limit=4),
        categories=CATEGORIES,
        bands=GRADE_BANDS,
        pass_mark=PASS_PERCENTAGE,
        session_name=SESSION,
    )


@bp.route("/result")
@roles_required("student")
def result_card():
    record = _own_record()
    blocked = _require_published(record)
    if blocked:
        return blocked
    return render_template(
        "student/result_card.html",
        record=record,
        bands=GRADE_BANDS,
        pass_mark=PASS_PERCENTAGE,
        session_name=SESSION,
        generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


@bp.route("/result.pdf")
@roles_required("student")
def result_pdf():
    record = _own_record()
    return _require_published(record) or pdf_response(record)
