"""The A4 discharge card. See docs/print-layout.md — "the deliverable that
matters" (CLAUDE.md).

Pure helper functions (format_date, format_investigations, etc.) are kept
separate from PDF assembly so the logic is directly unit-testable without
rendering a PDF — matches docs/print-layout.md's own testing section more
naturally than asserting on rendered output alone.

Field row order follows docs/print-layout.md's field-mapping table
EXACTLY, including a subtlety worth flagging: `findings` sits on its own
row right after Procedure, separate from the 5-field group (Presenting
Complaint, Past Medical History, Past Surgical History, Allergies,
Examination) that the "omit entirely if all blank" rule applies to — the
paper form's row order, confirmed against the doc, not the UI's grouping
(app/ui/sections/clinical_history.py groups all 6 together for UI
convenience; print must not reorder the paper form).

KeepTogether isn't wrapped around individual rows: ReportLab's Table
splits only at row boundaries by default, never mid-row, so "never split
a label row from its value" (docs/print-layout.md "Overflow") is already
guaranteed by using one Table with label+value as two cells in the same
row — nothing extra needed for that specific rule.
"""

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PAGE_SIZE = A4
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 15 * mm
LABEL_COL_WIDTH = 34 * mm
BODY_FONT_SIZE = 9.5
HEADING_FONT_SIZE = 11
LINE_SPACING = 1.45

GREY_FILL = colors.Color(0.90, 0.90, 0.90)
BORDER_COLOR = colors.black
HEADER_BAND_HEIGHT = 10 * mm

UNIT_NAME = "SURGICAL ONCOLOGY UNIT — TEACHING HOSPITAL, KURUNEGALA"

# (print label, Summary attribute) — order matches docs/print-layout.md exactly.
DETAIL_FIELDS = [
    ("Surgical team", "surgical_team", False),
    ("Indication", "indication", False),
    ("Procedure", "procedure_steps", True),  # True = preserve line breaks
    ("Findings", "findings", False),
]
CLINICAL_HISTORY_FIELDS = [
    ("Presenting Complaint", "presenting_complaint"),
    ("Past Medical History", "past_medical_history"),
    ("Past Surgical History", "past_surgical_history"),
    ("Allergies", "allergies"),
    ("Examination", "examination"),
]
TAIL_FIELDS = [
    ("Management", "management", True),
    ("Histology Report", "histology_report", False),
]


def format_date(iso_date):
    """ISO YYYY-MM-DD -> DD/MM/YYYY. Blank/None -> ''."""
    if not iso_date:
        return ""
    y, m, d = iso_date.split("-")
    return f"{d}/{m}/{y}"


def format_investigations(investigations):
    """[{'label':.., 'value':.., 'unit':..}, ...] -> 'FBS 86 · SCr 40 · ...',
    blank values skipped entirely. docs/print-layout.md divergence #3."""
    parts = []
    for row in investigations:
        value = (row.get("value") or "").strip()
        if not value:
            continue
        parts.append(f"{row['label']} {value}")
    return " · ".join(parts)


def has_clinical_history(summary):
    """Whether the 5-field group (NOT including Findings, which prints on
    its own row regardless) has anything to show at all."""
    return any(getattr(summary, attr).strip() for _, attr in CLINICAL_HISTORY_FIELDS if getattr(summary, attr))


def _para_text(value, preserve_linebreaks=False):
    text = xml_escape(value or "")
    if preserve_linebreaks:
        text = text.replace("\n", "<br/>")
    return text


def _styles():
    return {
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=BODY_FONT_SIZE, leading=BODY_FONT_SIZE * LINE_SPACING),
        "label": ParagraphStyle("label", fontName="Helvetica", fontSize=BODY_FONT_SIZE, leading=BODY_FONT_SIZE * LINE_SPACING),
        "band": ParagraphStyle("band", fontName="Helvetica-Bold", fontSize=HEADING_FONT_SIZE, alignment=TA_CENTER),
        "cell_center": ParagraphStyle("cell_center", fontName="Helvetica-Bold", fontSize=BODY_FONT_SIZE, alignment=TA_CENTER),
        "heading": ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=HEADING_FONT_SIZE, leading=HEADING_FONT_SIZE * LINE_SPACING, alignment=TA_CENTER),
        "signature": ParagraphStyle("signature", fontName="Helvetica", fontSize=BODY_FONT_SIZE, leading=BODY_FONT_SIZE * LINE_SPACING, alignment=TA_RIGHT),
    }


def _identity_table(summary, styles):
    content_width = PAGE_WIDTH - 2 * MARGIN
    value_col = (content_width - 2 * LABEL_COL_WIDTH) / 2

    def label(text):
        return Paragraph(_para_text(text), styles["label"])

    def value(text):
        return Paragraph(_para_text(text), styles["body"])

    rows = [
        [label("Name"), value(summary.patient_name), label("Date of admission"), value(format_date(summary.date_admission))],
        [label("Telephone"), value(summary.telephone), label("Date of discharge"), value(format_date(summary.date_discharge))],
        [label("Age"), value(str(summary.age) if summary.age is not None else ""), label("Date of surgery"), value(format_date(summary.date_surgery))],
        [label("Sex"), value(summary.sex), label("Blood group"), value(summary.blood_group)],
        [label("BHT number"), value(summary.bht_number), "", ""],
    ]
    table = Table(rows, colWidths=[LABEL_COL_WIDTH, value_col, LABEL_COL_WIDTH, value_col])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), GREY_FILL),
                ("BACKGROUND", (2, 0), (2, -1), GREY_FILL),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


_MAX_CHARS_PER_ROW_CHUNK = 2000
# ReportLab's Table splits BETWEEN rows, never within one — confirmed
# empirically: a single row needing 2 pages splits fine, but a row so
# long it would need 3+ pages raises LayoutError instead of splitting
# further. A real clinical note (e.g. a long histology report) can
# plausibly exceed that. This value is generous enough that normal-length
# fields never chunk (verified: the "forces a second page" scenario stays
# a single chunk, unchanged), it only engages for genuinely excessive text.


def _chunk_long_text(text, max_chars=_MAX_CHARS_PER_ROW_CHUNK):
    """Splits text at paragraph/word boundaries into pieces short enough
    that no single table row can ever exceed one page's height."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n", 0, max_chars)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, max_chars)
        if split_at == -1:
            split_at = max_chars
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n ")
    if remaining:
        chunks.append(remaining)
    return chunks


def _detail_rows(summary, investigations):
    """Returns [(label, value_text, preserve_linebreaks), ...] in the
    exact print-layout.md field order. A field long enough to risk the
    single-row page limit (see _chunk_long_text) becomes multiple rows,
    label shown only on the first — still one logical field, just safe
    to render at any length."""
    rows = []

    def add_field(label, text, preserve):
        for i, chunk in enumerate(_chunk_long_text(text or "")):
            rows.append((label if i == 0 else "", chunk, preserve))

    for label, attr, preserve in DETAIL_FIELDS:
        add_field(label, getattr(summary, attr), preserve)

    if has_clinical_history(summary):
        for label, attr in CLINICAL_HISTORY_FIELDS:
            add_field(label, getattr(summary, attr), False)

    add_field("Investigations", format_investigations(investigations), False)

    for label, attr, preserve in TAIL_FIELDS:
        add_field(label, getattr(summary, attr), preserve)

    return rows


def _detail_table(summary, investigations, styles):
    content_width = PAGE_WIDTH - 2 * MARGIN
    value_col = content_width - LABEL_COL_WIDTH

    def label(text):
        return Paragraph(_para_text(text), styles["label"])

    def value(text, preserve):
        return Paragraph(_para_text(text, preserve_linebreaks=preserve), styles["body"])

    rows = [[label(lbl), value(val, preserve)] for lbl, val, preserve in _detail_rows(summary, investigations)]
    table = Table(rows, colWidths=[LABEL_COL_WIDTH, value_col])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), GREY_FILL),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


class _NumberedCanvas(Canvas):
    """Buffers pages, then redraws with the real total page count once
    known — a single ReportLab pass can't know "Page X of Y" upfront."""

    def __init__(self, *args, printed_at="", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self._printed_at = printed_at

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total_pages)
            self._draw_header_band()
            Canvas.showPage(self)
        Canvas.save(self)

    def _draw_footer(self, total_pages):
        self.setFont("Helvetica", 8)
        self.drawString(MARGIN, 10 * mm, f"Printed on {self._printed_at}")
        self.drawRightString(PAGE_WIDTH - MARGIN, 10 * mm, f"Page {self.getPageNumber()} of {total_pages}")

    def _draw_header_band(self):
        # Repeats on every page, including overflow pages — docs/print-layout.md "Overflow".
        band_top = PAGE_HEIGHT - MARGIN
        band_bottom = band_top - HEADER_BAND_HEIGHT
        self.setLineWidth(0.5)
        self.rect(MARGIN, band_bottom, PAGE_WIDTH - 2 * MARGIN, HEADER_BAND_HEIGHT)
        self.setFont("Helvetica-Bold", HEADING_FONT_SIZE)
        self.drawCentredString(PAGE_WIDTH / 2, band_bottom + HEADER_BAND_HEIGHT / 2 - 4, UNIT_NAME)


def render_summary(summary, investigations, doctor, output_dir):
    """Renders the discharge card to a PDF file in output_dir (a temp
    directory — CLAUDE.md: generate to a temp file, not in memory).
    Returns the Path to the generated file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"discharge_summary_{summary.id}.pdf"

    styles = _styles()
    printed_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + HEADER_BAND_HEIGHT + 4 * mm,
        bottomMargin=MARGIN + 6 * mm,  # room for the footer band drawn below the frame
        pageCompression=0,  # keeps text searchable in the raw file — see docs/print-layout.md testing section
    )

    story = []

    ward = summary.ward or ""
    header_row = Table(
        [[Paragraph(_para_text("DISCHARGE SUMMARY"), styles["cell_center"]), Paragraph(_para_text(f"WARD {ward}"), styles["cell_center"])]],
        colWidths=[(PAGE_WIDTH - 2 * MARGIN) * 0.7, (PAGE_WIDTH - 2 * MARGIN) * 0.3],
    )
    header_row.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(header_row)
    story.append(Spacer(1, 4 * mm))

    story.append(_identity_table(summary, styles))
    story.append(Spacer(1, 5 * mm))

    title = (summary.procedure_title or "").upper()
    story.append(Paragraph(_para_text(title), styles["heading"]))
    story.append(Spacer(1, 5 * mm))

    story.append(_detail_table(summary, investigations, styles))
    story.append(Spacer(1, 10 * mm))

    if doctor is not None:
        story.append(Paragraph("_" * 30, styles["signature"]))
        story.append(Paragraph(_para_text(doctor.name), styles["signature"]))
        story.append(Paragraph(_para_text(doctor.designation), styles["signature"]))

    def _on_page(canvas, _doc):
        pass  # header band + footer are drawn once per page in _NumberedCanvas.save(), not here

    doc.build(
        story,
        onFirstPage=_on_page,
        onLaterPages=_on_page,
        canvasmaker=lambda *a, **kw: _NumberedCanvas(*a, printed_at=printed_at, **kw),
    )

    return pdf_path
