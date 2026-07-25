"""Multi-line text area that grows with content up to a capped number of
lines, then scrolls. See docs/ui-spec.md §4.5: "auto-growing to a 6-line
cap then scrolling." Reused by Procedure Steps (chunk 10) and Management
(chunk 12) — not local to one section.
"""

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QTextEdit

_VERTICAL_PADDING = 18  # matches the QTextEdit QSS padding (8px top+bottom) plus frame slack


class AutoGrowTextEdit(QTextEdit):
    def __init__(self, min_lines=3, max_lines=6, parent=None):
        super().__init__(parent)
        self._min_lines = min_lines
        self._max_lines = max_lines
        self.textChanged.connect(self._adjust_height)
        self._adjust_height()

    def _adjust_height(self):
        line_height = QFontMetrics(self.font()).lineSpacing()
        min_h = line_height * self._min_lines + _VERTICAL_PADDING
        max_h = line_height * self._max_lines + _VERTICAL_PADDING
        content_h = self.document().size().height() + _VERTICAL_PADDING
        target = max(min_h, min(content_h, max_h))
        self.setFixedHeight(int(target))
