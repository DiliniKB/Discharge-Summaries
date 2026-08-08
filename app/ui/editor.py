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
    QApplication,
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
        # Save/Print need Name/Telephone/BHT to actually be valid, not
        # just "not currently flagged red" — see patient.py's module
        # docstring and _update_save_print_enabled() below.
        self.patient_section.validity_changed.connect(lambda _valid: self._update_save_print_enabled())

        self._has_open_summary = False
        self._set_has_open_summary(False)

    def _commit_focused_field(self):
        """A button click (or picking a different patient card) doesn't
        reliably steal keyboard focus away from a QLineEdit still being
        edited — macOS in particular treats buttons as click-only, not
        focus-taking (same Cocoa HI behaviour already noted in
        app/ui/sections/patient.py's Tab-order comment). Without this,
        editingFinished never fires, so the just-typed value never
        reaches controller.set_field()/set_investigation() at all —
        flush() then has nothing pending to write, and the record is
        silently missing whatever was still focused. clearFocus() forces
        the blur (and its editingFinished) before anything reads or
        persists the current field state. Scoped to widgets actually
        inside this Editor so it can't steal focus from an unrelated
        widget elsewhere in the window (e.g. the patient list's own search box)."""
        focused = QApplication.focusWidget()
        if focused is not None and self.isAncestorOf(focused):
            focused.clearFocus()

    def load_summary(self, summary_id):
        """Loads a real summary from the DB through the controller and
        populates every section."""
        self._commit_focused_field()  # don't lose an in-progress edit on the PREVIOUS record when switching
        summary = self.controller.load(summary_id)
        self.patient_section.populate(summary)
        self.procedure_section.populate(summary)
        self.clinical_history_section.populate(summary)
        self.investigations_section.populate(summary, self.controller.investigations)
        self.attachments_section.populate()

        self._name_label.setText(summary.patient_name or "(unnamed)")
        self._meta_label.setText(f"BHT {summary.bht_number} · Ward {summary.ward or ''}")
        # _set_has_open_summary() sets "Not saved", then (via
        # _update_save_print_enabled()) replaces it with a "Fill in ..."
        # explanation if the record isn't actually complete — don't set
        # "Not saved" again afterward, that would silently clobber it.
        self._set_has_open_summary(True)
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
        self._has_open_summary = has_summary
        self.overflow_button.setEnabled(has_summary)
        self.attachments_section.set_enabled(has_summary)
        self._save_state_label.setText("Not saved" if has_summary else "")
        self._update_save_print_enabled()

    def _update_save_print_enabled(self):
        """Save/Print need both an open summary AND Name/Telephone/BHT to
        currently be valid (app/ui/sections/patient.py's is_valid()) — a
        record missing its required identity/contact fields isn't
        actually ready to be treated as done, even before anything is
        shown red. Duplicate/Delete (overflow_button) aren't gated the
        same way — neither is about finishing the record.

        A disabled Save button with no visible red anywhere (a genuinely
        untouched brand-new card, or an older record whose Telephone
        predates this validation) is a dead end with no explanation —
        reported as such. Since patient.py deliberately never shows red
        until the user's own blur, this is the other half: name the
        actual missing field(s) in the muted status text instead, so
        "why can't I save this" always has a visible answer.
        """
        valid = self.patient_section.is_valid()
        enabled = self._has_open_summary and valid
        self.print_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)

        if not self._has_open_summary:
            return
        if not valid:
            missing = ", ".join(self.patient_section.missing_required_fields())
            self._save_state_label.setText(f"Fill in {missing} to save")
        elif self._save_state_label.text().startswith("Fill in "):
            # Just became valid — but leave an existing "✓ Saved"/"Not
            # saved" alone otherwise; this only runs on a real blur, and
            # a no-op blur on an already-saved record must not make a
            # truthful "✓ Saved" flicker back to "Not saved".
            self._save_state_label.setText("Not saved")

    def _on_print(self):
        if self.controller.summary_id is None:
            return
        self._commit_focused_field()
        self.controller.flush()  # printed content must match what's about to be saved, not stale field values — always run, even if we bail out below, so a stray-armed coalesce timer never outlives this call
        # _commit_focused_field() can itself be what makes this record
        # invalid: if the user was still mid-edit in Name/Telephone/BHT
        # when they clicked Print, forcing that field to blur just now
        # is the FIRST time its current text gets validated — Print
        # could have been enabled a moment ago (based on the last
        # blurred, valid value) and only become invalid because of the
        # blur this same click just forced. Whatever WAS valid is still
        # flushed above; only opening a preview for an incomplete record
        # is what's refused here.
        if not self.patient_section.is_valid():
            return
        # ignore_cleanup_errors: os.startfile(path, "print") (app/printing/printer.py)
        # hands the PDF to whatever the shell's default handler is and
        # returns immediately — that external viewer/print spooler can
        # still hold the file open by the time this `with` exits, and
        # Windows (unlike POSIX) refuses to delete an open file
        # (WinError 32). That's an external process's timing, not
        # something this app controls or a real failure — cleanup best-
        # effort, don't let it interrupt the doctor closing the dialog.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            dialog = PrintPreviewDialog(
                self.controller.conn, self.controller.summary_id, tmp_dir, self.controller.current_doctor_id, self
            )
            dialog.exec()
            # tmp_dir (and the rendered PDF in it) is cleaned up here, once
            # the modal closes — CLAUDE.md: temp file, released after printing.

    def _on_save(self):
        # flush() only emits `saved` when something was actually pending —
        # right after an autosave already wrote it, or on a freshly-created
        # card nothing's been typed into yet, there's nothing to flush, but
        # the record IS fully persisted. An explicit Save click must
        # confirm that either way, or the label can be stuck on "Not
        # saved" forever despite the DB already matching the screen.
        self._commit_focused_field()
        self.controller.flush()  # always run first — whatever's actually valid still saves, and this stops any coalesce timer armed above before we might bail out below
        # _commit_focused_field() can itself be what makes this record
        # invalid: if the user was still mid-edit in Name/Telephone/BHT
        # when they clicked Save, forcing that field to blur just now is
        # the FIRST validation of it — Save could have been enabled a
        # moment ago (based on the last-blurred, valid value) and only
        # become invalid because of the blur this click just forced.
        # flush() above already saved whatever WAS valid; only the "✓
        # Saved" confirmation is refused here — showing it over a value
        # that was just flagged red would contradict the red border/
        # message sitting right next to it.
        if not self.patient_section.is_valid():
            return
        self._on_saved()

    def _on_duplicate(self):
        if self.controller.summary_id is None:
            return
        self._commit_focused_field()
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
