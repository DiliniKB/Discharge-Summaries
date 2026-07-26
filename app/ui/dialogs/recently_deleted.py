"""Restore a soft-deleted summary. See docs/decisions.md "Soft delete
with a 30-day purge" — no purge job exists in the code yet, so this
shows every soft-deleted record, not just the last 30 days.

A standalone header action, not tied to whichever record is open —
same reasoning as Settings living in the header rather than the editor.
"""

from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app import theme
from app.db import summaries
from app.printing.layout import format_date
from app.ui.widgets.scrollframe import ScrollFrame


class RecentlyDeletedDialog(QDialog):
    def __init__(self, conn, main_window, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._main_window = main_window
        self.setWindowTitle("Recently Deleted")
        self.resize(480, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING
        )
        layout.setSpacing(theme.FIELD_GAP)

        self._scroll = ScrollFrame()
        layout.addWidget(self._scroll, stretch=1)

        self._empty_label = QLabel("Nothing here.")
        self._empty_label.setObjectName("Muted")
        self._empty_label.setVisible(False)
        self._scroll.add_widget(self._empty_label)

        close_button = QPushButton("Close")
        close_button.setObjectName("Secondary")
        close_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self._rows = []
        self.refresh()

    def refresh(self):
        for row in self._rows:
            row.setParent(None)
        self._rows = []
        deleted = summaries.list_deleted(self._conn)
        for record in deleted:
            row = self._build_row(record)
            self._scroll.add_widget(row)
            self._rows.append(row)
        self._empty_label.setVisible(len(deleted) == 0)

    def _build_row(self, record):
        row = QFrame()
        row.setObjectName("Card")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(
            theme.SPACING_UNIT * 3, theme.SPACING_UNIT * 2, theme.SPACING_UNIT * 3, theme.SPACING_UNIT * 2
        )
        row_layout.setSpacing(theme.FIELD_GAP)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_label = QLabel(record["patient_name"] or "(unnamed)")
        text_col.addWidget(name_label)
        meta_label = QLabel(
            f"BHT {record['bht_number'] or '—'} · Ward {record['ward'] or '—'} · "
            f"Deleted {format_date(record['deleted_at'][:10])}"
        )
        meta_label.setObjectName("Muted")
        text_col.addWidget(meta_label)
        row_layout.addLayout(text_col, stretch=1)

        restore_button = QPushButton("Restore")
        restore_button.setObjectName("SecondaryCompact")
        restore_button.clicked.connect(lambda _checked=False, r=record: self._on_restore(r))
        row_layout.addWidget(restore_button)

        return row

    def _on_restore(self, record):
        summaries.restore(self._conn, record["id"])
        self.refresh()
        self._main_window.patient_list.refresh()
