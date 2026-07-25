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
from app.db import app_meta, connection as db_connection
from app.db import doctors as doctors_db
from app.db import templates as templates_db
from app.ui.editor import Editor
from app.ui.editor_controller import EditorController
from app.ui.patient_list import PatientList

HEADER_HEIGHT = 56
LIST_PANE_WIDTH = 280
MIN_WIDTH = 1280
MIN_HEIGHT = 720
LAST_DOCTOR_KEY = "last_doctor_id"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Discharge Summaries · Surgical Oncology Unit")
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        # CLAUDE.md hard rule: one connection, opened at startup, closed at
        # exit — never per-operation. See closeEvent() for the exit half.
        self._conn = db_connection.connect()
        self._controller = EditorController(self._conn)

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

        self.editor = Editor(self._controller)
        body_layout.addWidget(self.editor, stretch=1)

        templates_db.seed_if_empty(self._conn)
        self.editor.procedure_section.set_templates(templates_db.list_active(self._conn))

        self.patient_list.patient_selected.connect(self.editor.load_summary)
        self.patient_list.new_card_button.clicked.connect(self._on_new_card)
        # A save can change what a card should display (name/BHT typed
        # into a previously-blank new card) — refresh the list so it
        # stays truthful, not just the open editor.
        self._controller.saved.connect(self.patient_list.refresh)

        self._install_shortcuts()

    def _on_new_card(self):
        """+ New Card — creates a real blank row immediately (ui-spec.md
        §3.2), loads it into the editor, and selects it in the list."""
        created = self._controller.new_summary()
        self.editor.load_summary(created.id)
        self.patient_list.refresh()
        self.patient_list.select(created.id)

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

        doctors_db.seed_if_empty(self._conn)
        self._doctors = doctors_db.list_active(self._conn)

        default_index = 0
        last_id_str = app_meta.get(self._conn, LAST_DOCTOR_KEY)
        if last_id_str is not None:
            for i, d in enumerate(self._doctors):
                if d.id == int(last_id_str):
                    default_index = i
                    break
        self.selected_doctor = self._doctors[default_index]
        self._controller.current_doctor_id = self.selected_doctor.id

        doctor_picker = QComboBox()
        doctor_picker.setEditable(False)  # dropdown-only by default in Qt — no readonly quirk to work around
        doctor_picker.addItems([d.name for d in self._doctors])
        doctor_picker.setCurrentIndex(default_index)
        doctor_picker.setFixedWidth(220)
        doctor_picker.setFocusPolicy(Qt.StrongFocus)  # macOS skips comboboxes on Tab by default; force it explicitly
        doctor_picker.currentIndexChanged.connect(self._on_doctor_selected)
        layout.addWidget(doctor_picker)
        self._doctor_picker = doctor_picker

        return header

    def closeEvent(self, event):
        # Never lose a pending edit on exit, and never leave the connection
        # open — CLAUDE.md: "closed at exit."
        self._controller.flush()
        db_connection.close(self._conn)
        super().closeEvent(event)

    def _on_doctor_selected(self, index):
        self.selected_doctor = self._doctors[index]
        self._controller.current_doctor_id = self.selected_doctor.id
        app_meta.set(self._conn, LAST_DOCTOR_KEY, self.selected_doctor.id)

    def _build_list_pane(self):
        pane = QFrame()
        pane.setObjectName("Surface")
        pane.setFixedWidth(LIST_PANE_WIDTH)

        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)

        self.patient_list = PatientList(self._conn)
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
