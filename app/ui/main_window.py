"""Header + split pane. See docs/ui-spec.md §3.

Skeleton + header only: list pane and editor pane hold placeholder content.
Remaining chunks fill them in one at a time.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from app import theme
from app.models import Doctor
from app.ui.editor import Editor
from app.ui.patient_list import PatientList

HEADER_HEIGHT = 56
LIST_PANE_WIDTH = 280
MIN_WIDTH = 1280
MIN_HEIGHT = 720

# Fictional, hardcoded until app/db/doctors.py exists. Consultant first,
# per docs/schema.md ("Consultant first, not alphabetical") — sort_order
# reflects that, not alphabetisation.
PLACEHOLDER_DOCTORS = [
    Doctor(id=1, name="Dr. S. Herath", designation="SR Onco-surgery", sort_order=0),
    Doctor(id=2, name="Dr. N. Ratnayake", designation="Consultant Surgeon", sort_order=1),
    Doctor(id=3, name="Dr. P. Wickramasinghe", designation="Registrar", sort_order=2),
    Doctor(id=4, name="Dr. A. Fonseka", designation="SHO", sort_order=3),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Discharge Summaries · Surgical Oncology Unit")
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = self._build_header()
        outer.addWidget(self.header)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        outer.addWidget(body, stretch=1)

        self.list_pane = self._build_list_pane()
        body_layout.addWidget(self.list_pane)

        self.editor = Editor()
        body_layout.addWidget(self.editor, stretch=1)

        self.patient_list.patient_selected.connect(self.editor.set_current_patient)

        self._install_shortcuts()

    def _install_shortcuts(self):
        # docs/ui-spec.md §7. Print/Save shortcuts only fire when those
        # actions are actually available (a summary is open) — same guard
        # the buttons themselves already enforce via _set_has_open_summary.
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.patient_list.new_card_button.click)

        def focus_search():
            self.patient_list.search_box.setFocus()
            self.patient_list.search_box.selectAll()

        QShortcut(QKeySequence("Ctrl+F"), self, activated=focus_search)

        def trigger_print():
            if self.editor.print_button.isEnabled():
                self.editor.print_button.click()

        QShortcut(QKeySequence("Ctrl+P"), self, activated=trigger_print)

        def trigger_save():
            if self.editor.save_button.isEnabled():
                self.editor.save_button.click()

        QShortcut(QKeySequence("Ctrl+S"), self, activated=trigger_save)

        # No modals exist yet (print preview, dialogs) — Esc's "close modal"
        # half will be added when one does. Its fallback ("clear search")
        # works today.
        QShortcut(QKeySequence("Esc"), self, activated=self.patient_list.search_box.clear)

    def _build_header(self):
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(HEADER_HEIGHT)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(theme.SECTION_PADDING, 0, theme.SECTION_PADDING, 0)

        title = QLabel("Discharge Summaries · Surgical Oncology Unit")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)
        layout.addStretch()

        self._doctors = PLACEHOLDER_DOCTORS
        self.selected_doctor = self._doctors[0]
        # TODO(db chunk): default should be app_meta.last_doctor_id, not
        # always the first doctor. No settings/persistence layer yet.

        doctor_picker = QComboBox()
        doctor_picker.setEditable(False)  # dropdown-only by default in Qt — no readonly quirk to work around
        doctor_picker.addItems([d.name for d in self._doctors])
        doctor_picker.setFixedWidth(220)
        doctor_picker.setFocusPolicy(Qt.StrongFocus)  # macOS skips comboboxes on Tab by default; force it explicitly
        doctor_picker.currentIndexChanged.connect(self._on_doctor_selected)
        layout.addWidget(doctor_picker)
        self._doctor_picker = doctor_picker

        return header

    def _on_doctor_selected(self, index):
        self.selected_doctor = self._doctors[index]

    def _build_list_pane(self):
        pane = QFrame()
        pane.setObjectName("Surface")
        pane.setFixedWidth(LIST_PANE_WIDTH)

        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)

        self.patient_list = PatientList()
        layout.addWidget(self.patient_list)
        return pane


def main():
    app = QApplication(sys.argv)
    theme.apply_theme(app)
    win = MainWindow()
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
