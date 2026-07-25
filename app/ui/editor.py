"""Right pane: assembles the action bar + sections. See docs/ui-spec.md §3.3.

Action bar is real (breadcrumb updates on patient selection, buttons
enable/disable correctly). Print/Save/Duplicate/Delete are shells — there's
no controller or DB yet to act on, see the TODOs below. Sections (chunks
9-13) will be added into `self.sections_area` one at a time.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import theme
from app.ui.sections.clinical_history import ClinicalHistorySection
from app.ui.sections.patient import PatientSection
from app.ui.sections.procedure import ProcedureSection
from app.ui.widgets.scrollframe import ScrollFrame

ACTION_BAR_HEIGHT = 64


class Editor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.action_bar = self._build_action_bar()
        layout.addWidget(self.action_bar)

        self.sections_area = ScrollFrame()
        layout.addWidget(self.sections_area, stretch=1)

        self.patient_section = PatientSection()
        self.sections_area.add_widget(self.patient_section)

        self.procedure_section = ProcedureSection()
        self.sections_area.add_widget(self.procedure_section)

        self.clinical_history_section = ClinicalHistorySection()
        self.sections_area.add_widget(self.clinical_history_section)

        placeholder = QLabel("(remaining sections — chunks 12-13)")
        placeholder.setObjectName("Muted")
        placeholder.setContentsMargins(theme.SECTION_PADDING, theme.SECTION_PADDING, 0, 0)
        self.sections_area.add_widget(placeholder)

        self._set_has_open_summary(False)

    def _build_action_bar(self):
        bar = QFrame()
        bar.setObjectName("Header")  # reuses the same bottom-border treatment as the main header
        bar.setFixedHeight(ACTION_BAR_HEIGHT)

        outer = QVBoxLayout(bar)
        outer.setContentsMargins(theme.SECTION_PADDING, 6, theme.SECTION_PADDING, 6)
        outer.setSpacing(2)

        top_row = QHBoxLayout()
        self._name_label = QLabel("No summary open")
        self._name_label.setObjectName("PatientName")
        top_row.addWidget(self._name_label)
        top_row.addStretch()

        self.print_button = QPushButton("Print")
        self.print_button.setObjectName("PrimaryCompact")
        self.print_button.clicked.connect(self._on_print)
        top_row.addWidget(self.print_button)

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("SecondaryCompact")
        self.save_button.clicked.connect(self._on_save)
        top_row.addWidget(self.save_button)

        self.overflow_button = QToolButton()
        self.overflow_button.setText("⋮")
        self.overflow_button.setPopupMode(QToolButton.InstantPopup)
        overflow_menu = QMenu(self.overflow_button)
        self._duplicate_action = overflow_menu.addAction("Duplicate", self._on_duplicate)
        self._delete_action = overflow_menu.addAction("Delete", self._on_delete)
        self.overflow_button.setMenu(overflow_menu)
        top_row.addWidget(self.overflow_button)

        outer.addLayout(top_row)

        bottom_row = QHBoxLayout()
        self._meta_label = QLabel("")
        self._meta_label.setObjectName("Muted")
        bottom_row.addWidget(self._meta_label)
        bottom_row.addStretch()

        self._save_state_label = QLabel("")
        self._save_state_label.setObjectName("Muted")
        bottom_row.addWidget(self._save_state_label)
        outer.addLayout(bottom_row)

        return bar

    def _set_has_open_summary(self, has_summary):
        self.print_button.setEnabled(has_summary)
        self.save_button.setEnabled(has_summary)
        self.overflow_button.setEnabled(has_summary)
        self._save_state_label.setText("Not saved" if has_summary else "")

    def set_current_patient(self, patient):
        self._name_label.setText(patient["patient_name"])
        self._meta_label.setText(f"BHT {patient['bht_number']} · Ward {patient['ward']}")
        self._set_has_open_summary(True)

    def _on_print(self):
        pass  # TODO(printing chunk): app/printing/layout.py + printer.py don't exist yet.

    def _on_save(self):
        pass  # TODO(db chunk): app/ui/editor_controller.py + app/db/summaries.py don't exist yet.

    def _on_duplicate(self):
        pass  # TODO(db chunk): needs a real summary to copy.

    def _on_delete(self):
        pass  # TODO(db chunk): needs the type-name-to-confirm dialog + soft-delete in the DB.
