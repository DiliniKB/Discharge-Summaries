"""Attachments section. Collapsed by default. See docs/ui-spec.md §3.3.

Multi-select file picker or drag-and-drop onto the drop zone, both feeding
one shared handler (_import_paths) so there's exactly one code path.
Files are capped at 5 MB and images resized on import (CLAUDE.md hard
rule #9, app/util/attachments.py). Add/remove write straight through
EditorController — see docs/decisions.md.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from app import theme
from app.ui.widgets.collapsible import CollapsibleSection
from app.util.attachments import (
    AttachmentMissingError,
    AttachmentOpenUnsupportedError,
    AttachmentTooLargeError,
    format_size,
    open_attachment_file,
)


class _AttachmentRow(QWidget):
    """One attached file: name, size, open button, remove button. Mirrors
    investigations.py's _AdHocRow — constructor-injected on_remove/on_open
    callbacks passing itself, so the parent doesn't track index/id mapping."""

    def __init__(self, attachment, on_remove, on_open, parent=None):
        super().__init__(parent)
        self.attachment = attachment
        self._on_remove = on_remove
        self._on_open = on_open

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.FIELD_GAP)

        name_label = QLabel(attachment.filename)
        layout.addWidget(name_label, stretch=1)

        size_label = QLabel(format_size(attachment.size_bytes))
        size_label.setObjectName("Muted")
        layout.addWidget(size_label)

        open_button = QPushButton("Open")
        open_button.setObjectName("SecondaryCompact")
        open_button.clicked.connect(lambda: self._on_open(self))
        layout.addWidget(open_button)

        remove_button = QToolButton()
        remove_button.setText("✕")
        remove_button.clicked.connect(lambda: self._on_remove(self))
        layout.addWidget(remove_button)


class AttachmentsSection(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__(title="Attachments", collapsed=True, parent=parent)
        self._controller = None
        self.rows = []
        self.setAcceptDrops(True)

        self.drop_zone = QFrame()
        self.drop_zone.setObjectName("DropZone")
        zone_layout = QVBoxLayout(self.drop_zone)
        zone_layout.setAlignment(Qt.AlignCenter)
        zone_layout.setContentsMargins(theme.SECTION_PADDING, theme.SECTION_PADDING * 2, theme.SECTION_PADDING, theme.SECTION_PADDING * 2)
        zone_layout.setSpacing(theme.SPACING_UNIT * 2)

        message = QLabel("No files attached")
        message.setObjectName("Muted")
        message.setAlignment(Qt.AlignCenter)
        zone_layout.addWidget(message)

        sub_message = QLabel("Drag files here, or click Add File to browse")
        sub_message.setObjectName("Muted")
        sub_message.setAlignment(Qt.AlignCenter)
        zone_layout.addWidget(sub_message)

        self.add_file_button = QPushButton("+ Add File")
        self.add_file_button.setObjectName("SecondaryCompact")
        self.add_file_button.clicked.connect(self._on_add_file_clicked)
        zone_layout.addWidget(self.add_file_button, alignment=Qt.AlignCenter)

        self.body_layout.addWidget(self.drop_zone)

        self._error_label = QLabel("")
        self._error_label.setObjectName("Danger")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        self.body_layout.addWidget(self._error_label)

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(theme.FIELD_GAP)
        self.body_layout.addLayout(self.rows_layout)

        self._update_counter()
        self.set_enabled(False)

    def bind_controller(self, controller):
        self._controller = controller

    def populate(self):
        """Rebuilds the row list from the DB (via the controller) — no
        summary argument, since attachments aren't a Summary field."""
        for row_widget in list(self.rows):
            self._remove_row_widget(row_widget)
        for attachment in self._controller.list_attachments():
            self._add_row_widget(attachment)
        self._update_counter()

    def set_enabled(self, enabled):
        """Disables adding files (button + drag-drop) when no summary is
        open — mirrors Editor._set_has_open_summary disabling Print/Save."""
        self.add_file_button.setEnabled(enabled)
        self.setAcceptDrops(enabled)

    def _add_row_widget(self, attachment):
        row = _AttachmentRow(attachment, on_remove=self._on_remove_row, on_open=self._on_open_row)
        self.rows_layout.addWidget(row)
        self.rows.append(row)

    def _remove_row_widget(self, row):
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    def _update_counter(self):
        count = len(self.rows)
        self.set_counter(f"{count} file" if count == 1 else f"{count} files")

    def _on_add_file_clicked(self):
        # An explicit QFileDialog instance, not the static
        # getOpenFileNames() convenience method — that one gives no
        # handle to call raise_()/activateWindow() before it opens. On
        # macOS the native dialog can open behind the main window without
        # grabbing focus, which looks exactly like "the button does
        # nothing" (the same class of window-activation bug this app has
        # hit before — see tests/test_polish.py, tests/test_section_patient.py).
        dialog = QFileDialog(self, "Add attachment")
        dialog.setFileMode(QFileDialog.ExistingFiles)
        dialog.raise_()
        dialog.activateWindow()
        if dialog.exec():
            paths = dialog.selectedFiles()
            if paths:
                self._import_paths(paths)

    def _import_paths(self, paths):
        self._error_label.setVisible(False)
        errors = []
        for path in paths:
            try:
                self._controller.add_attachment(path)
            except AttachmentTooLargeError as e:
                errors.append(str(e))
        self.populate()
        if errors:
            self._error_label.setText("\n".join(errors))
            self._error_label.setVisible(True)

    def _on_remove_row(self, row):
        self._controller.remove_attachment(row.attachment.id)
        self.populate()

    def _on_open_row(self, row):
        # Hands off to the OS's default viewer for the file type (photo,
        # PDF, DOCX) — no in-app preview to build. Informs, never blocks:
        # a missing file or a non-Windows dev run shows an inline message
        # instead of crashing (docs/decisions.md's "warn, don't block").
        self._error_label.setVisible(False)
        try:
            open_attachment_file(row.attachment.stored_path)
        except (AttachmentMissingError, AttachmentOpenUnsupportedError) as e:
            self._error_label.setText(str(e))
            self._error_label.setVisible(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self._import_paths(paths)
        event.acceptProposedAction()
