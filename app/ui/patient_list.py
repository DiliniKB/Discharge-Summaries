"""Left pane: New Card button, search, patient cards. See docs/ui-spec.md §3.2.

Fixture data only — no DB layer yet. Cards are plain dicts, not a Summary
dataclass: the real summaries table has 20+ columns (docs/schema.md) and
modelling that now, before the DB chunk defines it for real, would mean
guessing at a shape likely to change.
"""

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import theme
from app.ui.widgets.scrollframe import ScrollFrame

SEARCH_DEBOUNCE_MS = 150

FIXTURE_PATIENTS = [
    {"patient_name": "W.D. Kusuma Wijerathna", "bht_number": "10178", "ward": "45", "date_discharge": "2026-01-22"},
    {"patient_name": "A.B. Perera", "bht_number": "10202", "ward": "45", "date_discharge": "2026-01-21"},
    {"patient_name": "K.M. Silva", "bht_number": "10166", "ward": "45", "date_discharge": "2026-01-19"},
    {"patient_name": "R.P.N. Gunawardena", "bht_number": "10190", "ward": "45", "date_discharge": "2026-01-18"},
    {"patient_name": "S.K. Jayasuriya", "bht_number": "10151", "ward": "45", "date_discharge": "2026-01-15"},
]


def _display_date(iso_date):
    """ISO YYYY-MM-DD -> DD/MM/YYYY. See CLAUDE.md Data conventions."""
    y, m, d = iso_date.split("-")
    return f"{d}/{m}/{y}"


class _PatientCard(QFrame):
    def __init__(self, patient, on_click):
        super().__init__()
        self.patient = patient
        self._on_click = on_click
        self.setObjectName("PatientCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACING_UNIT * 3, theme.SPACING_UNIT * 2, theme.SPACING_UNIT * 3, theme.SPACING_UNIT * 2)
        layout.setSpacing(2)

        name = QLabel(patient["patient_name"])
        name.setObjectName("PatientName")
        layout.addWidget(name)

        meta = QLabel(f"BHT {patient['bht_number']} · Ward {patient['ward']}")
        meta.setObjectName("Muted")
        layout.addWidget(meta)

        date = QLabel(_display_date(patient["date_discharge"]))
        date.setObjectName("Muted")
        layout.addWidget(date)

    def set_selected(self, selected):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        self._on_click(self)
        super().mousePressEvent(event)


class PatientList(QWidget):
    patient_selected = Signal(dict)

    def __init__(self, patients=None, parent=None):
        super().__init__(parent)
        self._patients = patients if patients is not None else FIXTURE_PATIENTS
        self._selected_card = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING
        )
        layout.setSpacing(theme.SPACING_UNIT * 3)

        self.new_card_button = QPushButton("+ New Card")
        self.new_card_button.setObjectName("Primary")
        self.new_card_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        layout.addWidget(self.new_card_button)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        layout.addWidget(self.search_box)

        self._scroll = ScrollFrame()
        layout.addWidget(self._scroll, stretch=1)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._apply_filter)
        self.search_box.textChanged.connect(lambda _: self._debounce.start(SEARCH_DEBOUNCE_MS))

        self._no_results_label = QLabel()
        self._no_results_label.setObjectName("Muted")
        self._no_results_label.setVisible(False)
        self._scroll.add_widget(self._no_results_label)

        self._cards = []
        self._render(self._sorted(self._patients))

    def _sorted(self, patients):
        return sorted(patients, key=lambda p: p["date_discharge"], reverse=True)

    def _render(self, patients):
        for card in self._cards:
            card.setParent(None)
        self._cards = []
        self._selected_card = None

        for patient in patients:
            card = _PatientCard(patient, on_click=self._on_card_clicked)
            self._scroll.add_widget(card)
            self._cards.append(card)

        self._no_results_label.setVisible(len(patients) == 0)

    def _on_card_clicked(self, card):
        if self._selected_card is not None:
            self._selected_card.set_selected(False)
        card.set_selected(True)
        self._selected_card = card
        self.patient_selected.emit(card.patient)

    def _apply_filter(self):
        query = self.search_box.text().strip().lower()
        if not query:
            self._render(self._sorted(self._patients))
            return

        matches = [
            p
            for p in self._patients
            if query in p["patient_name"].lower() or query in p["bht_number"].lower()
        ]
        self._no_results_label.setText(f'No summaries match "{self.search_box.text()}"')
        self._render(self._sorted(matches))
