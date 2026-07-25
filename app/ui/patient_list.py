"""Left pane: New Card button, search, patient cards. See docs/ui-spec.md §3.2.

Backed by the real DB (app/db/summaries.py) — list_page()/search() never
load full records, per CLAUDE.md hard rule #4.

Deferred: the "dot marker" on unsaved cards (ui-spec.md §3.2) isn't drawn
yet — undischarged cards do correctly sort to the top (see summaries.py's
_ORDER_UNDISCHARGED_FIRST), just without the visual marker distinguishing
them further.
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
from app.db import summaries
from app.ui.widgets.scrollframe import ScrollFrame

SEARCH_DEBOUNCE_MS = 150


def _display_date(iso_date):
    """ISO YYYY-MM-DD -> DD/MM/YYYY. See CLAUDE.md Data conventions."""
    if not iso_date:
        return "Not discharged"
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

        name = QLabel(patient["patient_name"] or "(unnamed)")
        name.setObjectName("PatientName")
        layout.addWidget(name)

        meta = QLabel(f"BHT {patient['bht_number'] or '—'} · Ward {patient['ward'] or '—'}")
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
    patient_selected = Signal(int)  # summary_id, not a fixture dict

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._selected_id = None

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
        self._debounce.timeout.connect(self.refresh)
        self.search_box.textChanged.connect(lambda _: self._debounce.start(SEARCH_DEBOUNCE_MS))

        self._no_results_label = QLabel()
        self._no_results_label.setObjectName("Muted")
        self._no_results_label.setVisible(False)
        self._scroll.add_widget(self._no_results_label)

        self._cards = []
        self.refresh()

    def refresh(self):
        """Re-queries the DB and rebuilds the card list, preserving
        whichever summary is currently selected (if it's still present)."""
        query = self.search_box.text().strip()
        if query:
            patients = summaries.search(self._conn, query)
            self._no_results_label.setText(f'No summaries match "{query}"')
        else:
            patients = summaries.list_page(self._conn)
        self._render(patients)

    def select(self, summary_id):
        self._selected_id = summary_id
        for card in self._cards:
            card.set_selected(card.patient["id"] == summary_id)

    def _render(self, patients):
        for card in self._cards:
            card.setParent(None)
        self._cards = []

        for patient in patients:
            card = _PatientCard(patient, on_click=self._on_card_clicked)
            card.set_selected(patient["id"] == self._selected_id)
            self._scroll.add_widget(card)
            self._cards.append(card)

        self._no_results_label.setVisible(len(patients) == 0)

    def _on_card_clicked(self, card):
        summary_id = card.patient["id"]
        self.select(summary_id)
        self.patient_selected.emit(summary_id)
