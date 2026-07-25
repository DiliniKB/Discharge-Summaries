"""Investigations & Management section. Open by default. See docs/ui-spec.md
§3.3, §4.1.

Analyte value fields have NO numeric validator — docs/decisions.md is
explicit that investigations.value is TEXT, not REAL, because real lab
results include values like "<0.5" and "Not done"; a numeric validator
would reject exactly the inputs that column exists to hold.

Units are shown as placeholder text inside the (otherwise identically
short) analyte labels, not appended to the label itself — "SCr (µmol/L)"
next to "FBS" would force uneven column widths across the grid, undoing
the width-tier discipline from the Patient & Admission redesign.

Histology Report is an auto-growing text area, same as Management, even
though §4.5 only names Procedure Steps and Management explicitly —
histology reports are routinely multi-paragraph pathology text
(docs/schema.md: "often filled in after discharge"); a single-line box
here would reintroduce the exact problem just fixed for Clinical History.
"""

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from app import theme
from app.ui.widgets.autogrow_textedit import AutoGrowTextEdit
from app.ui.widgets.collapsible import CollapsibleSection
from app.ui.widgets.labeled import LabeledField

# (name, unit) — order matches the spec's two-row grid: FBS/SCr/AST/Na, then K/S Ca/Hb.
ANALYTES_ROW_1 = [("FBS", "mg/dL"), ("SCr", "µmol/L"), ("AST", "U/L"), ("Na", "mmol/L")]
ANALYTES_ROW_2 = [("K", "mmol/L"), ("S Ca", "mmol/L"), ("Hb", "g/dL")]


class _AdHocRow(QWidget):
    """One '+ Other' label:value pair, removable."""

    def __init__(self, on_remove, parent=None):
        super().__init__(parent)
        self._on_remove = on_remove

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.FIELD_GAP)

        self.label_input = _short_line_edit(placeholder="e.g. CRP")
        layout.addWidget(LabeledField("Label", self.label_input))

        self.value_input = _short_line_edit(placeholder="Value")
        layout.addWidget(LabeledField("Value", self.value_input))

        remove_button = QToolButton()
        remove_button.setText("✕")
        remove_button.clicked.connect(lambda: self._on_remove(self))
        layout.addWidget(LabeledField("", remove_button))  # blank label keeps vertical alignment with the row

        layout.addStretch()


def _short_line_edit(placeholder=""):
    box = QLineEdit()
    box.setPlaceholderText(placeholder)
    box.setMinimumHeight(theme.INPUT_HEIGHT_PX)
    box.setMaximumWidth(theme.WIDTH_S)
    box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return box


class InvestigationsSection(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__(title="Investigations & Management", collapsed=False, parent=parent)

        self.analyte_inputs = {}

        row1 = QHBoxLayout()
        row1.setSpacing(theme.FIELD_GAP)
        for name, unit in ANALYTES_ROW_1:
            box = _short_line_edit(placeholder=unit)
            self.analyte_inputs[name] = box
            row1.addWidget(LabeledField(name, box))
        row1.addStretch()
        self.body_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(theme.FIELD_GAP)
        for name, unit in ANALYTES_ROW_2:
            box = _short_line_edit(placeholder=unit)
            self.analyte_inputs[name] = box
            row2.addWidget(LabeledField(name, box))

        self.add_other_button = QPushButton("+ Other")
        self.add_other_button.setObjectName("SecondaryCompact")
        self.add_other_button.clicked.connect(self._add_other_row)
        row2.addWidget(LabeledField("", self.add_other_button))  # blank label, same reason as the remove button

        row2.addStretch()
        self.body_layout.addLayout(row2)

        self.other_rows_layout = QVBoxLayout()
        self.other_rows_layout.setSpacing(theme.FIELD_GAP)
        self.body_layout.addLayout(self.other_rows_layout)
        self.other_rows = []

        self.management_input = AutoGrowTextEdit(min_lines=3, max_lines=6)
        self.body_layout.addWidget(LabeledField("Management", self.management_input))

        self.histology_input = AutoGrowTextEdit(min_lines=2, max_lines=6)
        self.body_layout.addWidget(LabeledField("Histology Report", self.histology_input))

    def _add_other_row(self):
        row = _AdHocRow(on_remove=self._remove_other_row)
        self.other_rows_layout.addWidget(row)
        self.other_rows.append(row)

    def _remove_other_row(self, row):
        self.other_rows.remove(row)
        row.setParent(None)
        row.deleteLater()
