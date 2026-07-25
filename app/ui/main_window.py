"""Header + split pane. See docs/ui-spec.md §3.

Skeleton + header only: list pane and editor pane hold placeholder content.
Remaining chunks fill them in one at a time.
"""

import sys

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

        self.editor_pane = self._build_editor_pane()
        body_layout.addWidget(self.editor_pane, stretch=1)

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
        layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING
        )

        # Placeholder — New Card button, search, and patient cards land in chunks 6-7.
        placeholder = QLabel("(patient list — chunk 6)")
        placeholder.setObjectName("Muted")
        layout.addWidget(placeholder)
        layout.addStretch()
        return pane

    def _build_editor_pane(self):
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING
        )

        # Placeholder — action bar + sections land in chunks 8-13.
        placeholder = QLabel("(editor — chunks 8-13)")
        placeholder.setObjectName("Muted")
        layout.addWidget(placeholder)
        layout.addStretch()
        return pane


def main():
    app = QApplication(sys.argv)
    theme.apply_theme(app)
    win = MainWindow()
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
