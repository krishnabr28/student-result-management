"""Business rules and input validation. Plain functions, so they are tested without the GUI or database."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

PASS_PERCENTAGE = Decimal("40")
MAX_TOTAL_MARKS = Decimal("1000")
GRADE_BANDS = (
    (Decimal("90"), "A+"),
    (Decimal("80"), "A"),
    (Decimal("70"), "B"),
    (Decimal("60"), "C"),
    (Decimal("40"), "D"),
)
TWO_PLACES = Decimal("0.01")

ROLL_NO_RE = re.compile(r"^[A-Za-z0-9-]{3,20}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,50}$")
PERSON_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,99}$")
MIN_PASSWORD_LENGTH = 8


class ValidationError(ValueError):
    pass


def calculate_percentage(marks, total):
    """Percentage rounded half-up to two decimals, so the grade always matches the shown value."""
    marks, total = Decimal(marks), Decimal(total)
    return (marks / total * 100).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_grade(percentage):
    percentage = Decimal(percentage)
    for minimum, grade in GRADE_BANDS:
        if percentage >= minimum:
            return grade
    return "F"


def result_status(percentage):
    if percentage is None:
        return "Pending"
    return "Pass" if Decimal(percentage) >= PASS_PERCENTAGE else "Fail"


def format_number(value):
    """86.00 -> '86', 45.50 -> '45.5'."""
    if value is None:
        return ""
    return format(Decimal(value).normalize(), "f")


def _parse_number(text, label):
    text = (text or "").strip()
    if not text:
        raise ValidationError(f"{label} is required.")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValidationError(f"{label} must be a number.") from None
    if not value.is_finite():
        raise ValidationError(f"{label} must be a finite number.")
    if value.as_tuple().exponent < -2:
        raise ValidationError(f"{label} can have at most two decimal places.")
    return value


def parse_marks(marks_text, total_text):
    """Validate form input and return (marks, total) as Decimals."""
    total = _parse_number(total_text, "Total marks")
    marks = _parse_number(marks_text, "Marks obtained")
    if total <= 0:
        raise ValidationError("Total marks must be greater than 0.")
    if total > MAX_TOTAL_MARKS:
        raise ValidationError(f"Total marks cannot exceed {MAX_TOTAL_MARKS}.")
    if marks < 0:
        raise ValidationError("Marks obtained cannot be negative.")
    if marks > total:
        raise ValidationError("Marks obtained cannot be more than total marks.")
    return marks, total


def clean_text(value, label, *, min_len=1, max_len=100, required=True):
    value = " ".join((value or "").split())
    if not value:
        if required:
            raise ValidationError(f"{label} is required.")
        return ""
    if len(value) < min_len:
        raise ValidationError(f"{label} must be at least {min_len} characters.")
    if len(value) > max_len:
        raise ValidationError(f"{label} must be at most {max_len} characters.")
    return value


def clean_roll_no(value):
    value = (value or "").strip().upper()
    if not ROLL_NO_RE.match(value):
        raise ValidationError("Roll number must be 3-20 letters, digits or '-'.")
    return value


def clean_username(value):
    value = (value or "").strip().lower()
    if not USERNAME_RE.match(value):
        raise ValidationError("Username must be 3-50 letters, digits, '.', '_' or '-'.")
    return value


def clean_person_name(value, label="Name"):
    value = clean_text(value, label, min_len=2, max_len=100)
    if not PERSON_NAME_RE.match(value):
        raise ValidationError(f"{label} can contain only letters, spaces, '.', ' and -.")
    return value


def check_password(password, confirm=None):
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > 128:
        raise ValidationError("Password must be at most 128 characters.")
    if confirm is not None and password != confirm:
        raise ValidationError("Passwords do not match.")
    return password
