"""QScrollArea + inner widget. Everything else depends on this. See CLAUDE.md."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget


class ScrollFrame(QScrollArea):
    """A vertically scrollable container.

    Add content into `.body` (via `.body_layout`), not into this widget directly.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setFrameShape(QScrollArea.NoFrame)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        self.body_layout.addStretch()  # keeps content top-aligned as sections are added

        self.setWidget(self.body)

    def add_widget(self, widget):
        """Insert before the trailing stretch, so content stacks top-down."""
        self.body_layout.insertWidget(self.body_layout.count() - 1, widget)
