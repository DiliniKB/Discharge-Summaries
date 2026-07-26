"""Patient & Admission section. Open by default. See docs/ui-spec.md §3.3.

Fields use a fixed set of width tiers (theme.WIDTH_XS/S/M) rather than a
one-off pixel value per field — same-class fields (Sex/Blood Group as
short codes, BHT/dates as medium identifiers) share a tier so the form
reads as one designed system, not each field guessed independently.

Each logical row-group (identity codes / contact+physical / dates) gets
its own layout rather than one shared QGridLayout across all of them.
They're not a real table — there's no meaningful reason Age should share
a column width with Date of Admission — and a shared grid forces Qt to
size each column by the widest demand across every row that touches it,
which visibly distorts groups that have nothing to do with each other.

Cross-field date-order validation (§4.2) lives in app/util/validators.py
per CLAUDE.md's planned layout — this section only calls it and displays
the result. Same as duplicate BHT and the abnormal-lab styling
(app/ui/sections/investigations.py), it warns, never blocks: an unusual
but correct date order must still be saveable immediately.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QSizePolicy

from app import theme
from app.ui.widgets.collapsible import CollapsibleSection
from app.ui.widgets.datefield import DateField
from app.ui.widgets.labeled import LabeledField
from app.util.validators import validate_date_order

DEFAULT_WARD = "45"  # docs/schema.md: ward TEXT, "Defaults to 45"

# A rushed doctor typing free text produces "O positive" / "o+" / "O Positive"
# inconsistently for a field that exists specifically because it's clinically
# needed (docs/decisions.md). Constrained the same way Sex already is.
BLOOD_GROUPS = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


class PatientSection(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__(title="Patient & Admission", collapsed=False, parent=parent)

        # Name — the one field that should expand with the window.
        self.name_input = self._line_edit()
        self.body_layout.addWidget(LabeledField("Name", self.name_input, required=True))

        # Identity codes — compact, own row, own width negotiation.
        identity_row = QHBoxLayout()
        identity_row.setSpacing(theme.FIELD_GAP)

        self.age_input = self._line_edit(theme.WIDTH_XS)
        self.age_input.setValidator(QIntValidator(0, 150, self.age_input))
        identity_row.addWidget(LabeledField("Age", self.age_input))

        self.sex_input = QComboBox()
        self.sex_input.addItems(["", "Female", "Male"])
        self.sex_input.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.sex_input.setMaximumWidth(theme.WIDTH_S)
        self.sex_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # macOS restricts Tab to text fields/lists by default (Cocoa HI
        # guideline), skipping comboboxes regardless of their reported
        # focusPolicy — confirmed by testing, not assumed. Windows doesn't
        # have this restriction, but CLAUDE.md's "keyboard-first" tab-order
        # requirement shouldn't rest on an OS default either way.
        self.sex_input.setFocusPolicy(Qt.StrongFocus)
        identity_row.addWidget(LabeledField("Sex", self.sex_input))

        self.bht_input = self._line_edit(theme.WIDTH_M)
        identity_row.addWidget(LabeledField("BHT Number", self.bht_input, required=True))

        self.ward_input = self._line_edit(theme.WIDTH_XS)
        self.ward_input.setText(DEFAULT_WARD)
        identity_row.addWidget(LabeledField("Ward", self.ward_input))

        identity_row.addStretch()
        self.body_layout.addLayout(identity_row)

        # Contact / physical — Telephone expands a little, Blood Group stays compact.
        contact_row = QHBoxLayout()
        contact_row.setSpacing(theme.FIELD_GAP)

        self.telephone_input = self._line_edit(theme.WIDTH_TELEPHONE)
        contact_row.addWidget(LabeledField("Telephone", self.telephone_input))

        self.blood_group_input = QComboBox()
        self.blood_group_input.addItems(BLOOD_GROUPS)
        self.blood_group_input.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.blood_group_input.setMaximumWidth(theme.WIDTH_S)
        self.blood_group_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.blood_group_input.setFocusPolicy(Qt.StrongFocus)  # see Sex combobox comment above
        contact_row.addWidget(LabeledField("Blood Group", self.blood_group_input))

        contact_row.addStretch()
        self.body_layout.addLayout(contact_row)

        # The three dates — one temporal sequence, own row, own width negotiation.
        dates_row = QHBoxLayout()
        dates_row.setSpacing(theme.FIELD_GAP)

        self.admission_date = DateField()
        dates_row.addWidget(LabeledField("Date of Admission", self.admission_date))

        self.surgery_date = DateField()
        dates_row.addWidget(LabeledField("Date of Surgery", self.surgery_date))

        self.discharge_date = DateField()
        # Discharge summaries are filled in around discharge time, so
        # "today" is usually right. Admission/Surgery are almost always
        # past dates by then — defaulting those to today would be wrong
        # more often than not, so they stay blank.
        self.discharge_date.set_today()
        dates_row.addWidget(LabeledField("Date of Discharge", self.discharge_date))

        dates_row.addStretch()
        self.body_layout.addLayout(dates_row)

        # Hidden until _revalidate_dates() finds an out-of-order pair —
        # never blocks saving, just prompts a second look (see module docstring).
        self._date_warning_label = QLabel("")
        self._date_warning_label.setObjectName("Danger")
        self._date_warning_label.setWordWrap(True)
        self._date_warning_label.setVisible(False)
        self.body_layout.addWidget(self._date_warning_label)

    def bind_controller(self, controller):
        """Wires every field's blur to controller.set_field(). Called once
        by Editor after construction — see app/ui/editor_controller.py."""
        self.name_input.editingFinished.connect(lambda: controller.set_field("patient_name", self.name_input.text()))
        self.age_input.editingFinished.connect(lambda: controller.set_field("age", int(self.age_input.text()) if self.age_input.text() else None))
        self.sex_input.currentTextChanged.connect(lambda text: controller.set_field("sex", text))
        self.bht_input.editingFinished.connect(lambda: controller.set_field("bht_number", self.bht_input.text()))
        self.ward_input.editingFinished.connect(lambda: controller.set_field("ward", self.ward_input.text()))
        self.telephone_input.editingFinished.connect(lambda: controller.set_field("telephone", self.telephone_input.text()))
        self.blood_group_input.currentTextChanged.connect(lambda text: controller.set_field("blood_group", text))
        self.admission_date.value_changed.connect(lambda iso: controller.set_field("date_admission", iso))
        self.surgery_date.value_changed.connect(lambda iso: controller.set_field("date_surgery", iso))
        self.discharge_date.value_changed.connect(lambda iso: controller.set_field("date_discharge", iso))
        self.admission_date.value_changed.connect(self._revalidate_dates)
        self.surgery_date.value_changed.connect(self._revalidate_dates)
        self.discharge_date.value_changed.connect(self._revalidate_dates)

    def _revalidate_dates(self, *_args):
        """*_args absorbs value_changed's str payload — the check reads
        the three fields' current state directly rather than the single
        changed value, since a warning can depend on any pair of them."""
        warnings = validate_date_order(
            self.admission_date.get_iso(),
            self.surgery_date.get_iso(),
            self.discharge_date.get_iso(),
        )
        self._date_warning_label.setText(" ".join(warnings))
        self._date_warning_label.setVisible(bool(warnings))

    def populate(self, summary):
        """Fills every field from a Summary — the reverse of bind_controller.
        Setting text programmatically here doesn't itself trigger a save
        (setText() doesn't fire editingFinished, and a combobox's
        currentTextChanged firing is harmless — the controller's own diff
        guard sees it matches the just-loaded snapshot and no-ops)."""
        self.name_input.setText(summary.patient_name)
        self.age_input.setText(str(summary.age) if summary.age is not None else "")
        self.sex_input.setCurrentText(summary.sex or "")
        self.bht_input.setText(summary.bht_number)
        self.ward_input.setText(summary.ward or "")
        self.telephone_input.setText(summary.telephone or "")
        self.blood_group_input.setCurrentText(summary.blood_group or "")
        self.admission_date.set_iso(summary.date_admission or "")
        self.surgery_date.set_iso(summary.date_surgery or "")
        self.discharge_date.set_iso(summary.date_discharge or "")
        self._revalidate_dates()

    def _line_edit(self, max_width=None):
        box = QLineEdit()
        box.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        if max_width:
            box.setMaximumWidth(max_width)
            # QLineEdit defaults to a horizontally Expanding size policy —
            # without pinning it Fixed, the wrapping LabeledField claims
            # far more row space than the capped widget actually uses.
            box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return box
