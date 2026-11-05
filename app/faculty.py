import csv
import io

import mysql.connector
from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from .auth import hash_password, roles_required
from .db import fetch_all, fetch_one, transaction
from .notifications import create_notification
from .result_card import pdf_response
from .rules import (
    GRADE_BANDS,
    PASS_PERCENTAGE,
    ValidationError,
    calculate_grade,
    calculate_percentage,
    check_password,
    clean_person_name,
    clean_roll_no,
    clean_text,
    format_number,
    parse_marks,
    result_status,
)

bp = Blueprint("faculty", __name__, url_prefix="/faculty")
staff_only = roles_required("faculty", "admin")

STATUS_FILTERS = ("all", "pass", "fail", "pending")
GRADES = [grade for _, grade in GRADE_BANDS] + ["F"]

_STUDENT_SELECT = (
    "SELECT s.id, s.user_id, s.roll_no, s.student_name, s.course, s.company, s.topic, s.created_at,"
    " r.marks_obtained, r.total_marks, r.percentage, r.grade, r.remarks, r.updated_at,"
    " u.full_name AS entered_by_name"
    " FROM students s"
    " LEFT JOIN results r ON r.student_id = s.id"
    " LEFT JOIN users u ON u.id = r.entered_by"
)


def _with_status(rows):
    for row in rows:
        row["status"] = result_status(row["percentage"])
    return rows


def _like(term):
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _search_students(query, status, course):
    where, params = [], []
    if query:
        where.append("(s.student_name LIKE %s OR s.roll_no LIKE %s)")
        params += [_like(query), _like(query)]
    if status == "pending":
        where.append("r.id IS NULL")
    elif status == "pass":
        where.append("r.percentage >= %s")
        params.append(PASS_PERCENTAGE)
    elif status == "fail":
        where.append("r.percentage < %s")
        params.append(PASS_PERCENTAGE)
    if course:
        where.append("s.course = %s")
        params.append(course)
    sql = _STUDENT_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY s.roll_no"
    return _with_status(fetch_all(sql, params))


def _filters():
    query = " ".join((request.args.get("q") or "").split())[:100]
    status = request.args.get("status", "all")
    if status not in STATUS_FILTERS:
        status = "all"
    course = (request.args.get("course") or "").strip()[:50]
    return query, status, course


def _get_student(student_id):
    row = fetch_one(_STUDENT_SELECT + " WHERE s.id = %s", (student_id,))
    if row is None:
        abort(404)
    row["status"] = result_status(row["percentage"])
    return row


def _courses():
    return [r["course"] for r in fetch_all("SELECT DISTINCT course FROM students ORDER BY course")]


@bp.route("/")
@staff_only
def dashboard():
    stats = fetch_one(
        "SELECT COUNT(s.id) AS students, COUNT(r.id) AS published,"
        " COALESCE(SUM(r.percentage >= %s), 0) AS passed, AVG(r.percentage) AS average"
        " FROM students s LEFT JOIN results r ON r.student_id = s.id",
        (PASS_PERCENTAGE,),
    )
    stats["pending"] = stats["students"] - stats["published"]
    stats["failed"] = stats["published"] - int(stats["passed"])
    stats["pass_rate"] = round(int(stats["passed"]) * 100 / stats["published"]) if stats["published"] else None
    counts = {r["grade"]: r["n"] for r in fetch_all("SELECT grade, COUNT(*) AS n FROM results GROUP BY grade")}
    peak = max(counts.values(), default=0)
    distribution = [
        {"grade": grade, "count": counts.get(grade, 0), "share": (counts.get(grade, 0) * 100 // peak) if peak else 0}
        for grade in GRADES
    ]
    recent = _with_status(fetch_all(_STUDENT_SELECT + " WHERE r.id IS NOT NULL ORDER BY r.updated_at DESC LIMIT 5"))
    top = _with_status(
        fetch_all(_STUDENT_SELECT + " WHERE r.id IS NOT NULL ORDER BY r.percentage DESC, s.roll_no LIMIT 3")
    )
    pending = fetch_all(_STUDENT_SELECT + " WHERE r.id IS NULL ORDER BY s.roll_no LIMIT 5")
    return render_template(
        "faculty/dashboard.html", stats=stats, distribution=distribution, recent=recent, top=top, pending=pending
    )


@bp.route("/students")
@staff_only
def students():
    query, status, course = _filters()
    rows = _search_students(query, status, course)
    return render_template(
        "faculty/students.html", students=rows, q=query, status=status, course=course, courses=_courses()
    )


@bp.route("/students/export.csv")
@staff_only
def export_csv():
    query, status, course = _filters()
    rows = _search_students(query, status, course)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["Roll No", "Name", "Course", "Company", "Topic", "Marks", "Total", "Percentage", "Grade", "Status", "Remarks"]
    )
    for r in rows:
        writer.writerow(
            [
                _csv_safe(v)
                for v in (
                    r["roll_no"],
                    r["student_name"],
                    r["course"],
                    r["company"],
                    r["topic"],
                    format_number(r["marks_obtained"]),
                    format_number(r["total_marks"]),
                    r["percentage"] if r["percentage"] is not None else "",
                    r["grade"] or "",
                    r["status"],
                    r["remarks"] or "",
                )
            ]
        )
    return Response(
        "﻿" + buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=student_results.csv"},
    )


def _csv_safe(value):
    """Stop spreadsheet apps from treating a text cell as a formula."""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _read_student_form(form, *, require_password):
    data = {
        "roll_no": clean_roll_no(form.get("roll_no")),
        "student_name": clean_person_name(form.get("student_name"), "Student name"),
        "course": clean_text(form.get("course"), "Course", min_len=2, max_len=50),
        "company": clean_text(form.get("company"), "Company / organisation", min_len=2, max_len=100),
        "topic": clean_text(form.get("topic"), "Project topic", min_len=3, max_len=150),
    }
    password = form.get("password") or ""
    if require_password or password:
        check_password(password, form.get("confirm_password") or "")
    data["password"] = password
    return data


def _roll_taken(roll_no, exclude_student_id=None):
    row = fetch_one(
        "SELECT s.id FROM students s WHERE s.roll_no = %s AND s.id <> %s"
        " UNION SELECT NULL FROM users u WHERE u.username = %s"
        " AND u.id NOT IN (SELECT user_id FROM students WHERE id = %s AND user_id IS NOT NULL)",
        (roll_no, exclude_student_id or 0, roll_no.lower(), exclude_student_id or 0),
    )
    return row is not None


@bp.route("/students/new", methods=["GET", "POST"])
@staff_only
def add_student():
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        try:
            data = _read_student_form(form, require_password=True)
            if _roll_taken(data["roll_no"]):
                raise ValidationError(f"A student or account with roll number {data['roll_no']} already exists.")
            with transaction() as cur:
                cur.execute(
                    "INSERT INTO users (username, password_hash, full_name, role) VALUES (%s, %s, %s, 'student')",
                    (data["roll_no"].lower(), hash_password(data["password"]), data["student_name"]),
                )
                user_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO students (user_id, roll_no, student_name, course, company, topic)"
                    " VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, data["roll_no"], data["student_name"], data["course"], data["company"], data["topic"]),
                )
                create_notification(
                    cur,
                    title="Welcome to the result portal",
                    message=(
                        f'Your student account has been created for the project "{data["topic"]}" '
                        f"at {data['company']}. You will be notified here as soon as your result is published."
                    ),
                    category="notice",
                    audience="user",
                    target_user_id=user_id,
                    created_by=g.user["id"],
                )
        except ValidationError as exc:
            flash(str(exc), "error")
            return render_template("faculty/student_form.html", form=form, student=None, courses=_courses()), 400
        except mysql.connector.IntegrityError:
            flash("That roll number already exists.", "error")
            return render_template("faculty/student_form.html", form=form, student=None, courses=_courses()), 409
        flash(f"Student {data['student_name']} added. They can log in with roll number {data['roll_no']}.", "success")
        if form.get("next_action") == "result":
            student = fetch_one("SELECT id FROM students WHERE roll_no = %s", (data["roll_no"],))
            return redirect(url_for("faculty.result", student_id=student["id"]))
        return redirect(url_for("faculty.students"))
    return render_template("faculty/student_form.html", form=form, student=None, courses=_courses())


@bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@staff_only
def edit_student(student_id):
    student = _get_student(student_id)
    form = request.form if request.method == "POST" else student
    if request.method == "POST":
        try:
            data = _read_student_form(form, require_password=False)
            if _roll_taken(data["roll_no"], student_id):
                raise ValidationError(f"Roll number {data['roll_no']} is already used by another student.")
            with transaction() as cur:
                cur.execute(
                    "UPDATE students SET roll_no = %s, student_name = %s, course = %s, company = %s, topic = %s"
                    " WHERE id = %s",
                    (data["roll_no"], data["student_name"], data["course"], data["company"], data["topic"], student_id),
                )
                if student["user_id"]:
                    cur.execute(
                        "UPDATE users SET username = %s, full_name = %s WHERE id = %s",
                        (data["roll_no"].lower(), data["student_name"], student["user_id"]),
                    )
                    if data["password"]:
                        cur.execute(
                            "UPDATE users SET password_hash = %s WHERE id = %s",
                            (hash_password(data["password"]), student["user_id"]),
                        )
        except ValidationError as exc:
            flash(str(exc), "error")
            return render_template("faculty/student_form.html", form=form, student=student, courses=_courses()), 400
        except mysql.connector.IntegrityError:
            flash("That roll number already exists.", "error")
            return render_template("faculty/student_form.html", form=form, student=student, courses=_courses()), 409
        message = "Student details updated."
        if student["user_id"] and data["roll_no"] != student["roll_no"]:
            message += f" Their login username is now {data['roll_no']}."
        if data["password"] and student["user_id"]:
            message += " The student's password was reset."
        flash(message, "success")
        return redirect(url_for("faculty.students"))
    return render_template("faculty/student_form.html", form=form, student=student, courses=_courses())


@bp.route("/students/<int:student_id>/result", methods=["GET", "POST"])
@staff_only
def result(student_id):
    student = _get_student(student_id)
    if request.method == "POST":
        form = request.form
        try:
            marks, total = parse_marks(form.get("marks_obtained"), form.get("total_marks"))
            remarks = clean_text(form.get("remarks"), "Remarks", max_len=255, required=False) or None
        except ValidationError as exc:
            flash(str(exc), "error")
            return render_template("faculty/result_form.html", student=student, form=form), 400
        percentage = calculate_percentage(marks, total)
        grade = calculate_grade(percentage)
        status = result_status(percentage)
        is_update = student["percentage"] is not None
        with transaction() as cur:
            cur.execute(
                "INSERT INTO results (student_id, marks_obtained, total_marks, percentage, grade, remarks, entered_by)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)"
                " ON DUPLICATE KEY UPDATE marks_obtained = VALUES(marks_obtained),"
                " total_marks = VALUES(total_marks), percentage = VALUES(percentage), grade = VALUES(grade),"
                " remarks = VALUES(remarks), entered_by = VALUES(entered_by)",
                (student_id, marks, total, percentage, grade, remarks, g.user["id"]),
            )
            if student["user_id"]:
                create_notification(
                    cur,
                    title="Your result has been updated" if is_update else "Your result has been published",
                    message=(
                        f'Minor project result for "{student["topic"]}": '
                        f"{format_number(marks)} / {format_number(total)} marks, "
                        f"{percentage}% - Grade {grade} ({status})." + (f" Remarks: {remarks}" if remarks else "")
                    ),
                    category="result",
                    audience="user",
                    target_user_id=student["user_id"],
                    created_by=g.user["id"],
                    priority="important",
                )
        flash(
            f"Result {'updated' if is_update else 'saved'} for {student['student_name']}: "
            f"{percentage}% - Grade {grade} ({status}). The student has been notified.",
            "success",
        )
        return redirect(url_for("faculty.students"))
    form = {
        "marks_obtained": format_number(student["marks_obtained"]),
        "total_marks": format_number(student["total_marks"]) or "100",
        "remarks": student["remarks"] or "",
    }
    return render_template("faculty/result_form.html", student=student, form=form)


@bp.route("/students/<int:student_id>/result.pdf")
@staff_only
def result_pdf(student_id):
    student = _get_student(student_id)
    if student["percentage"] is None:
        flash(f"{student['student_name']} has no published result yet, so there is no result card to download.", "info")
        return redirect(url_for("faculty.students"))
    return pdf_response(student)


@bp.route("/students/<int:student_id>/delete", methods=["POST"])
@staff_only
def delete_student(student_id):
    student = _get_student(student_id)
    with transaction() as cur:
        # Deleting the login account cascades to the student row, result and personal notifications.
        if student["user_id"]:
            cur.execute("DELETE FROM users WHERE id = %s AND role = 'student'", (student["user_id"],))
        cur.execute("DELETE FROM students WHERE id = %s", (student_id,))
    flash(f"Student {student['student_name']} ({student['roll_no']}) and their result were deleted.", "success")
    return redirect(url_for("faculty.students"))
