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

from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app import theme
from app.db import doctors as doctors_db, summaries
from app.printing import layout as print_layout
from app.printing.printer import PrintUnsupportedError, print_pdf


class PrintPreviewDialog(QDialog):
    def __init__(self, conn, summary_id, tmp_dir, doctor_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Print Preview")
        self.resize(700, 900)

        summary = summaries.get(conn, summary_id)
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
