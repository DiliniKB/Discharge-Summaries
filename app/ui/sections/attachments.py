"""Attachments section. Collapsed by default, empty-state only. See
docs/ui-spec.md §3.3.

Deliberately a shell, not a full feature: real file handling needs
app/db/attachments.py (paths in DB, files on disk per docs/decisions.md)
and the 5MB-cap-and-resize rule from CLAUDE.md, neither of which exists
yet. Add File is a documented no-op, same treatment as Print/Save in
app/ui/editor.py — wiring even a "harmless" file dialog now would mean
building on top of a storage layer that isn't there.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from app import theme
from app.ui.widgets.collapsible import CollapsibleSection


class AttachmentsSection(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__(title="Attachments", collapsed=True, parent=parent)
        self.set_counter("0 files")

        drop_zone = QFrame()
        drop_zone.setObjectName("DropZone")
        zone_layout = QVBoxLayout(drop_zone)
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
        self.add_file_button.clicked.connect(self._on_add_file)
        zone_layout.addWidget(self.add_file_button, alignment=Qt.AlignCenter)

        self.body_layout.addWidget(drop_zone)

    def _on_add_file(self):
        pass  # TODO(attachments chunk): file picker, 5MB cap, resize, app/db/attachments.py — none exist yet.
