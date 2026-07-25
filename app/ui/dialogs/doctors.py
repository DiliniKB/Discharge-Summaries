"""Manage Doctors dialog. See docs/user-guide.md "Adding or removing doctors".

Add / deactivate / reactivate — never delete. docs/decisions.md: deleting
a doctor would orphan the FK on every summary they signed, so old cards
would print without a signing officer. Reactivate exists because staff
rotate back through the unit — deactivation means "not currently here,"
not "gone for good."
"""

from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout
from PySide6.QtCore import Signal

from app import theme
from app.db import doctors as doctors_db
from app.ui.widgets.scrollframe import ScrollFrame


class DoctorsDialog(QDialog):
    doctors_changed = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("Manage Doctors")
        self.resize(420, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING
        )
        layout.setSpacing(theme.FIELD_GAP)

        self._scroll = ScrollFrame()
        layout.addWidget(self._scroll, stretch=1)

        add_row = QHBoxLayout()
        add_row.setSpacing(theme.FIELD_GAP)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Name")
        self.name_input.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        add_row.addWidget(self.name_input, stretch=1)

        self.designation_input = QLineEdit()
        self.designation_input.setPlaceholderText("Designation")
        self.designation_input.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        add_row.addWidget(self.designation_input, stretch=1)

        self.add_button = QPushButton("+ Add")
        self.add_button.setObjectName("Primary")
        self.add_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.add_button.clicked.connect(self._on_add)
        add_row.addWidget(self.add_button)
        layout.addLayout(add_row)

        close_button = QPushButton("Done")
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
        for doctor in doctors_db.list_all(self._conn):
            row = self._build_row(doctor)
            self._scroll.add_widget(row)
            self._rows.append(row)

    def _build_row(self, doctor):
        row = QFrame()
        row.setObjectName("Card")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(
            theme.SPACING_UNIT * 3, theme.SPACING_UNIT * 2, theme.SPACING_UNIT * 3, theme.SPACING_UNIT * 2
        )

        label = QLabel(doctor.display_name if doctor.active else f"{doctor.display_name} (inactive)")
        if not doctor.active:
            label.setObjectName("Muted")
        row_layout.addWidget(label, stretch=1)

        if doctor.active:
            deactivate_button = QPushButton("Deactivate")
            deactivate_button.setObjectName("SecondaryCompact")
            deactivate_button.clicked.connect(lambda _checked=False, d=doctor: self._on_deactivate(d))
            row_layout.addWidget(deactivate_button)
        else:
            reactivate_button = QPushButton("Reactivate")
            reactivate_button.setObjectName("SecondaryCompact")
            reactivate_button.clicked.connect(lambda _checked=False, d=doctor: self._on_reactivate(d))
            row_layout.addWidget(reactivate_button)

        return row

    def _on_add(self):
        name = self.name_input.text().strip()
        if not name:
            return
        designation = self.designation_input.text().strip()
        next_sort_order = len(doctors_db.list_all(self._conn))
        doctors_db.add(self._conn, name, designation, sort_order=next_sort_order)
        self.name_input.clear()
        self.designation_input.clear()
        self.refresh()
        self.doctors_changed.emit()

    def _on_deactivate(self, doctor):
        doctors_db.deactivate(self._conn, doctor.id)
        self.refresh()
        self.doctors_changed.emit()

    def _on_reactivate(self, doctor):
        doctors_db.reactivate(self._conn, doctor.id)
        self.refresh()
        self.doctors_changed.emit()
