from decimal import Decimal

import pytest

from app.rules import (
    ValidationError,
    calculate_grade,
    calculate_percentage,
    check_password,
    clean_person_name,
    clean_roll_no,
    format_number,
    parse_marks,
    result_status,
)


@pytest.mark.parametrize(
    ("percentage", "grade", "status"),
    [
        ("100", "A+", "Pass"),
        ("90", "A+", "Pass"),
        ("89.99", "A", "Pass"),
        ("80", "A", "Pass"),
        ("79.99", "B", "Pass"),
        ("70", "B", "Pass"),
        ("69.99", "C", "Pass"),
        ("60", "C", "Pass"),
        ("59.99", "D", "Pass"),
        ("40", "D", "Pass"),
        ("39.99", "F", "Fail"),
        ("0", "F", "Fail"),
    ],
)
def test_grade_band_edges(percentage, grade, status):
    assert calculate_grade(Decimal(percentage)) == grade
    assert result_status(Decimal(percentage)) == status


def test_pending_when_no_result():
    assert result_status(None) == "Pending"


@pytest.mark.parametrize(
    ("marks", "total", "expected", "grade"),
    [("86", "100", "86.00", "A"), ("35", "100", "35.00", "F"), ("45", "60", "75.00", "B"), ("2", "3", "66.67", "C")],
)
def test_presentation_worked_examples(marks, total, expected, grade):
    percentage = calculate_percentage(Decimal(marks), Decimal(total))
    assert percentage == Decimal(expected)
    assert calculate_grade(percentage) == grade


def test_rounding_is_half_up_so_grade_matches_displayed_value():
    percentage = calculate_percentage(Decimal("179.99"), Decimal("200"))  # 89.995
    assert str(percentage) == "90.00"
    assert calculate_grade(percentage) == "A+"


@pytest.mark.parametrize(
    ("marks", "total", "message"),
    [
        ("101", "100", "cannot be more than"),
        ("5", "0", "greater than 0"),
        ("-1", "100", "cannot be negative"),
        ("abc", "100", "must be a number"),
        ("nan", "100", "finite"),
        ("inf", "100", "finite"),
        ("50", "Infinity", "finite"),
        ("", "100", "required"),
        ("50.123", "100", "two decimal places"),
        ("50", "5000", "cannot exceed"),
    ],
)
def test_invalid_marks_rejected(marks, total, message):
    with pytest.raises(ValidationError, match=message):
        parse_marks(marks, total)


def test_valid_marks_parsed():
    assert parse_marks(" 45.5 ", "60") == (Decimal("45.5"), Decimal("60"))
    assert parse_marks("0", "100") == (Decimal("0"), Decimal("100"))
    assert parse_marks("100", "100") == (Decimal("100"), Decimal("100"))


def test_format_number():
    assert format_number(Decimal("86.00")) == "86"
    assert format_number(Decimal("100.00")) == "100"
    assert format_number(Decimal("45.50")) == "45.5"
    assert format_number(None) == ""


def test_roll_no_and_name_validation():
    assert clean_roll_no(" 241203106130 ") == "241203106130"
    assert clean_roll_no("bca-01") == "BCA-01"
    for bad in ["", "ab", "12 34", "x" * 21, "1/2/3", "<script>"]:
        with pytest.raises(ValidationError):
            clean_roll_no(bad)
    assert clean_person_name("  Krishna   Kumar Singh ") == "Krishna Kumar Singh"
    with pytest.raises(ValidationError):
        clean_person_name("R2D2")


def test_password_rules():
    assert check_password("Secret@123", "Secret@123") == "Secret@123"
    with pytest.raises(ValidationError, match="at least 8"):
        check_password("short")
    with pytest.raises(ValidationError, match="do not match"):
        check_password("Secret@123", "Secret@124")


def test_safe_local_path():
    from app.auth import safe_local_path

    assert safe_local_path("/notifications?show=unread") == "/notifications?show=unread"
    for bad in (None, "", "//evil.com", "/\\evil.com", "/\t/evil.com", "https://evil.com", "evil.com", "/a\\b"):
        assert safe_local_path(bad) is None, bad
