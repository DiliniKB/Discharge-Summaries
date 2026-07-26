"""Read-only rendering of a full Summary record — shared by Advanced
Search's inline quick-view panel and the bigger Full View dialog
(app/ui/dialogs/summary_full_view.py), so there's exactly one place that
knows how to lay this out. Blank fields are omitted entirely rather than
shown as "—" — same "omit if nothing to show" rule the printed card
already follows (app/printing/layout.py).
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app import theme
from app.printing import layout as print_layout
from app.ui.widgets.labeled import LabeledField
from app.util.attachments import (
    AttachmentMissingError,
    AttachmentOpenUnsupportedError,
    format_size,
    open_attachment_file,
)

_ADMISSION_TEXT_FIELDS = [
    ("Telephone", "telephone"),
    ("Blood Group", "blood_group"),
]


def _add_field(scroll_frame, label, value):
    if not value:
        return
    value_label = QLabel(str(value))
    value_label.setWordWrap(True)
    scroll_frame.add_widget(LabeledField(label, value_label))


def _add_section_header(scroll_frame, heading):
    header = QLabel(heading)
    header.setObjectName("SectionHeader")
    scroll_frame.add_widget(header)


def populate_summary_view(scroll_frame, summary, investigations, doctors_by_id, attachments=()):
    """Clears nothing — caller is responsible for starting from an empty
    scroll_frame.body_layout (ScrollFrame.add_widget only ever appends)."""
    name_label = QLabel(summary.patient_name or "(unnamed)")
    name_label.setObjectName("PatientName")
    name_label.setWordWrap(True)
    scroll_frame.add_widget(name_label)

    age_sex = f"{summary.age}{(summary.sex or '')[:1]}" if summary.age else (summary.sex or "")
    identity_bits = [b for b in [age_sex, f"BHT {summary.bht_number or '—'}"] if b]
    if summary.ward:
        identity_bits.append(f"Ward {summary.ward}")
    identity_label = QLabel(" · ".join(identity_bits))
    identity_label.setObjectName("Muted")
    scroll_frame.add_widget(identity_label)

    attribution_bits = []
    creator = doctors_by_id.get(summary.created_by)
    if creator:
        attribution_bits.append(f"Created by {creator.name} · {_format_timestamp(summary.created_at)}")
    last_editor = doctors_by_id.get(summary.last_edited_by)
    if last_editor:
        attribution_bits.append(f"Last edited by {last_editor.name} · {_format_timestamp(summary.updated_at)}")
    if attribution_bits:
        attribution_label = QLabel("   ·   ".join(attribution_bits))
        attribution_label.setObjectName("Muted")
        attribution_label.setWordWrap(True)
        scroll_frame.add_widget(attribution_label)

    _add_section_header(scroll_frame, "ADMISSION")
    for label, attr in _ADMISSION_TEXT_FIELDS:
        _add_field(scroll_frame, label, getattr(summary, attr))
    _add_field(scroll_frame, "Admission Date", print_layout.format_date(summary.date_admission))
    _add_field(scroll_frame, "Surgery Date", print_layout.format_date(summary.date_surgery))
    _add_field(scroll_frame, "Discharge Date", print_layout.format_date(summary.date_discharge))

    _add_section_header(scroll_frame, "PROCEDURE")
    if summary.procedure_title:
        title_label = QLabel(summary.procedure_title.upper())
        title_label.setObjectName("ProcedureTitle")
        title_label.setWordWrap(True)
        scroll_frame.add_widget(title_label)
    for label, attr, _preserve in print_layout.DETAIL_FIELDS:
        _add_field(scroll_frame, label, getattr(summary, attr))

    _add_section_header(scroll_frame, "CLINICAL HISTORY")
    if print_layout.has_clinical_history(summary):
        for label, attr in print_layout.CLINICAL_HISTORY_FIELDS:
            _add_field(scroll_frame, label, getattr(summary, attr))
    else:
        empty_label = QLabel("No clinical history recorded.")
        empty_label.setObjectName("Muted")
        scroll_frame.add_widget(empty_label)

    _add_section_header(scroll_frame, "INVESTIGATIONS & MANAGEMENT")
    investigations_text = print_layout.format_investigations(investigations)
    if investigations_text or summary.management or summary.histology_report:
        _add_field(scroll_frame, "Investigations", investigations_text)
        for label, attr, _preserve in print_layout.TAIL_FIELDS:
            _add_field(scroll_frame, label, getattr(summary, attr))
    else:
        empty_label = QLabel("No investigations or management recorded.")
        empty_label.setObjectName("Muted")
        scroll_frame.add_widget(empty_label)

    # Omitted entirely when there are none, same rule as every other
    # section here — a record with no files shouldn't show an empty
    # "ATTACHMENTS" heading followed by nothing.
    if attachments:
        _add_section_header(scroll_frame, "ATTACHMENTS")
        for attachment in attachments:
            scroll_frame.add_widget(_build_attachment_row(attachment))


def _build_attachment_row(attachment):
    """filename · size, plus an Open button that hands off to the OS's
    default viewer (app/util/attachments.py) — no in-app preview to
    build or maintain, same choice as app/ui/sections/attachments.py's
    editor row. Read-only view, so no remove button here."""
    wrap = QWidget()
    wrap_layout = QVBoxLayout(wrap)
    wrap_layout.setContentsMargins(0, 0, 0, 0)
    wrap_layout.setSpacing(theme.SPACING_UNIT)

    top_row = QHBoxLayout()
    top_row.setContentsMargins(0, 0, 0, 0)
    top_row.setSpacing(theme.FIELD_GAP)
    text_label = QLabel(f"{attachment.filename}  ·  {format_size(attachment.size_bytes)}")
    text_label.setWordWrap(True)
    top_row.addWidget(text_label, stretch=1)

    error_label = QLabel("")
    error_label.setObjectName("Danger")
    error_label.setWordWrap(True)
    error_label.setVisible(False)

    open_button = QPushButton("Open")
    open_button.setObjectName("SecondaryCompact")
    open_button.clicked.connect(lambda: _open_attachment(error_label, attachment))
    top_row.addWidget(open_button)

    wrap_layout.addLayout(top_row)
    wrap_layout.addWidget(error_label)
    return wrap


def _open_attachment(error_label, attachment):
    error_label.setVisible(False)
    try:
        open_attachment_file(attachment.stored_path)
    except (AttachmentMissingError, AttachmentOpenUnsupportedError) as e:
        error_label.setText(str(e))
        error_label.setVisible(True)


def _format_timestamp(iso_timestamp):
    """Full ISO datetime -> 'DD/MM/YYYY HH:MM'. Blank -> ''."""
    if not iso_timestamp:
        return ""
    date_part, _, time_part = iso_timestamp.partition("T")
    y, m, d = date_part.split("-")
    hh_mm = time_part[:5]
    return f"{d}/{m}/{y} {hh_mm}"
