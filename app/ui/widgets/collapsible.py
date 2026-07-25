"""Collapsible section = header toggles body via setVisible(). See CLAUDE.md."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app import theme

CHEVRON_OPEN = "▾"
CHEVRON_CLOSED = "▸"


class _ClickableHeader(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class CollapsibleSection(QWidget):
    """A titled section that expands/collapses. Content goes in `.body_layout`."""

    def __init__(self, title, collapsed=False, parent=None):
        super().__init__(parent)
        self._expanded = not collapsed

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(theme.SPACING_UNIT * 2)  # gap between header text and the bordered card

        header = _ClickableHeader()
        header.setCursor(Qt.PointingHandCursor)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(theme.SPACING_UNIT * 2, theme.SPACING_UNIT * 2, theme.SPACING_UNIT * 2, theme.SPACING_UNIT * 2)

        self._chevron = QLabel()
        self._chevron.setObjectName("SectionHeader")
        header_layout.addWidget(self._chevron)

        self._title = QLabel(title.upper())
        self._title.setObjectName("SectionHeader")
        header_layout.addWidget(self._title)
        header_layout.addStretch()

        self._counter = QLabel("")
        self._counter.setObjectName("Muted")
        header_layout.addWidget(self._counter)

        header.clicked.connect(self._toggle)
        outer.addWidget(header)

        # Bordered card, matching the boxed sections drawn in docs/ui-spec.md §3 —
        # groups a section's fields visually instead of floating them on the
        # pane background. Generic here so every section chunk gets it free.
        self.body = QFrame()
        self.body.setObjectName("Card")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SPACING_UNIT * 4, theme.SECTION_PADDING, theme.SPACING_UNIT * 4
        )
        self.body_layout.setSpacing(theme.FIELD_GAP)
        outer.addWidget(self.body)

        self._render_chevron()
        self.body.setVisible(self._expanded)

    def _toggle(self):
        self._expanded = not self._expanded
        self.body.setVisible(self._expanded)
        self._render_chevron()

    def _render_chevron(self):
        self._chevron.setText(CHEVRON_OPEN if self._expanded else CHEVRON_CLOSED)

    def set_counter(self, text):
        """Shown right-aligned in the header, e.g. '2 of 6 filled'. Empty string hides it."""
        self._counter.setText(text)

    @property
    def expanded(self):
        return self._expanded
