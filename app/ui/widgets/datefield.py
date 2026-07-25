"""One DD/MM/YYYY field, not a calendar picker — typing is faster than
clicking for staff entering a date they already know. See docs/ui-spec.md
§4.2. Storage is ISO-8601 (get_iso/set_iso); conversion happens only at
this UI boundary, per CLAUDE.md Data conventions.

No QLineEdit input mask: Qt's mask blank character renders visibly on
screen ("__/__/____") even when QLineEdit.text() strips it from the
returned string — confirmed by grabbing an actual widget render, not
assumed. That's inconsistent with every other empty field in the form,
which are clean blank boxes. Placeholder text + format-as-you-type
matches the pattern already used by the search box elsewhere in the app.

The calendar picker is docked inside the field itself via QLineEdit's
addAction() (trailing-edge icon), not a separate button beside the box —
one bordered field, not two chrome elements glued together.
"""

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QCalendarWidget, QHBoxLayout, QLineEdit, QSizePolicy, QWidget

from app import theme

_CALENDAR_ICON = None  # rendered once, reused across every DateField instance


def _calendar_icon():
    global _CALENDAR_ICON
    if _CALENDAR_ICON is None:
        size = 18
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setFont(QFont(theme.FONT_FAMILY, 12))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "📅")
        painter.end()
        _CALENDAR_ICON = QIcon(pixmap)
    return _CALENDAR_ICON


class DateField(QWidget):
    # Fires whenever a complete-or-cleared value should be persisted — on
    # blur after typing, AND on picking a date from the calendar (setText()
    # via set_iso() doesn't trigger QLineEdit's own editingFinished, so the
    # controller would silently miss calendar-picked dates without this).
    value_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.line = QLineEdit()
        self.line.setObjectName("DateBox")
        self.line.setPlaceholderText("DD/MM/YYYY")
        self.line.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # matches every other input in the form
        self.line.setFixedWidth(theme.WIDTH_M)  # same tier as BHT Number — both "medium identifier" fields
        self.line.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.line.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.line.textEdited.connect(self._auto_format)
        self.line.editingFinished.connect(lambda: self.value_changed.emit(self.get_iso()))
        layout.addWidget(self.line)

        # Convenience alongside typing, not a replacement — docs/ui-spec.md
        # §4.2 still holds: typing is faster for a date staff already
        # knows. Docked inside the field's own trailing edge, not a
        # separate button beside it.
        self._calendar_action = self.line.addAction(_calendar_icon(), QLineEdit.TrailingPosition)
        self._calendar_action.triggered.connect(self._open_calendar)

        self._calendar = QCalendarWidget()
        self._calendar.setWindowFlags(Qt.Popup)
        self._calendar.clicked.connect(self._on_calendar_date_picked)

    def _open_calendar(self):
        current = self.get_iso()
        if current:
            y, m, d = current.split("-")
            self._calendar.setSelectedDate(QDate(int(y), int(m), int(d)))
        pos = self.line.mapToGlobal(self.line.rect().bottomLeft())
        self._calendar.move(pos)
        self._calendar.show()

    def _on_calendar_date_picked(self, qdate):
        self.set_iso(qdate.toString("yyyy-MM-dd"))
        self._calendar.hide()
        self.value_changed.emit(self.get_iso())

    def set_today(self):
        self.set_iso(QDate.currentDate().toString("yyyy-MM-dd"))

    def _auto_format(self, text):
        digits = "".join(ch for ch in text if ch.isdigit())[:8]
        parts = [digits[0:2], digits[2:4], digits[4:8]]
        formatted = "/".join(p for p in parts if p)
        if formatted != text:
            self.line.blockSignals(True)
            self.line.setText(formatted)
            self.line.blockSignals(False)
            self.line.setCursorPosition(len(formatted))

    def get_iso(self):
        """Returns 'YYYY-MM-DD', or '' if the date is incomplete."""
        digits = "".join(ch for ch in self.line.text() if ch.isdigit())
        if len(digits) != 8:
            return ""
        d, m, y = digits[0:2], digits[2:4], digits[4:8]
        return f"{y}-{m}-{d}"

    def set_iso(self, iso_date):
        if not iso_date:
            self.line.clear()
            return
        y, m, d = iso_date.split("-")
        self.line.setText(f"{d}/{m}/{y}")
