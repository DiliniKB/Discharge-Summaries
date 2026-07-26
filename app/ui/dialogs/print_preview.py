"""Print Preview dialog. See docs/ui-spec.md §5, docs/print-layout.md.

Renders the actual generated PDF, not an HTML approximation — what's on
screen is what leaves the printer.

Printer-picker/copies controls are deliberately NOT included:
docs/decisions.md is explicit that printer selection is OS-level and
advisory only, decided by the shell handler at print time — building UI
controls that don't actually do anything would mislead ward staff into
thinking they control something they don't.

Esc closes — standard QDialog behavior, no extra code needed for that
half of docs/ui-spec.md §7's "Esc: Close modal."
"""

import re
import shutil

from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app import theme
from app.db import doctors as doctors_db, summaries
from app.printing import layout as print_layout
from app.printing.printer import PrintUnsupportedError, print_pdf
from app.util.screen import clamped_dialog_size

_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


class PrintPreviewDialog(QDialog):
    def __init__(self, conn, summary_id, tmp_dir, doctor_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Print Preview")
        # A full A4 page preview genuinely wants 900px of height, but
        # that's taller than the target 1366x768 screen has room for
        # once Windows' taskbar is accounted for — clamped so the
        # Save/Cancel/Print row at the bottom is never pushed off-screen
        # (docs/decisions.md).
        self.resize(*clamped_dialog_size(self, 700, 900))

        summary = summaries.get(conn, summary_id)
        self.summary = summary
        investigations = summaries.list_investigations(conn, summary_id)
        # The signing officer is whoever is CURRENTLY selected in the
        # header when printing, not summary.created_by — a different
        # doctor may have created the record than the one discharging/
        # signing it now (docs/decisions.md).
        doctor = doctors_db.get(conn, doctor_id) if doctor_id else None

        self.pdf_path = print_layout.render_summary(summary, investigations, doctor, tmp_dir)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._document = QPdfDocument(self)
        self._document.load(str(self.pdf_path))

        self._view = QPdfView(self)
        self._view.setDocument(self._document)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        layout.addWidget(self._view, stretch=1)

        button_bar = QHBoxLayout()
        button_bar.setContentsMargins(
            theme.SECTION_PADDING, theme.SPACING_UNIT * 2, theme.SECTION_PADDING, theme.SPACING_UNIT * 2
        )
        button_bar.setSpacing(theme.FIELD_GAP)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        button_bar.addWidget(self.status_label, stretch=1)

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("Secondary")
        self.save_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.save_button.clicked.connect(self._on_save)
        button_bar.addWidget(self.save_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("Secondary")
        cancel_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        cancel_button.clicked.connect(self.reject)
        button_bar.addWidget(cancel_button)

        self.print_button = QPushButton("Print")
        self.print_button.setObjectName("Primary")
        self.print_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.print_button.clicked.connect(self._on_print)
        button_bar.addWidget(self.print_button)

        layout.addLayout(button_bar)

    def _on_print(self):
        try:
            print_pdf(self.pdf_path)
            self.accept()
        except PrintUnsupportedError:
            self.status_label.setText("No default printer, or printing isn't available on this system.")

    def _on_save(self):
        # Copies the already-rendered PDF, doesn't re-render — doesn't
        # accept()/reject() either, unlike Print, since a doctor might
        # want to save and then still print, or just save without
        # printing at all.
        default_name = _UNSAFE_FILENAME_CHARS.sub(
            "_", f"{self.summary.patient_name or 'summary'}_{self.summary.bht_number or ''}"
        ).strip("_") + ".pdf"
        chosen_path, _filter = QFileDialog.getSaveFileName(self, "Save PDF", default_name, "PDF Files (*.pdf)")
        if not chosen_path:
            return
        shutil.copy2(self.pdf_path, chosen_path)
        self.status_label.setText("Saved.")
