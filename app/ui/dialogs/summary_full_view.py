"""Full View — a bigger, visually organized popup for a record's full
detail, alongside Advanced Search's compact inline quick-view panel
(app/ui/widgets/summary_view.py).

Deliberately does NOT reuse that shared renderer — the quick-view panel
is built for a narrow sidebar glance (flat, compact, instant); this is a
dedicated detail screen and earns real visual hierarchy: a hero identity
header, card-grouped sections (mirroring the editor's own collapsible
sections), and a prominent allergy alert — the one thing on a discharge
summary that's genuinely safety-critical to flag, not just another field
in a list (docs/decisions.md).
"""

from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app import theme
from app.printing import layout as print_layout
from app.ui.widgets.labeled import LabeledField
from app.ui.widgets.scrollframe import ScrollFrame
from app.ui.widgets.summary_view import _build_attachment_row


class SummaryFullViewDialog(QDialog):
    def __init__(self, summary, investigations, doctors_by_id, attachments=(), parent=None):
        super().__init__(parent)
        self.setWindowTitle(summary.patient_name or "Full View")
        self.resize(760, 820)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING
        )
        layout.setSpacing(theme.FIELD_GAP)

        scroll = ScrollFrame()
        layout.addWidget(scroll, stretch=1)

        scroll.add_widget(self._build_hero(summary, doctors_by_id))

        # The one deliberately loud element on the page — allergy status
        # is the single most safety-critical thing a doctor scanning a
        # discharge summary needs to not miss.
        if summary.allergies:
            scroll.add_widget(self._build_allergy_alert(summary.allergies))

        scroll.add_widget(self._build_admission_card(summary))
        scroll.add_widget(self._build_procedure_card(summary))
        history_card = self._build_clinical_history_card(summary)
        if history_card is not None:
            scroll.add_widget(history_card)
        scroll.add_widget(self._build_investigations_card(summary, investigations))
        if attachments:
            scroll.add_widget(self._build_attachments_card(attachments))

        close_button = QPushButton("Close")
        close_button.setObjectName("Secondary")
        close_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    # --- Sections ---------------------------------------------------

    def _build_hero(self, summary, doctors_by_id):
        card = QFrame()
        card.setObjectName("HeroCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING
        )
        card_layout.setSpacing(theme.SPACING_UNIT * 2)

        name_label = QLabel(summary.patient_name or "(unnamed)")
        name_label.setObjectName("HeroName")
        name_label.setWordWrap(True)
        card_layout.addWidget(name_label)

        age_sex = f"{summary.age}{(summary.sex or '')[:1]}" if summary.age else (summary.sex or "")
        identity_bits = [b for b in [age_sex, f"BHT {summary.bht_number or '—'}"] if b]
        if summary.ward:
            identity_bits.append(f"Ward {summary.ward}")
        if summary.date_discharge:
            identity_bits.append(f"Discharged {print_layout.format_date(summary.date_discharge)}")
        identity_label = QLabel(" · ".join(identity_bits))
        identity_label.setObjectName("Muted")
        card_layout.addWidget(identity_label)

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
            card_layout.addWidget(attribution_label)

        return card

    def _build_allergy_alert(self, allergies):
        card = QFrame()
        card.setObjectName("AlertCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SPACING_UNIT * 3, theme.SECTION_PADDING, theme.SPACING_UNIT * 3
        )
        text = QLabel(f"⚠ Allergies: {allergies}")
        text.setObjectName("AlertText")
        text.setWordWrap(True)
        card_layout.addWidget(text)
        return card

    def _build_admission_card(self, summary):
        card, card_layout = self._section_card("ADMISSION")
        # Short fields, side by side — more scannable than one per line,
        # and there's no meaningful reason Telephone needs a full row.
        row = QHBoxLayout()
        row.setSpacing(theme.FIELD_GAP)
        fields = [
            ("Telephone", summary.telephone),
            ("Blood Group", summary.blood_group),
            ("Admission Date", print_layout.format_date(summary.date_admission)),
            ("Surgery Date", print_layout.format_date(summary.date_surgery)),
            ("Discharge Date", print_layout.format_date(summary.date_discharge)),
        ]
        present = [(label, value) for label, value in fields if value]
        if present:
            for label, value in present:
                row.addWidget(self._value_field(label, value))
            row.addStretch()
            card_layout.addLayout(row)
        else:
            card_layout.addWidget(self._muted("No admission details recorded."))
        return card

    def _build_procedure_card(self, summary):
        card, card_layout = self._section_card("PROCEDURE")
        if summary.procedure_title:
            title_label = QLabel(summary.procedure_title.upper())
            title_label.setObjectName("ProcedureTitle")
            title_label.setWordWrap(True)
            card_layout.addWidget(title_label)
        any_field = False
        for label, attr, _preserve in print_layout.DETAIL_FIELDS:
            value = getattr(summary, attr)
            if value:
                card_layout.addWidget(self._value_field(label, value))
                any_field = True
        if not summary.procedure_title and not any_field:
            card_layout.addWidget(self._muted("No procedure details recorded."))
        return card

    def _build_clinical_history_card(self, summary):
        if not print_layout.has_clinical_history(summary):
            return None
        card, card_layout = self._section_card("CLINICAL HISTORY")
        for label, attr in print_layout.CLINICAL_HISTORY_FIELDS:
            value = getattr(summary, attr)
            if value:
                card_layout.addWidget(self._value_field(label, value))
        return card

    def _build_investigations_card(self, summary, investigations):
        card, card_layout = self._section_card("INVESTIGATIONS & MANAGEMENT")
        investigations_text = print_layout.format_investigations(investigations)
        any_field = False
        if investigations_text:
            card_layout.addWidget(self._value_field("Investigations", investigations_text))
            any_field = True
        for label, attr, _preserve in print_layout.TAIL_FIELDS:
            value = getattr(summary, attr)
            if value:
                card_layout.addWidget(self._value_field(label, value))
                any_field = True
        if not any_field:
            card_layout.addWidget(self._muted("No investigations or management recorded."))
        return card

    def _build_attachments_card(self, attachments):
        # Only added to the page when there's at least one (see __init__),
        # so no "no attachments" muted fallback line is needed here —
        # unlike every other card, which is always present. Reuses
        # summary_view.py's row (filename · size + Open button) rather
        # than duplicating the open-file wiring a second time.
        card, card_layout = self._section_card("ATTACHMENTS")
        for attachment in attachments:
            card_layout.addWidget(_build_attachment_row(attachment))
        return card

    # --- Small builders ------------------------------------------------

    @staticmethod
    def _section_card(heading):
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SPACING_UNIT * 3, theme.SECTION_PADDING, theme.SPACING_UNIT * 3
        )
        card_layout.setSpacing(theme.FIELD_GAP)
        header = QLabel(heading)
        header.setObjectName("SectionHeader")
        card_layout.addWidget(header)
        return card, card_layout

    @staticmethod
    def _value_field(label, value):
        value_label = QLabel(str(value))
        value_label.setWordWrap(True)
        return LabeledField(label, value_label)

    @staticmethod
    def _muted(text):
        label = QLabel(text)
        label.setObjectName("Muted")
        return label


def _format_timestamp(iso_timestamp):
    """Full ISO datetime -> 'DD/MM/YYYY HH:MM'. Blank -> ''."""
    if not iso_timestamp:
        return ""
    date_part, _, time_part = iso_timestamp.partition("T")
    y, m, d = date_part.split("-")
    hh_mm = time_part[:5]
    return f"{d}/{m}/{y} {hh_mm}"
