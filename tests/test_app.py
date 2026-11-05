"""End-to-end tests through the Flask test client against a real MySQL test database."""

from decimal import Decimal

from app import create_app
from conftest import Browser, csrf_from, query

FACULTY = ("faculty", "Faculty@123")
ADMIN = ("admin", "Admin@123")
STUDENT = ("241203106130", "Student@123")
PENDING_STUDENT = ("241203106105", "Student@123")


def student_id(db, roll):
    return query(db, "SELECT id FROM students WHERE roll_no = %s", (roll,))[0][0]


def unread_for(browser):
    return browser.get("/api/notifications/summary").get_json()["unread"]


# ---------- Authentication and access control ----------


def test_login_page_shows_demo_accounts(client):
    html = client.get("/login").get_data(as_text=True)
    assert "Faculty Login" not in html
    assert "Log in to your account" in html
    assert 'data-demo-user="faculty"' in html


def test_wrong_password_rejected(browser):
    response = browser.login("faculty", "wrong-password")
    assert response.status_code == 401
    assert "Invalid username or password" in response.get_data(as_text=True)


def test_unknown_user_rejected(browser):
    assert browser.login("nobody", "whatever123").status_code == 401


def test_faculty_login_and_dashboard(browser):
    response = browser.login(*FACULTY)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/faculty/")
    html = browser.get("/faculty/").get_data(as_text=True)
    assert "Welcome, Dr. Anjali Sharma" in html
    assert "Pending results" in html


def test_student_login_goes_to_student_portal(browser):
    response = browser.login(*STUDENT)
    assert response.headers["Location"].endswith("/student/")
    html = browser.get("/student/").get_data(as_text=True)
    assert "Krishna Kumar Singh" in html
    assert "86.00%" in html
    assert "Grade A" in html


def test_anonymous_redirected_to_login(client):
    response = client.get("/faculty/students")
    assert response.status_code == 302
    assert "/login?next=" in response.headers["Location"]


def test_student_cannot_open_staff_pages(browser):
    browser.login(*STUDENT)
    for url in ("/faculty/", "/faculty/students", "/announcements", "/admin/users", "/faculty/students/export.csv"):
        assert browser.get(url).status_code == 403, url


def test_faculty_cannot_open_admin_pages(browser):
    browser.login(*FACULTY)
    assert browser.get("/admin/users").status_code == 403


def test_post_without_csrf_token_rejected(client):
    response = client.post("/login", data={"username": "faculty", "password": "Faculty@123"})
    assert response.status_code == 400


def test_open_redirect_blocked(browser):
    response = browser.post("/login?next=//evil.example/x", {"username": "faculty", "password": "Faculty@123"})
    assert response.headers["Location"].endswith("/faculty/")


def test_safe_next_redirect_followed(browser):
    response = browser.post("/login?next=/notifications", {"username": "faculty", "password": "Faculty@123"})
    assert response.headers["Location"].endswith("/notifications")


def test_logout(browser):
    browser.login(*FACULTY)
    browser.logout()
    assert browser.get("/faculty/").status_code == 302


def test_change_password(browser):
    browser.login(*STUDENT)
    bad = browser.post(
        "/account/password",
        {"current_password": "nope", "new_password": "NewPass@123", "confirm_password": "NewPass@123"},
    )
    assert bad.status_code == 400
    ok = browser.post(
        "/account/password",
        {"current_password": "Student@123", "new_password": "NewPass@123", "confirm_password": "NewPass@123"},
    )
    assert ok.status_code == 302
    browser.logout()
    assert browser.login(STUDENT[0], "Student@123").status_code == 401
    assert browser.login(STUDENT[0], "NewPass@123").status_code == 302


# ---------- Students ----------


def test_add_student_creates_login_and_welcome_notification(browser, db):
    browser.login(*FACULTY)
    response = browser.post(
        "/faculty/students/new",
        {
            "roll_no": "241203106199",
            "student_name": "Riya Kapoor",
            "course": "BCA",
            "company": "Infosys",
            "topic": "Smart Parking System",
            "password": "Riya@12345",
            "confirm_password": "Riya@12345",
        },
    )
    assert response.status_code == 302
    assert query(db, "SELECT student_name FROM students WHERE roll_no = '241203106199'") == [("Riya Kapoor",)]
    browser.logout()
    assert browser.login("241203106199", "Riya@12345").status_code == 302
    html = browser.get("/student/").get_data(as_text=True)
    assert "Result pending" in html
    assert "Welcome to the result portal" in html
    assert unread_for(browser) >= 1


def test_duplicate_roll_number_blocked(browser, db):
    browser.login(*FACULTY)
    response = browser.post(
        "/faculty/students/new",
        {
            "roll_no": "241203106130",
            "student_name": "Someone Else",
            "course": "BCA",
            "company": "X Corp",
            "topic": "Duplicate",
            "password": "Pass@12345",
            "confirm_password": "Pass@12345",
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.get_data(as_text=True)
    assert query(db, "SELECT COUNT(*) FROM students WHERE roll_no = '241203106130'") == [(1,)]


def test_add_student_validation_keeps_form_values(browser):
    browser.login(*FACULTY)
    response = browser.post(
        "/faculty/students/new",
        {
            "roll_no": "ab",
            "student_name": "Valid Name",
            "course": "BCA",
            "company": "Wipro",
            "topic": "Some topic",
            "password": "Pass@12345",
            "confirm_password": "Pass@12345",
        },
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Roll number must be" in html
    assert 'value="Valid Name"' in html


def test_edit_student_and_reset_password(browser, db):
    browser.login(*FACULTY)
    sid = student_id(db, "241203106130")
    response = browser.post(
        f"/faculty/students/{sid}/edit",
        {
            "roll_no": "241203106130",
            "student_name": "Krishna K Singh",
            "course": "BCA",
            "company": "GNIOT Lab",
            "topic": "Result Portal",
            "password": "Changed@123",
            "confirm_password": "Changed@123",
        },
    )
    assert response.status_code == 302
    assert query(db, "SELECT student_name, company FROM students WHERE id = %s", (sid,)) == [
        ("Krishna K Singh", "GNIOT Lab")
    ]
    browser.logout()
    assert browser.login("241203106130", "Changed@123").status_code == 302


def test_search_and_status_filters(browser):
    browser.login(*FACULTY)
    html = browser.get("/faculty/students?q=pathak").get_data(as_text=True)
    assert "Krish Pathak" in html and "Aarav Gupta" not in html
    html = browser.get("/faculty/students?q=241203106185").get_data(as_text=True)
    assert "Pradeep" in html and "Showing 1 student" in html
    html = browser.get("/faculty/students?status=pending").get_data(as_text=True)
    assert "Vikas Sharma" in html and "Krish Pathak" not in html
    html = browser.get("/faculty/students?status=fail").get_data(as_text=True)
    assert "Aarav Gupta" in html and "Arjun Mehta" in html and "Priya Singh" not in html
    html = browser.get("/faculty/students?q=%25").get_data(as_text=True)
    assert "No matching students" in html


def test_delete_student_removes_account_and_result(browser, db):
    browser.login(*FACULTY)
    sid = student_id(db, "241203106101")
    assert browser.post(f"/faculty/students/{sid}/delete").status_code == 302
    assert query(db, "SELECT COUNT(*) FROM students WHERE id = %s", (sid,)) == [(0,)]
    assert query(db, "SELECT COUNT(*) FROM results WHERE student_id = %s", (sid,)) == [(0,)]
    assert query(db, "SELECT COUNT(*) FROM users WHERE username = '241203106101'") == [(0,)]


def test_missing_student_returns_404(browser):
    browser.login(*FACULTY)
    assert browser.get("/faculty/students/99999/result").status_code == 404


# ---------- Results ----------


def test_enter_result_notifies_student(browser, db):
    browser.login(*PENDING_STUDENT)
    before = unread_for(browser)
    browser.logout()

    browser.login(*FACULTY)
    sid = student_id(db, PENDING_STUDENT[0])
    response = browser.post(
        f"/faculty/students/{sid}/result", {"marks_obtained": "45", "total_marks": "60", "remarks": "Good work"}
    )
    assert response.status_code == 302
    rows = query(db, "SELECT marks_obtained, total_marks, percentage, grade FROM results WHERE student_id = %s", (sid,))
    assert rows == [(Decimal("45.00"), Decimal("60.00"), Decimal("75.00"), "B")]
    browser.logout()

    browser.login(*PENDING_STUDENT)
    assert unread_for(browser) == before + 1
    latest = browser.get("/api/notifications/summary").get_json()["latest"][0]
    assert latest["title"] == "Your result has been published" and latest["unread"]
    html = browser.get("/student/").get_data(as_text=True)
    assert "75.00%" in html and "Good work" in html


def test_update_result_keeps_one_row(browser, db):
    browser.login(*FACULTY)
    sid = student_id(db, "241203106130")
    browser.post(f"/faculty/students/{sid}/result", {"marks_obtained": "92", "total_marks": "100"})
    assert query(db, "SELECT COUNT(*), MAX(grade) FROM results WHERE student_id = %s", (sid,)) == [(1, "A+")]
    titles = query(
        db,
        "SELECT n.title FROM notifications n JOIN students s ON s.user_id = n.target_user_id"
        " WHERE s.id = %s ORDER BY n.id DESC LIMIT 1",
        (sid,),
    )
    assert titles == [("Your result has been updated",)]


def test_invalid_marks_not_saved(browser, db):
    browser.login(*FACULTY)
    sid = student_id(db, PENDING_STUDENT[0])
    for marks, total in [("101", "100"), ("5", "0"), ("-1", "100"), ("abc", "100"), ("nan", "100"), ("inf", "100")]:
        response = browser.post(f"/faculty/students/{sid}/result", {"marks_obtained": marks, "total_marks": total})
        assert response.status_code == 400, (marks, total)
    assert query(db, "SELECT COUNT(*) FROM results WHERE student_id = %s", (sid,)) == [(0,)]


def test_database_check_constraint_backs_up_validation(db):
    sid = query(db, "SELECT id FROM students LIMIT 1")[0][0]
    try:
        db.execute("UPDATE results SET marks_obtained = 150, total_marks = 100 WHERE student_id = %s", (sid,))
    except Exception as exc:  # noqa: BLE001 - any constraint error is the expected outcome
        assert "chk_results_marks" in str(exc)
    else:
        raise AssertionError("CHECK constraint did not reject marks above total")


def test_csv_export(browser):
    browser.login(*FACULTY)
    response = browser.get("/faculty/students/export.csv?status=pending")
    text = response.get_data(as_text=True)
    assert response.mimetype == "text/csv"
    assert "Roll No,Name" in text
    assert "Vikas Sharma" in text and "Krish Pathak" not in text


def test_csv_export_escapes_formulas(browser, db):
    browser.login(*FACULTY)
    browser.post(
        "/faculty/students/new",
        {
            "roll_no": "EVIL-1",
            "student_name": "Test Person",
            "course": "BCA",
            "company": "=HYPERLINK(1)",
            "topic": "Formula test",
            "password": "Pass@12345",
            "confirm_password": "Pass@12345",
        },
    )
    text = browser.get("/faculty/students/export.csv?q=EVIL").get_data(as_text=True)
    assert "'=HYPERLINK(1)" in text


# ---------- Notifications ----------


def test_student_sees_only_their_audience(browser):
    browser.login(*STUDENT)
    html = browser.get("/notifications").get_data(as_text=True)
    assert "Minor project viva-voce schedule" in html
    assert "Result portal is now live" in html
    assert "Marks entry closes" not in html  # faculty-only notice


def test_faculty_sees_faculty_notice_not_student_results(browser):
    browser.login(*FACULTY)
    html = browser.get("/notifications").get_data(as_text=True)
    assert "Marks entry closes" in html
    assert "Your result has been published" not in html


def test_mark_read_unread_and_all(browser):
    browser.login(*STUDENT)
    start = unread_for(browser)
    assert start > 0
    first_unread = next(n for n in browser.get("/api/notifications/summary").get_json()["latest"] if n["unread"])
    browser.get(first_unread["url"])
    assert unread_for(browser) == start - 1
    nid = first_unread["url"].rsplit("/", 1)[1]
    browser.post(f"/notifications/{nid}/unread")
    assert unread_for(browser) == start
    browser.post("/notifications/read-all")
    assert unread_for(browser) == 0
    html = browser.get("/notifications?show=unread").get_data(as_text=True)
    assert "No unread notifications" in html


def test_cannot_open_another_users_notification(browser, db):
    other = query(
        db,
        "SELECT n.id FROM notifications n JOIN users u ON u.id = n.target_user_id"
        " WHERE u.username = '241203106125' LIMIT 1",
    )[0][0]
    browser.login(*STUDENT)
    assert browser.get(f"/notifications/{other}").status_code == 404
    assert browser.post(f"/notifications/{other}/read").status_code == 404


def test_announcement_reaches_students(browser):
    browser.login(*FACULTY)
    response = browser.post(
        "/announcements",
        {
            "title": "Lab closed on Friday",
            "message": "Computer lab 3 is closed.",
            "category": "notice",
            "audience": "students",
            "important": "1",
        },
    )
    assert response.status_code == 302
    browser.logout()
    browser.login(*STUDENT)
    latest = browser.get("/api/notifications/summary").get_json()["latest"][0]
    assert latest["title"] == "Lab closed on Friday" and latest["important"] and latest["unread"]


def test_announcement_validation(browser):
    browser.login(*FACULTY)
    response = browser.post("/announcements", {"title": "", "message": "x", "category": "notice", "audience": "all"})
    assert response.status_code == 400
    response = browser.post(
        "/announcements", {"title": "Valid", "message": "Valid message", "category": "result", "audience": "all"}
    )
    assert response.status_code == 400


def test_only_author_or_admin_deletes_announcement(browser, db):
    nid = query(db, "SELECT id FROM notifications WHERE title = 'Marks entry closes on 20 November'")[0][0]
    browser.login(*FACULTY)  # written by admin
    assert browser.post(f"/announcements/{nid}/delete").status_code == 403
    browser.logout()
    browser.login(*ADMIN)
    assert browser.post(f"/announcements/{nid}/delete").status_code == 302
    assert query(db, "SELECT COUNT(*) FROM notifications WHERE id = %s", (nid,)) == [(0,)]


# ---------- Admin ----------


def test_admin_creates_and_deactivates_faculty(browser, db):
    browser.login(*ADMIN)
    response = browser.post(
        "/admin/users",
        {
            "full_name": "Dr. Neha Gupta",
            "username": "neha.gupta",
            "role": "faculty",
            "password": "Neha@12345",
            "confirm_password": "Neha@12345",
        },
    )
    assert response.status_code == 302
    uid = query(db, "SELECT id FROM users WHERE username = 'neha.gupta'")[0][0]
    browser.post(f"/admin/users/{uid}/toggle")
    browser.logout()
    response = browser.login("neha.gupta", "Neha@12345")
    assert response.status_code == 403
    assert "deactivated" in response.get_data(as_text=True)


def test_admin_cannot_deactivate_self(browser, db):
    browser.login(*ADMIN)
    uid = query(db, "SELECT id FROM users WHERE username = 'admin'")[0][0]
    browser.post(f"/admin/users/{uid}/toggle")
    assert query(db, "SELECT is_active FROM users WHERE id = %s", (uid,)) == [(1,)]


def test_admin_cannot_manage_students_via_staff_routes(browser, db):
    browser.login(*ADMIN)
    uid = query(db, "SELECT id FROM users WHERE username = '241203106130'")[0][0]
    assert browser.post(f"/admin/users/{uid}/toggle").status_code == 404


def test_deactivated_user_loses_session(browser, db):
    browser.login(*FACULTY)
    assert browser.get("/faculty/").status_code == 200
    db.execute("UPDATE users SET is_active = FALSE WHERE username = 'faculty'")
    assert browser.get("/faculty/").status_code == 302


# ---------- Errors ----------


def test_database_down_shows_friendly_page(db_config):
    broken = dict(db_config, port=1)
    client = create_app({"TESTING": True, "SECRET_KEY": "x", "DB": broken}).test_client()
    browser = Browser(client)
    response = browser.login(*FACULTY)
    assert response.status_code == 503
    assert "Database not reachable" in response.get_data(as_text=True)


def test_unknown_page_404(client):
    assert client.get("/no-such-page").status_code == 404


def test_security_headers(client):
    response = client.get("/login")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert csrf_from(response)


def test_backslash_and_control_char_redirects_blocked(browser):
    for target in ("/%5Cevil.example", "/%09/evil.example", "/%5C%5Cevil.example"):
        response = browser.post(f"/login?next={target}", {"username": "faculty", "password": "Faculty@123"})
        assert response.headers["Location"].endswith("/faculty/"), target
        browser.logout()
    browser.login(*FACULTY)
    response = browser.post("/notifications/read-all", {"next": "/\\evil.example"})
    assert response.headers["Location"].endswith("/notifications")


def test_non_ascii_csrf_token_is_a_clean_400(client):
    response = client.post("/login", data={"csrf_token": "é", "username": "x", "password": "y"})
    assert response.status_code == 400
