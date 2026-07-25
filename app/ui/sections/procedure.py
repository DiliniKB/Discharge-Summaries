"""Procedure section. Open by default. See docs/ui-spec.md §3.3, §4.3.

Template picker lives in the section HEADER (▼ PROCEDURE  [Template ▾]),
not the body — matching the spec's layout exactly, not just its field list.

Templates insert, they don't link (docs/decisions.md): selecting one copies
the template's body into Steps and resets the picker — an action, not a
persistent selection. Templates come from the real DB (app/db/templates.py)
via set_templates(), called once by MainWindow after querying it — this
section doesn't own a DB connection itself, same reasoning as the doctor
dropdown in main_window.py.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QLineEdit, QMessageBox

from app import theme
from app.ui.widgets.autogrow_textedit import AutoGrowTextEdit
from app.ui.widgets.collapsible import CollapsibleSection
from app.ui.widgets.labeled import LabeledField

TEMPLATE_PLACEHOLDER = "Insert template…"
MANAGE_TEMPLATES_LABEL = "Manage templates…"


class ProcedureSection(CollapsibleSection):
    manage_templates_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(title="Procedure", collapsed=False, parent=parent)

        self._templates_by_name = {}

        self.template_picker = QComboBox()
        self.template_picker.addItem(TEMPLATE_PLACEHOLDER)
        self.template_picker.setMaximumWidth(200)
        self.template_picker.setFocusPolicy(Qt.StrongFocus)  # macOS skips comboboxes on Tab by default; force it explicitly
        self.template_picker.currentIndexChanged.connect(self._on_template_selected)
        self.header_layout.addWidget(self.template_picker)

        self.title_input = QLineEdit()
        self.title_input.setObjectName("ProcedureTitleInput")
        self.title_input.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.body_layout.addWidget(LabeledField("Title", self.title_input))

        self.team_input = self._line_edit()
        self.body_layout.addWidget(LabeledField("Surgical Team", self.team_input))

        self.indication_input = self._line_edit()
        self.body_layout.addWidget(LabeledField("Indication", self.indication_input))

        self.steps_input = AutoGrowTextEdit(min_lines=3, max_lines=6)
        self.body_layout.addWidget(LabeledField("Procedure Steps", self.steps_input))

    def set_templates(self, templates):
        """templates: list of app.models.Template (active ones — see
        app/db/templates.py list_active())."""
        self._templates_by_name = {t.name: t.body for t in templates}
        self.template_picker.blockSignals(True)  # avoid firing _on_template_selected while rebuilding the list
        self.template_picker.clear()
        self.template_picker.addItem(TEMPLATE_PLACEHOLDER)
        self.template_picker.addItems(sorted(self._templates_by_name.keys()))
        self.template_picker.addItem(MANAGE_TEMPLATES_LABEL)
        self.template_picker.blockSignals(False)

    def _on_template_selected(self, index):
        if index <= 0:  # the placeholder itself, not a real template
            return
        name = self.template_picker.currentText()

        if name == MANAGE_TEMPLATES_LABEL:
            self.template_picker.setCurrentIndex(0)
            self.manage_templates_requested.emit()
            return

        # A doctor who's already typed steps and taps this dropdown out of
        # habit shouldn't lose that work silently — this would be worse
        # than a crash (CLAUDE.md: "a crash must cost one field, not one
        # card"), since there'd be no error to notice, just gone text.
        if self.steps_input.toPlainText().strip():
            reply = QMessageBox.question(
                self,
                "Replace procedure steps?",
                f'"{name}" will replace the steps already typed here. Continue?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self.template_picker.setCurrentIndex(0)
                return

        self.steps_input.setPlainText(self._templates_by_name[name])
        self.template_picker.setCurrentIndex(0)  # action, not a persistent selection
        # setPlainText() doesn't trigger editingFinished (no focus change
        # happened) — without this, Ctrl+S right after inserting a
        # template (before ever blurring Steps) would silently miss it.
        self.steps_input.editingFinished.emit()

    def bind_controller(self, controller):
        self.title_input.editingFinished.connect(lambda: controller.set_field("procedure_title", self.title_input.text()))
        self.team_input.editingFinished.connect(lambda: controller.set_field("surgical_team", self.team_input.text()))
        self.indication_input.editingFinished.connect(lambda: controller.set_field("indication", self.indication_input.text()))
        self.steps_input.editingFinished.connect(lambda: controller.set_field("procedure_steps", self.steps_input.toPlainText()))

    def populate(self, summary):
        self.title_input.setText(summary.procedure_title or "")
        self.team_input.setText(summary.surgical_team or "")
        self.indication_input.setText(summary.indication or "")
        self.steps_input.setPlainText(summary.procedure_steps or "")

    def _line_edit(self):
        box = QLineEdit()
        box.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        return box
