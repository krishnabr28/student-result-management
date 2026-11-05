"""Builds the downloadable PDF result card with fpdf2 (pure Python, no system libraries)."""

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from flask import Response
from fpdf import FPDF
from fpdf.enums import TableCellFillMode
from fpdf.fonts import FontFace

from .rules import GRADE_BANDS, PASS_PERCENTAGE, format_number

SESSION = "2026-2027"
INSTITUTE = "GNIOT Institute of Professional Studies, Greater Noida"
UNIVERSITY = "Affiliated to Chaudhary Charan Singh University (CCSU), Meerut"
IMG_DIR = Path(__file__).parent / "static" / "img"

INK = (24, 24, 27)
MUTED = (91, 91, 102)
RULE = (212, 212, 216)
SHADE = (244, 244, 245)
ACCENT = (194, 65, 12)
ACCENT_SHADE = (255, 237, 224)
WHITE = (255, 255, 255)
STATUS_INK = {"Pass": (21, 128, 61), "Fail": (185, 28, 28)}
STATUS_SHADE = {"Pass": (220, 252, 231), "Fail": (254, 226, 226)}

_PUNCTUATION = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "...",
        "•": "-",
        "₹": "Rs.",
        " ": " ",
    }
)


def pdf_text(value):
    """Core PDF fonts are Latin-1 only: transliterate what we can, replace each other run of characters with '?'."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value if value is not None else "")).translate(_PUNCTUATION)
    out = []
    for ch in text:
        if ord(ch) < 256:
            out.append(ch)
            continue
        folded = unicodedata.normalize("NFKD", ch).encode("latin-1", "ignore").decode("latin-1")
        if folded:
            out.append(folded)
        elif not out or out[-1] != "?":
            out.append("?")
    return "".join(out)


def safe_filename(roll_no):
    return f"result-{re.sub(r'[^A-Za-z0-9-]', '', roll_no or '') or 'student'}.pdf"


def _local(value):
    return value.replace(tzinfo=timezone.utc).astimezone() if value.tzinfo is None else value.astimezone()


def _when(value):
    return _local(value).strftime("%d %b %Y, %I:%M %p")


class _ResultCard(FPDF):
    generated = ""

    def header(self):
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.8)
        self.rect(8, 8, self.w - 16, self.h - 16)
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.rect(10, 10, self.w - 20, self.h - 20)

    def footer(self):
        self.set_y(-27)
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2.5)
        self.set_text_color(*MUTED)
        self.set_font("Helvetica", "", 8)
        self.multi_cell(
            0,
            4,
            "This is a computer-generated result card from the Student Result Management System and does not "
            "require a signature. Marks are shown as published by the evaluating faculty.",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.cell(0, 4, f"Generated on {self.generated}  |  Page {self.page_no()}", align="C")


def _section_title(pdf, text):
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*ACCENT)
    pdf.set_char_spacing(0.6)
    pdf.cell(0, 5, text.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.ln(1)
    pdf.set_text_color(*INK)
    pdf.set_draw_color(*RULE)
    pdf.set_fill_color(*WHITE)
    pdf.set_line_width(0.2)


def _letterhead(pdf):
    top = 14
    pdf.image(str(IMG_DIR / "gips.png"), x=pdf.l_margin, y=top, h=16)
    pdf.image(str(IMG_DIR / "ccsu.png"), x=pdf.w - pdf.r_margin - 16, y=top, h=16)
    pdf.set_y(top + 18)
    pdf.set_font("Helvetica", "B", 13.5)
    pdf.set_text_color(*INK)
    pdf.cell(0, 6.5, INSTITUTE, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, UNIVERSITY, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    y = pdf.get_y()
    pdf.set_fill_color(*ACCENT)
    pdf.rect(pdf.l_margin, y, pdf.epw, 9.5, style="F")
    pdf.set_xy(pdf.l_margin, y)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_char_spacing(1.2)
    pdf.cell(0, 9.5, "MINOR PROJECT RESULT CARD", align="C")
    pdf.set_char_spacing(0)
    pdf.set_y(y + 11)
    pdf.set_text_color(*MUTED)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 4.5, f"Academic session {SESSION}", align="C")
    pdf.ln(4)


def _details(pdf, record):
    _section_title(pdf, "Student details")
    label = FontFace(emphasis="BOLD", color=MUTED, fill_color=SHADE, size_pt=8.5)
    value = FontFace(emphasis="BOLD", color=INK, fill_color=WHITE, size_pt=10)
    rows = [
        ("Name of student", record["student_name"], "Roll number", record["roll_no"]),
        ("Course", record["course"], "Session", SESSION),
        ("Company / organisation", record["company"], None, None),
        ("Project topic", record["topic"], None, None),
    ]
    with pdf.table(
        col_widths=(44, 62, 28, 44),
        first_row_as_headings=False,
        line_height=5.2,
        padding=(1.4, 2.5),
        borders_layout="ALL",
        v_align="M",
    ) as table:
        for a_label, a_value, b_label, b_value in rows:
            row = table.row()
            row.cell(a_label, style=label)
            if b_label is None:
                row.cell(pdf_text(a_value), style=value, colspan=3)
            else:
                row.cell(pdf_text(a_value), style=value)
                row.cell(b_label, style=label)
                row.cell(pdf_text(b_value), style=value)


def _summary(pdf, record):
    _section_title(pdf, "Result summary")
    status = record["status"]
    tiles = [
        ("Marks obtained", f"{format_number(record['marks_obtained'])} / {format_number(record['total_marks'])}"),
        ("Percentage", f"{record['percentage']}%"),
        ("Grade", record["grade"]),
        ("Result", status.upper()),
    ]
    gap = 4
    width = (pdf.epw - gap * (len(tiles) - 1)) / len(tiles)
    y = pdf.get_y()
    for index, (caption, text) in enumerate(tiles):
        x = pdf.l_margin + index * (width + gap)
        is_status = caption == "Result"
        pdf.set_fill_color(*(STATUS_SHADE.get(status, SHADE) if is_status else SHADE))
        pdf.set_draw_color(*(STATUS_INK.get(status, RULE) if is_status else RULE))
        pdf.set_line_width(0.3 if is_status else 0.2)
        pdf.rect(x, y, width, 19, style="DF", round_corners=True, corner_radius=2)
        pdf.set_xy(x, y + 3)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.set_char_spacing(0.4)
        pdf.cell(width, 4, caption.upper(), align="C")
        pdf.set_char_spacing(0)
        pdf.set_xy(x, y + 8)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*(STATUS_INK.get(status, INK) if is_status else INK))
        pdf.cell(width, 9, pdf_text(text), align="C")
    pdf.set_y(y + 19)


def _marks(pdf, record):
    _section_title(pdf, "Statement of marks")
    head = FontFace(emphasis="BOLD", color=INK, fill_color=SHADE, size_pt=8.5)
    body = FontFace(color=INK, fill_color=WHITE, size_pt=9.5)
    strong = FontFace(emphasis="BOLD", color=INK, fill_color=SHADE, size_pt=9.5)
    with pdf.table(
        col_widths=(12, 72, 22, 28, 26, 18),
        headings_style=head,
        line_height=5,
        padding=(1.5, 2),
        text_align=("CENTER", "LEFT", "CENTER", "CENTER", "CENTER", "CENTER"),
        borders_layout="ALL",
        v_align="M",
    ) as table:
        table.row(["S.No.", "Assessment", "Max. marks", "Marks obtained", "Percentage", "Grade"])
        row = table.row()
        for text in (
            "1",
            pdf_text(f"Minor project: {record['topic']}"),
            format_number(record["total_marks"]),
            format_number(record["marks_obtained"]),
            f"{record['percentage']}%",
            record["grade"],
        ):
            row.cell(text, style=body)
        row = table.row()
        row.cell("Total", style=strong, colspan=2, align="RIGHT")
        row.cell(format_number(record["total_marks"]), style=strong)
        row.cell(format_number(record["marks_obtained"]), style=strong)
        row.cell(f"{record['percentage']}%", style=strong)
        row.cell(record["grade"], style=strong)


def _remarks(pdf, record):
    _section_title(pdf, "Faculty remarks")
    pdf.set_font("Helvetica", "I" if record["remarks"] else "", 10)
    pdf.set_text_color(*(INK if record["remarks"] else MUTED))
    pdf.multi_cell(
        0,
        5.2,
        pdf_text(record["remarks"]) if record["remarks"] else "No remarks were recorded.",
        border=1,
        padding=(2.5, 4),
        new_x="LMARGIN",
        new_y="NEXT",
    )


def _scale_and_evaluation(pdf, record):
    _section_title(pdf, "Grading scale and evaluation")
    top = pdf.get_y()
    head = FontFace(emphasis="BOLD", color=INK, fill_color=SHADE, size_pt=8.5)
    body = FontFace(color=INK, fill_color=WHITE, size_pt=9)
    current = FontFace(emphasis="BOLD", color=ACCENT, fill_color=ACCENT_SHADE, size_pt=9)
    bands = [(f"{format_number(minimum)}% and above", grade, "Pass") for minimum, grade in GRADE_BANDS]
    bands.append((f"Below {format_number(PASS_PERCENTAGE)}%", "F", "Fail"))
    scale_width = 96
    with pdf.table(
        width=scale_width,
        align="LEFT",
        col_widths=(48, 22, 26),
        headings_style=head,
        line_height=4.6,
        padding=(0.7, 2),
        text_align=("LEFT", "CENTER", "CENTER"),
        borders_layout="HORIZONTAL_LINES",
        cell_fill_mode=TableCellFillMode.NONE,
    ) as table:
        table.row(["Percentage", "Grade", "Result"])
        for band in bands:
            table.row(band, style=current if band[1] == record["grade"] else body)
    bottom = pdf.get_y()

    x = pdf.l_margin + scale_width + 8
    width = pdf.w - pdf.r_margin - x
    pdf.set_xy(x, top)
    facts = [
        ("Evaluated by", record.get("entered_by_name") or "Department faculty"),
        ("Result published / last updated", _when(record["updated_at"])),
        ("Pass requirement", f"{format_number(PASS_PERCENTAGE)}% of total marks"),
        ("Document reference", f"SRMS/{SESSION}/{record['roll_no']}"),
    ]
    for caption, text in facts:
        pdf.set_x(x)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.set_char_spacing(0.3)
        pdf.cell(width, 4, caption.upper(), new_x="LEFT", new_y="NEXT")
        pdf.set_char_spacing(0)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*INK)
        pdf.multi_cell(width, 5, pdf_text(text), new_x="LEFT", new_y="NEXT")
        pdf.ln(2)
    pdf.set_y(max(bottom, pdf.get_y()))


def build_result_card(record, generated_at=None):
    """Return the PDF bytes for one published result (record has the columns of the student/result join)."""
    if record.get("percentage") is None:
        raise ValueError("Result is not published yet.")
    pdf = _ResultCard(orientation="P", unit="mm", format="A4")
    pdf.generated = _when(generated_at or datetime.now(timezone.utc))
    pdf.set_margins(16, 14, 16)
    pdf.set_auto_page_break(True, margin=30)
    pdf.set_title(pdf_text(f"Result card - {record['student_name']} ({record['roll_no']})"))
    pdf.set_author(pdf_text(INSTITUTE))
    pdf.set_creator("Student Result Management System")
    pdf.add_page()
    _letterhead(pdf)
    _details(pdf, record)
    _summary(pdf, record)
    _marks(pdf, record)
    _remarks(pdf, record)
    _scale_and_evaluation(pdf, record)
    return bytes(pdf.output())


def pdf_response(record):
    return Response(
        build_result_card(record),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename(record["roll_no"])}"'},
    )
