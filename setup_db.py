"""Create the MySQL database, tables and (optionally) demo data.

python setup_db.py              create database + tables + demo data (first run)
python setup_db.py --reset      drop everything and start again with fresh demo data
python setup_db.py --no-demo    create tables and only an admin account (asks for a password)
"""

import argparse
import getpass
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import mysql.connector
from werkzeug.security import generate_password_hash

from app.config import load_config
from app.demo import DEFAULT_PASSWORDS, DEMO_PASSWORDS
from app.rules import (
    ValidationError,
    calculate_grade,
    calculate_percentage,
    check_password,
    format_number,
    result_status,
)

SCHEMA = Path(__file__).with_name("schema.sql")


STAFF = [
    ("admin", "System Administrator", "admin"),
    ("faculty", "Dr. Anjali Sharma", "faculty"),
    ("faculty2", "Prof. Rajeev Verma", "faculty"),
]

# roll_no, name, company, topic, (marks, total) or None for pending, entered by
LAB = "GNIOT Software Lab"
SRMS = "Student Result Management System"
STUDENTS = [
    ("241203106130", "Krishna Kumar Singh", LAB, SRMS, (86, 100), "faculty"),
    ("241203106125", "Krish Pathak", LAB, SRMS, (91, 100), "faculty"),
    ("241203106185", "Pradeep", LAB, SRMS, (45, 60), "faculty"),
    ("241203106101", "Aarav Gupta", "TCS iON", "Library Management System", (35, 100), "faculty"),
    ("241203106102", "Ananya Verma", "Wipro", "Online Quiz Application", (78, 100), "faculty2"),
    ("241203106103", "Rohit Yadav", "HCLTech", "Hospital Appointment Booking", (62, 100), "faculty2"),
    ("241203106104", "Sneha Chauhan", "Tech Mahindra", "Expense Tracker with Charts", (55, 100), "faculty"),
    ("241203106105", "Vikas Sharma", "Accenture", "QR Code Attendance System", None, None),
    ("241203106106", "Priya Singh", "Cognizant", "E-commerce Product Catalogue", (Decimal("89.5"), 100), "faculty2"),
    ("241203106107", "Mohit Kumar", "Capgemini", "Weather Forecast Dashboard", None, None),
    ("241203106108", "Neha Rawat", "Infosys", "Hostel Room Allocation System", None, None),
    ("241203106109", "Arjun Mehta", "IBM SkillsBuild", "Chatbot for College FAQs", (38, 100), "faculty"),
]

# title, message, category, priority, audience, author, hours ago
BROADCASTS = [
    (
        "Result portal is now live",
        "Minor project results for the 2026-2027 session will be published on this portal. "
        "Log in regularly to check your result and important notices.",
        "announcement",
        "normal",
        "all",
        "admin",
        120,
    ),
    (
        "End-semester examination form",
        "End-semester examination forms are open on the CCSU portal until 10 November 2026. "
        "Late submissions will attract a fine.",
        "exam",
        "important",
        "students",
        "admin",
        72,
    ),
    (
        "Final report submission deadline",
        "Submit the final minor project report (PDF) and source code to your project guide by 14 November 2026.",
        "notice",
        "important",
        "all",
        "faculty",
        50,
    ),
    (
        "Minor project viva-voce schedule",
        "Viva-voce for BCA minor projects will be held on 18 November 2026 in Computer Lab 3 from 10:00 AM. "
        "Bring two printed copies of your project report and your college ID card.",
        "exam",
        "important",
        "students",
        "faculty",
        26,
    ),
    (
        "Marks entry closes on 20 November",
        "Please complete minor project marks entry for all assigned students by 20 November 2026.",
        "notice",
        "normal",
        "faculty",
        "admin",
        8,
    ),
]


def connect(config, database=None):
    return mysql.connector.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=database,
        autocommit=True,
        time_zone="+00:00",
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
    )


def create_schema(cur):
    sql = re.sub(r"--[^\n]*", "", SCHEMA.read_text(encoding="utf-8"))
    for statement in sql.split(";"):
        if statement.strip():
            cur.execute(statement)


def seed_demo(cur):
    for role, password in DEMO_PASSWORDS.items():
        try:
            check_password(password)
        except ValidationError as exc:
            sys.exit(f"DEMO_{role.upper()}_PASSWORD: {exc}")
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    ids = {}
    for username, full_name, role in STAFF:
        cur.execute(
            "INSERT INTO users (username, password_hash, full_name, role, created_at) VALUES (%s, %s, %s, %s, %s)",
            (username, generate_password_hash(DEMO_PASSWORDS[role]), full_name, role, now - timedelta(days=10)),
        )
        ids[username] = cur.lastrowid

    student_hash = generate_password_hash(DEMO_PASSWORDS["student"])
    for index, (roll, name, company, topic, marks, author) in enumerate(STUDENTS):
        created = now - timedelta(days=7, hours=index)
        cur.execute(
            "INSERT INTO users (username, password_hash, full_name, role, created_at)"
            " VALUES (%s, %s, %s, 'student', %s)",
            (roll.lower(), student_hash, name, created),
        )
        user_id = cur.lastrowid
        cur.execute(
            "INSERT INTO students (user_id, roll_no, student_name, course, company, topic, created_at)"
            " VALUES (%s, %s, %s, 'BCA', %s, %s, %s)",
            (user_id, roll, name, company, topic, created),
        )
        student_id = cur.lastrowid
        welcome_id = _notify(
            cur,
            "Welcome to the result portal",
            f'Your student account has been created for the project "{topic}" at {company}. '
            "You will be notified here as soon as your result is published.",
            "notice",
            "normal",
            "user",
            ids["faculty"],
            created,
            user_id,
        )
        cur.execute(
            "INSERT INTO notification_reads (notification_id, user_id, read_at) VALUES (%s, %s, %s)",
            (welcome_id, user_id, created + timedelta(hours=1)),
        )
        if marks is None:
            continue
        got, total = Decimal(marks[0]), Decimal(marks[1])
        percentage = calculate_percentage(got, total)
        grade = calculate_grade(percentage)
        published = now - timedelta(hours=3 + index * 2)
        cur.execute(
            "INSERT INTO results (student_id, marks_obtained, total_marks, percentage, grade, entered_by, updated_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (student_id, got, total, percentage, grade, ids[author], published),
        )
        _notify(
            cur,
            "Your result has been published",
            f'Minor project result for "{topic}": {format_number(got)} / {format_number(total)} marks, '
            f"{percentage}% - Grade {grade} ({result_status(percentage)}).",
            "result",
            "important",
            "user",
            ids[author],
            published,
            user_id,
        )

    for title, message, category, priority, audience, author, hours in BROADCASTS:
        _notify(cur, title, message, category, priority, audience, ids[author], now - timedelta(hours=hours))
    # The oldest broadcast has already been read by everyone, so the demo shows a read/unread mix.
    cur.execute(
        "INSERT INTO notification_reads (notification_id, user_id)"
        " SELECT n.id, u.id FROM notifications n CROSS JOIN users u WHERE n.title = %s",
        (BROADCASTS[0][0],),
    )


def _notify(cur, title, message, category, priority, audience, author, created, target=None):
    cur.execute(
        "INSERT INTO notifications (title, message, category, priority, audience, target_user_id, created_by,"
        " created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (title, message, category, priority, audience, target, author, created),
    )
    return cur.lastrowid


def seed_admin_only(cur):
    print("Create the administrator account.")
    while True:
        password = getpass.getpass("Admin password (min 8 characters): ")
        try:
            check_password(password, getpass.getpass("Repeat password: "))
            break
        except ValidationError as exc:
            print(exc)
    cur.execute(
        "INSERT INTO users (username, password_hash, full_name, role)"
        " VALUES ('admin', %s, 'System Administrator', 'admin')",
        (generate_password_hash(password),),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop the database first (deletes all data)")
    parser.add_argument("--no-demo", action="store_true", help="do not load demo data; create only an admin")
    parser.add_argument("--yes", action="store_true", help="do not ask before --reset")
    args = parser.parse_args()

    config = load_config()["DB"]
    name = config["database"]
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        sys.exit("DB_NAME may contain only letters, digits and underscores.")

    try:
        server = connect(config)
    except mysql.connector.Error as exc:
        sys.exit(
            f"Could not connect to MySQL at {config['host']}:{config['port']} as {config['user']}: {exc.msg}\n"
            "Check that MySQL is running and DB_USER / DB_PASSWORD in .env are correct."
        )

    cur = server.cursor()
    if args.reset:
        if not args.yes and input(f"This deletes ALL data in '{name}'. Type 'yes' to continue: ").strip() != "yes":
            sys.exit("Cancelled.")
        cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.execute(f"USE `{name}`")
    create_schema(cur)

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0]:
        print(f"Database '{name}' is ready. Existing data was kept (use --reset to start fresh).")
        return

    server.start_transaction()
    try:
        seed_admin_only(cur) if args.no_demo else seed_demo(cur)
        server.commit()
    except Exception:
        server.rollback()
        raise
    finally:
        cur.close()
        server.close()

    print(f"Database '{name}' created.")
    if args.no_demo:
        print("Log in as 'admin' with the password you just entered.")
    else:
        print("Demo data loaded. Demo logins:")
        for label, username, role in (
            ("Admin", "admin", "admin"),
            ("Faculty", "faculty", "faculty"),
            ("Student", "241203106130", "student"),
        ):
            custom = DEMO_PASSWORDS[role] != DEFAULT_PASSWORDS[role]
            shown = f"(password from DEMO_{role.upper()}_PASSWORD)" if custom else DEMO_PASSWORDS[role]
            print(f"  {label:<8} {username} / {shown}")


if __name__ == "__main__":
    main()
