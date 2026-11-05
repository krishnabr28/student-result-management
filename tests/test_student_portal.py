"""Student portal: result card PDF, printable page, dashboard and access rules."""

import re
import zlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.result_card import build_result_card, pdf_text, safe_filename
from app.student import grade_scale
from conftest import query

FACULTY = ("faculty", "Faculty@123")
ADMIN = ("admin", "Admin@123")
STUDENT = ("241203106130", "Student@123")
OTHER_STUDENT = ("241203106125", "Student@123")
FAILED_STUDENT = ("241203106101", "Student@123")
PENDING_STUDENT = ("241203106105", "Student@123")


def student_id(db, roll):
    return query(db, "SELECT id FROM students WHERE roll_no = %s", (roll,))[0][0]


def pdf_strings(data):
    """Text drawn on the page: inflate the content streams and collect the (...) string operands."""
    chunks = []
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            chunks.append(zlib.decompress(stream))
        except zlib.error:
            chunks.append(stream)
    return b"".join(re.findall(rb"\(((?:[^()\\]|\\.)*)\)", b"\n".join(chunks))).decode("latin-1")


def assert_pdf(response, roll):
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    disposition = response.headers["Content-Disposition"]
    assert disposition.startswith("attachment")
    assert f'filename="result-{roll}.pdf"' in disposition
    assert response.data.startswith(b"%PDF")
    return pdf_strings(response.data)


# ---------- Student downloads ----------


def test_student_downloads_own_result_pdf(browser):
    browser.login(*STUDENT)
    text = assert_pdf(browser.get("/student/result.pdf"), "241203106130")
    for expected in ("241203106130", "Krishna Kumar Singh", "86.00%", "MINOR PROJECT RESULT CARD", "Generated on"):
        assert expected in text, expected
    assert "no-store" in browser.get("/student/result.pdf").headers["Cache-Control"]


def test_student_pdf_ignores_ids_in_the_url(browser):
    browser.login(*OTHER_STUDENT)
    text = assert_pdf(browser.get("/student/result.pdf?roll_no=241203106130&student_id=1"), "241203106125")
    assert "Krish Pathak" in text
    assert "241203106130" not in text and "Krishna" not in text
    assert browser.get("/student/result.pdf/1").status_code == 404
    assert browser.get("/student/1/result.pdf").status_code == 404


def test_student_cannot_use_staff_download(browser, db):
    sid = student_id(db, "241203106130")
    browser.login(*OTHER_STUDENT)
    response = browser.get(f"/faculty/students/{sid}/result.pdf")
    assert response.status_code == 403
    assert response.mimetype != "application/pdf"


def test_pending_student_gets_no_pdf(browser):
    browser.login(*PENDING_STUDENT)
    for url in ("/student/result.pdf", "/student/result"):
        response = browser.get(url)
        assert response.status_code == 302, url
        assert response.headers["Location"].endswith("/student/")
        assert response.mimetype != "application/pdf"
    html = browser.get("/student/").get_data(as_text=True)
    assert "has not been published yet" in html
    assert "Evaluation in progress" in html
    assert "/student/result.pdf" not in html


def test_anonymous_cannot_download(client, db):
    sid = student_id(db, "241203106130")
    for url in ("/student/result.pdf", "/student/result", f"/faculty/students/{sid}/result.pdf"):
        response = client.get(url)
        assert response.status_code == 302, url
        assert "/login?next=" in response.headers["Location"]


def test_staff_cannot_use_student_download(browser):
    for account in (FACULTY, ADMIN):
        browser.login(*account)
        assert browser.get("/student/result.pdf").status_code == 403
        assert browser.get("/student/result").status_code == 403
        browser.logout()


# ---------- Staff downloads ----------


def test_faculty_downloads_a_students_pdf(browser, db):
    browser.login(*FACULTY)
    text = assert_pdf(browser.get(f"/faculty/students/{student_id(db, '241203106185')}/result.pdf"), "241203106185")
    assert "Pradeep" in text and "75.00%" in text
    pending = browser.get(f"/faculty/students/{student_id(db, '241203106105')}/result.pdf")
    assert pending.status_code == 302
    assert pending.headers["Location"].endswith("/faculty/students")
    assert browser.get("/faculty/students/99999/result.pdf").status_code == 404
    html = browser.get("/faculty/students").get_data(as_text=True)
    assert f"/faculty/students/{student_id(db, '241203106130')}/result.pdf" in html
    assert f"/faculty/students/{student_id(db, '241203106105')}/result.pdf" not in html


def test_admin_downloads_a_students_pdf(browser, db):
    browser.login(*ADMIN)
    assert_pdf(browser.get(f"/faculty/students/{student_id(db, '241203106130')}/result.pdf"), "241203106130")


def test_pdf_follows_updated_result_with_non_ascii_remarks(browser, db):
    sid = student_id(db, "241203106130")
    browser.login(*FACULTY)
    remarks = "Très bien — उत्कृष्ट कार्य “great” work"
    browser.post(f"/faculty/students/{sid}/result", {"marks_obtained": "93", "total_marks": "100", "remarks": remarks})
    browser.logout()
    browser.login(*STUDENT)
    text = assert_pdf(browser.get("/student/result.pdf"), "241203106130")
    assert "93.00%" in text
    assert 'Très bien - ? ? "great" work' in text.replace("\\", "")


# ---------- Pages ----------


def test_dashboard_shows_actions_standing_and_scale(browser):
    browser.login(*STUDENT)
    html = browser.get("/student/").get_data(as_text=True)
    assert 'href="/student/result.pdf"' in html
    assert 'href="/student/result"' in html
    assert "Change password" in html
    assert "4% more would have reached grade A+" in html
    assert 'class="sp-avatar" aria-hidden="true">KS<' in html
    assert "css/student.css" in html


def test_failed_student_dashboard_shows_gap_to_pass(browser):
    browser.login(*FAILED_STUDENT)
    html = browser.get("/student/").get_data(as_text=True)
    assert "5% below the pass mark of 40%" in html
    assert "badge-fail" in html


def test_printable_result_card(browser):
    browser.login(*STUDENT)
    response = browser.get("/student/result")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for expected in ("Minor project result card", "241203106130", "data-print", "computer-generated", "86.00%"):
        assert expected in html, expected
    assert "<script>" not in html


# ---------- Pure helpers (no database) ----------


def test_pdf_text_is_latin1_safe():
    assert pdf_text("Krishna Kumar Singh") == "Krishna Kumar Singh"
    assert pdf_text("Café “quote” – ₹500") == 'Café "quote" - Rs.500'
    assert pdf_text("कृष्ण कुमार") == "? ?"
    assert pdf_text("Ščepán\x00\nŁódź") == "Scepán ?ódz"
    assert pdf_text(None) == ""
    for sample in ("कृष्ण", "李小龍", "😀 emoji", "Ω≈ç√"):
        pdf_text(sample).encode("latin-1")


def test_build_result_card_with_unicode_fields():
    record = {
        "roll_no": "241203106130",
        "student_name": "Krishna Kumar Singh",
        "course": "BCA",
        "company": "ज्ञान Software Lab",
        "topic": "Résumé parser — 日本語 support " * 4,
        "marks_obtained": Decimal("45.5"),
        "total_marks": Decimal("60"),
        "percentage": Decimal("75.83"),
        "grade": "B",
        "remarks": "x" * 255,
        "updated_at": datetime(2026, 11, 1, 9, 30),
        "entered_by_name": None,
        "status": "Pass",
    }
    data = build_result_card(record)
    assert data.startswith(b"%PDF")
    assert len(re.findall(rb"/Type /Page\b", data)) == 1


def test_student_css_uses_tokens_and_no_gradients():
    css = (Path(__file__).parent.parent / "app" / "static" / "css" / "student.css").read_text()
    assert "gradient" not in css
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", css)


def test_safe_filename():
    assert safe_filename("241203106130") == "result-241203106130.pdf"
    assert safe_filename('a"b;c\r\n/..') == "result-abc.pdf"
    assert safe_filename("") == "result-student.pdf"


def test_grade_scale_marks_current_band_and_gap():
    standing = grade_scale(Decimal("86.00"))
    assert [b["grade"] for b in standing["bands"]] == ["F", "D", "C", "B", "A", "A+"]
    assert sum(b["width"] for b in standing["bands"]) == 100
    assert [b["grade"] for b in standing["bands"] if b["current"]] == ["A"]
    assert (standing["next_grade"], standing["gap"]) == ("A+", Decimal("4.00"))
    top = grade_scale(Decimal("100"))
    assert top["next_grade"] is None and top["bands"][-1]["current"]
    assert grade_scale(Decimal("0"))["bands"][0]["current"]
    assert grade_scale(Decimal("40"))["bands"][1]["current"]
    assert not any(b["current"] for b in grade_scale(None)["bands"])
