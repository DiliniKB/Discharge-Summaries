"""Template Manager dialog. See docs/ui-spec.md screen inventory ("modal,
edit canned procedure text").

Editing a template here must never alter an existing summary
(docs/decisions.md) — no extra guard needed for that: summaries already
hold their own independent copy of the text from when it was inserted
(verified in the Procedure section's own tests), so this dialog editing
a template's DB row is inherently safe.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app import theme
from app.db import templates as templates_db
from app.ui.widgets.autogrow_textedit import AutoGrowTextEdit
from app.ui.widgets.labeled import LabeledField


class TemplatesDialog(QDialog):
    templates_changed = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._current_id = None
        self.setWindowTitle("Template Manager")
        self.resize(640, 480)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING
        )
        layout.setSpacing(theme.FIELD_GAP)

        left = QVBoxLayout()
        left.setSpacing(theme.FIELD_GAP)
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        left.addWidget(self.list_widget, stretch=1)

        self.new_button = QPushButton("+ New Template")
        self.new_button.setObjectName("Secondary")
        self.new_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.new_button.clicked.connect(self._on_new)
        left.addWidget(self.new_button)
        layout.addLayout(left, stretch=1)

        right = QVBoxLayout()
        right.setSpacing(theme.FIELD_GAP)
        self.name_input = QLineEdit()
        self.name_input.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        right.addWidget(LabeledField("Name", self.name_input))

        self.body_input = AutoGrowTextEdit(min_lines=8, max_lines=20)
        right.addWidget(LabeledField("Steps", self.body_input))

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("Primary")
        self.save_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.save_button.clicked.connect(self._on_save)
        right.addWidget(self.save_button)
        right.addStretch()
        layout.addLayout(right, stretch=2)

        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        for template in templates_db.list_active(self._conn):
            item = QListWidgetItem(template.name)
            item.setData(Qt.UserRole, template.id)
            self.list_widget.addItem(item)

    def _on_selection_changed(self, current, _previous):
        if current is None:
            self._current_id = None
            self.name_input.clear()
            self.body_input.clear()
            return
        template = templates_db.get(self._conn, current.data(Qt.UserRole))
        self._current_id = template.id
        self.name_input.setText(template.name)
        self.body_input.setPlainText(template.body)

    def _on_new(self):
        created = templates_db.add(self._conn, "New template", "", sort_order=self.list_widget.count())
        self.refresh()
        self.templates_changed.emit()
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.UserRole) == created.id:
                self.list_widget.setCurrentRow(i)
                break

    def _on_save(self):
        if self._current_id is None:
            return
        name = self.name_input.text().strip()
        if not name:
            return
        saved_id = self._current_id
        templates_db.update(self._conn, saved_id, name, self.body_input.toPlainText())
        self.refresh()
        self.templates_changed.emit()
        # refresh() clears and rebuilds the list, which resets _current_id
        # to None via the currentItemChanged(None, ...) signal — without
        # re-selecting, the user would see their just-saved template
        # deselected right after clicking Save.
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.UserRole) == saved_id:
                self.list_widget.setCurrentRow(i)
                break
