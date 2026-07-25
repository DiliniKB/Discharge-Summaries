"""Procedure section. Open by default. See docs/ui-spec.md §3.3, §4.3.

Template picker lives in the section HEADER (▼ PROCEDURE  [Template ▾]),
not the body — matching the spec's layout exactly, not just its field list.

Templates insert, they don't link (docs/decisions.md): selecting one copies
fixture text into Steps and resets the picker — an action, not a
persistent selection. No real templates table yet (DB-layer chunk), so
this uses fixture data the same way the doctor dropdown and patient list
fixtures do.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QMessageBox

from app import theme
from app.ui.widgets.autogrow_textedit import AutoGrowTextEdit
from app.ui.widgets.collapsible import CollapsibleSection
from app.ui.widgets.labeled import LabeledField

TEMPLATE_PLACEHOLDER = "Insert template…"

FIXTURE_TEMPLATES = {
    "Thyroid lobectomy": (
        "1. GA induced, patient supine, neck extended.\n"
        "2. Collar incision, subplatysmal flaps raised.\n"
        "3. Strap muscles separated in the midline.\n"
        "4. Affected lobe mobilised, isthmus divided.\n"
        "5. Haemostasis secured, wound closed in layers."
    ),
    "Complete thyroidectomy": (
        "1. GA induced, patient supine, neck extended.\n"
        "2. Collar incision, subplatysmal flaps raised.\n"
        "3. Both lobes mobilised and delivered.\n"
        "4. Parathyroids identified and preserved.\n"
        "5. Haemostasis secured, wound closed in layers."
    ),
    "Total mastectomy": (
        "1. GA induced, patient supine, arm abducted.\n"
        "2. Elliptical incision around the breast.\n"
        "3. Skin flaps raised, breast tissue excised off pectoralis fascia.\n"
        "4. Haemostasis secured, drain placed.\n"
        "5. Wound closed in layers."
    ),
}


class ProcedureSection(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__(title="Procedure", collapsed=False, parent=parent)

        self.template_picker = QComboBox()
        self.template_picker.addItem(TEMPLATE_PLACEHOLDER)
        self.template_picker.addItems(sorted(FIXTURE_TEMPLATES.keys()))
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

    def _on_template_selected(self, index):
        if index <= 0:  # the placeholder itself, not a real template
            return
        name = self.template_picker.currentText()

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

        self.steps_input.setPlainText(FIXTURE_TEMPLATES[name])
        self.template_picker.setCurrentIndex(0)  # action, not a persistent selection

    def _line_edit(self):
        box = QLineEdit()
        box.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        return box
