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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import config, theme
from app.db import app_meta, connection as db_connection
from app.db import doctors as doctors_db
from app.db import templates as templates_db
from app.ui.dialogs.advanced_search import AdvancedSearchDialog
from app.ui.dialogs.doctors import DoctorsDialog
from app.ui.dialogs.recently_deleted import RecentlyDeletedDialog
from app.ui.dialogs.settings import BACKUP_PATH_KEY, SettingsDialog
from app.ui.dialogs.templates import TemplatesDialog
from app.ui.editor import Editor
from app.ui.editor_controller import EditorController
from app.ui.patient_list import PatientList
from app.util import backup as backup_util

HEADER_HEIGHT = 56
LIST_PANE_WIDTH = 280
MIN_WIDTH = 1280
MIN_HEIGHT = 720
LAST_DOCTOR_KEY = "last_doctor_id"
MANAGE_DOCTORS_LABEL = "Manage doctors…"


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
        self.editor.procedure_section.manage_templates_requested.connect(self._open_manage_templates)

        self.patient_list.patient_selected.connect(self.editor.load_summary)
        self.patient_list.new_card_button.clicked.connect(self._on_new_card)
        self.patient_list.advanced_search_button.clicked.connect(self._open_advanced_search)
        self.editor.duplicated.connect(self._on_summary_duplicated)
        self.editor.deleted.connect(self._on_summary_deleted)
        # A save can change what a card should display (name/BHT typed
        # into a previously-blank new card) — refresh the list so it
        # stays truthful, not just the open editor.
        self._controller.saved.connect(self.patient_list.refresh)

        self._install_shortcuts()

    def _open_manage_templates(self):
        dialog = TemplatesDialog(self._conn, self)
        dialog.exec()
        self.editor.procedure_section.set_templates(templates_db.list_active(self._conn))

    def _open_advanced_search(self):
        dialog = AdvancedSearchDialog(self._conn, self, self)
        dialog.exec()

    def _on_new_card(self):
        """+ New Card — creates a real blank row immediately (ui-spec.md
        §3.2), loads it into the editor, and selects it in the list."""
        created = self._controller.new_summary()
        self.editor.load_summary(created.id)
        self.patient_list.refresh()
        self.patient_list.select(created.id)

    def _on_summary_duplicated(self, new_id):
        self.patient_list.refresh()
        self.patient_list.select(new_id)

    def _on_summary_deleted(self):
        self.patient_list.refresh()

    def _install_shortcuts(self):
        # docs/ui-spec.md §7. Print/Save shortcuts only fire when those
        # actions are actually available (a summary is open) — same guard
        # the buttons themselves already enforce via _set_has_open_summary.
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.patient_list.new_card_button.click)

        # "Find" — opens Advanced Search, which replaced the old inline
        # search box entirely (docs/decisions.md).
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.patient_list.advanced_search_button.click)

        def trigger_print():
            if self.editor.print_button.isEnabled():
                self.editor.print_button.click()

        QShortcut(QKeySequence("Ctrl+P"), self, activated=trigger_print)

        def trigger_save():
            if self.editor.save_button.isEnabled():
                self.editor.save_button.click()

        QShortcut(QKeySequence("Ctrl+S"), self, activated=trigger_save)

        # Esc closes modals natively via Qt (QDialog) — no explicit
        # shortcut needed for that half. There's no search box to clear
        # anymore, so no fallback action is wired here.

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
        doctor_picker.addItems([d.name for d in self._doctors] + [MANAGE_DOCTORS_LABEL])
        doctor_picker.setCurrentIndex(default_index)
        doctor_picker.setFixedWidth(220)
        doctor_picker.setFocusPolicy(Qt.StrongFocus)  # macOS skips comboboxes on Tab by default; force it explicitly
        doctor_picker.currentIndexChanged.connect(self._on_doctor_selected)
        layout.addWidget(doctor_picker)
        self._doctor_picker = doctor_picker

        self._recently_deleted_button = QToolButton()
        self._recently_deleted_button.setText("🗑")
        self._recently_deleted_button.setToolTip("Recently Deleted")
        self._recently_deleted_button.clicked.connect(self._open_recently_deleted)
        layout.addWidget(self._recently_deleted_button)

        settings_button = QToolButton()
        settings_button.setText("⚙")
        settings_button.clicked.connect(self._open_settings)
        layout.addWidget(settings_button)

        return header

    def _open_settings(self):
        dialog = SettingsDialog(self._conn, self)
        dialog.exec()

    def _open_recently_deleted(self):
        dialog = RecentlyDeletedDialog(self._conn, self, self)
        dialog.exec()
        self.patient_list.refresh()

    def closeEvent(self, event):
        # Never lose a pending edit on exit, and never leave the connection
        # open — CLAUDE.md: "closed at exit."
        self._controller.flush()

        backup_path = app_meta.get(self._conn, BACKUP_PATH_KEY)
        if backup_path:
            # WAL mode means recent commits may still be sitting in the
            # -wal file, not yet in the main .db — checkpoint first so the
            # backed-up file is actually complete, not silently missing
            # the last few writes.
            self._conn.execute("PRAGMA wal_checkpoint(FULL)")
            backup_util.backup_now(config.get_db_path(), backup_path)

        db_connection.close(self._conn)
        super().closeEvent(event)

    def _on_doctor_selected(self, index):
        if index == len(self._doctors):  # the "Manage doctors…" sentinel, last item
            self._doctor_picker.blockSignals(True)
            self._doctor_picker.setCurrentIndex(self._doctors.index(self.selected_doctor))
            self._doctor_picker.blockSignals(False)
            self._open_manage_doctors()
            return
        self.selected_doctor = self._doctors[index]
        self._controller.current_doctor_id = self.selected_doctor.id
        app_meta.set(self._conn, LAST_DOCTOR_KEY, self.selected_doctor.id)

    def _open_manage_doctors(self):
        dialog = DoctorsDialog(self._conn, self)
        dialog.exec()
        self._reload_doctors()

    def _reload_doctors(self):
        """Called after the Manage Doctors dialog closes — rebuilds the
        dropdown, keeping the same selection if that doctor is still
        active, otherwise falling back to the first one."""
        self._doctors = doctors_db.list_active(self._conn)
        self._doctor_picker.blockSignals(True)
        self._doctor_picker.clear()
        self._doctor_picker.addItems([d.name for d in self._doctors] + [MANAGE_DOCTORS_LABEL])
        idx = next((i for i, d in enumerate(self._doctors) if d.id == self.selected_doctor.id), 0)
        self._doctor_picker.setCurrentIndex(idx)
        self._doctor_picker.blockSignals(False)
        self.selected_doctor = self._doctors[idx]
        self._controller.current_doctor_id = self.selected_doctor.id

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
