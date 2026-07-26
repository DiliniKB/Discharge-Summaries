"""Right pane: assembles the action bar + sections. See docs/ui-spec.md §3.3.

Action bar is real (breadcrumb updates on patient selection, buttons
enable/disable correctly). Fields across all data-bearing sections now
autosave through `controller` (app/ui/editor_controller.py) — see
bind_controller() on each section. Print opens the real Print Preview
dialog (app/ui/dialogs/print_preview.py). Duplicate/Delete are real too —
Editor has no reference to PatientList/MainWindow, so it announces both
via signals (duplicated/deleted) rather than reaching into either, same
shape as the existing controller.saved -> patient_list.refresh wiring in
main_window.py.
"""

import datetime
import tempfile

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.db import summaries
from app.ui.dialogs.print_preview import PrintPreviewDialog

from app import theme
from app.ui.sections.attachments import AttachmentsSection
from app.ui.sections.clinical_history import ClinicalHistorySection
from app.ui.sections.investigations import InvestigationsSection
from app.ui.sections.patient import PatientSection
from app.ui.sections.procedure import ProcedureSection
from app.ui.widgets.scrollframe import ScrollFrame

ACTION_BAR_HEIGHT = 64


class Editor(QWidget):
    duplicated = Signal(int)  # new summary_id
    deleted = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.action_bar = self._build_action_bar()
        layout.addWidget(self.action_bar)

        self.sections_area = ScrollFrame()
        layout.addWidget(self.sections_area, stretch=1)

        self.patient_section = PatientSection()
        self.sections_area.add_widget(self.patient_section)

        self.procedure_section = ProcedureSection()
        self.sections_area.add_widget(self.procedure_section)

        self.clinical_history_section = ClinicalHistorySection()
        self.sections_area.add_widget(self.clinical_history_section)

        self.investigations_section = InvestigationsSection()
        self.sections_area.add_widget(self.investigations_section)

        self.attachments_section = AttachmentsSection()
        self.sections_area.add_widget(self.attachments_section)

        self.patient_section.bind_controller(controller)
        self.procedure_section.bind_controller(controller)
        self.clinical_history_section.bind_controller(controller)
        self.investigations_section.bind_controller(controller)
        self.attachments_section.bind_controller(controller)
        controller.saved.connect(self._on_saved)

        self._set_has_open_summary(False)

    def load_summary(self, summary_id):
        """Loads a real summary from the DB through the controller and
        populates every section."""
        summary = self.controller.load(summary_id)
        self.patient_section.populate(summary)
        self.procedure_section.populate(summary)
        self.clinical_history_section.populate(summary)
        self.investigations_section.populate(summary, self.controller.investigations)
        self.attachments_section.populate()

        self._name_label.setText(summary.patient_name or "(unnamed)")
        self._meta_label.setText(f"BHT {summary.bht_number} · Ward {summary.ward or ''}")
        self._set_has_open_summary(True)
        self._save_state_label.setText("Not saved")
        return summary

    def _on_saved(self):
        now = datetime.datetime.now().strftime("%H:%M")
        self._save_state_label.setText(f"✓ Saved {now}")

    def _build_action_bar(self):
        bar = QFrame()
        bar.setObjectName("Header")  # reuses the same bottom-border treatment as the main header
        bar.setFixedHeight(ACTION_BAR_HEIGHT)

        outer = QVBoxLayout(bar)
        outer.setContentsMargins(theme.SECTION_PADDING, 6, theme.SECTION_PADDING, 6)
        outer.setSpacing(2)

        top_row = QHBoxLayout()
        self._name_label = QLabel("No summary open")
        self._name_label.setObjectName("PatientName")
        top_row.addWidget(self._name_label)
        top_row.addStretch()

        self.print_button = QPushButton("Print")
        self.print_button.setObjectName("PrimaryCompact")
        self.print_button.clicked.connect(self._on_print)
        top_row.addWidget(self.print_button)

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("SecondaryCompact")
        self.save_button.clicked.connect(self._on_save)
        top_row.addWidget(self.save_button)

        self.overflow_button = QToolButton()
        self.overflow_button.setText("⋮")
        self.overflow_button.setPopupMode(QToolButton.InstantPopup)
        overflow_menu = QMenu(self.overflow_button)
        self._duplicate_action = overflow_menu.addAction("Duplicate", self._on_duplicate)
        self._delete_action = overflow_menu.addAction("Delete", self._on_delete)
        self.overflow_button.setMenu(overflow_menu)
        top_row.addWidget(self.overflow_button)

        outer.addLayout(top_row)

        bottom_row = QHBoxLayout()
        self._meta_label = QLabel("")
        self._meta_label.setObjectName("Muted")
        bottom_row.addWidget(self._meta_label)
        bottom_row.addStretch()

        self._save_state_label = QLabel("")
        self._save_state_label.setObjectName("Muted")
        bottom_row.addWidget(self._save_state_label)
        outer.addLayout(bottom_row)

        return bar

    def _set_has_open_summary(self, has_summary):
        self.print_button.setEnabled(has_summary)
        self.save_button.setEnabled(has_summary)
        self.overflow_button.setEnabled(has_summary)
        self.attachments_section.set_enabled(has_summary)
        self._save_state_label.setText("Not saved" if has_summary else "")

    def _on_print(self):
        if self.controller.summary_id is None:
            return
        self.controller.flush()  # printed content must match what's about to be saved, not stale field values
        with tempfile.TemporaryDirectory() as tmp_dir:
            dialog = PrintPreviewDialog(
                self.controller.conn, self.controller.summary_id, tmp_dir, self.controller.current_doctor_id, self
            )
            dialog.exec()
            # tmp_dir (and the rendered PDF in it) is cleaned up here, once
            # the modal closes — CLAUDE.md: temp file, released after printing.

    def _on_save(self):
        self.controller.flush()

    def _on_duplicate(self):
        if self.controller.summary_id is None:
            return
        self.controller.flush()  # must not duplicate stale unsaved edits — same reasoning as _on_print
        new_summary = self.controller.duplicate_summary(self.controller.summary_id)
        self.load_summary(new_summary.id)
        self.duplicated.emit(new_summary.id)

    def _on_delete(self):
        if self.controller.summary_id is None:
            return
        current = summaries.get(self.controller.conn, self.controller.summary_id)
        name = current.patient_name or "this record"
        # Single-click confirm, not a typed-name dialog — Recently Deleted
        # (app/ui/dialogs/recently_deleted.py) is the real safety net now,
        # so the heavier friction wasn't earning its keep (docs/decisions.md).
        # Default button is No so Enter/Return can't accidentally confirm.
        reply = QMessageBox.question(
            self,
            "Delete Summary",
            f'Delete "{name}"? You can restore it later from Recently Deleted.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        summaries.soft_delete(self.controller.conn, self.controller.summary_id)
        self.controller.clear()
        self._name_label.setText("No summary open")
        self._meta_label.setText("")
        self._set_has_open_summary(False)
        self.deleted.emit()
