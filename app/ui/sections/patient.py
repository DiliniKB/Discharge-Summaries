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

Name/Telephone/BHT format validation is different, and deliberately so:
an invalid value there is never handed to controller.set_field() at
all — that one field simply doesn't save until it's fixed, a real
block, not a warning. This was an explicit request (docs/decisions.md),
not this section improvising past the app's usual "warn, don't block"
convention. It's scoped per field, not per record — an invalid BHT
doesn't stop Name (or anything else already valid) from autosaving.

The invalid/red flag only ever appears from this section's OWN blur
handlers, never from populate() — a freshly created blank card (or an
older record saved before this validation existed) must open looking
normal, not already flagged red before the user has touched anything.
populate() explicitly clears the flag on every load for this reason.

Per-field blocking above stops a bad EDIT from being written, but a
brand-new card's Name/Telephone/BHT start out blank regardless — that
row is created directly via summaries.create(), bypassing this section
entirely — so blocking only the edit doesn't stop the record as a whole
from being treated as "done" while still incomplete. validity_changed
(emitted after every blur here, and after populate()) reports the
section's REAL current validity even when nothing is shown red yet;
Editor uses it to disable Save/Print until Name, Telephone, and BHT are
all actually valid, not just "not currently flagged."

Name typeahead: typing (debounced 150ms) into Name searches past
admissions by substring (app/db/summaries.py::search_patients_by_name)
and shows them via a QCompleter in UnfilteredPopupCompletion mode — the
matches are already filtered server-side, so Qt's own prefix filtering
would be redundant (and wrong: our LIKE is substring, Qt's default is
prefix). QCompleter, not a hand-rolled Qt.Popup window, deliberately:
it's Qt's own battle-tested "popup below a QLineEdit" mechanism, used
internally for exactly this shape of UI everywhere from address bars to
file dialogs, and by design never steals editing focus from the line
edit it's attached to — a custom Qt.Popup QListWidget was tried first
and failed twice in real use (docs/decisions.md) for reasons a
hand-rolled popup has to solve itself and QCompleter already solves.

Picking a suggestion autofills Age/Sex/Telephone/Blood Group from that
admission — through the SAME blur handlers a manual edit would use, so
it's saved and validated identically, not a separate path. BHT is
deliberately NOT autofilled: whether this admission continues under the
same BHT or needs a new one is a clinical decision, not something to
guess on the doctor's behalf — a note names the old BHT instead, so the
doctor can decide.
"""

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QComboBox, QCompleter, QHBoxLayout, QLabel, QLineEdit, QSizePolicy

from app import theme
from app.db import summaries
from app.models import DEFAULT_WARD
from app.printing import layout as print_layout
from app.ui.widgets.collapsible import CollapsibleSection
from app.ui.widgets.datefield import DateField
from app.ui.widgets.labeled import LabeledField
from app.util.validators import validate_bht, validate_date_order, validate_name, validate_telephone

# A rushed doctor typing free text produces "O positive" / "o+" / "O Positive"
# inconsistently for a field that exists specifically because it's clinically
# needed (docs/decisions.md). Constrained the same way Sex already is.
BLOOD_GROUPS = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

_NAME_ERROR = "Name is required."
_BHT_ERROR = "BHT number must be in the format number-year, e.g. 12345-2026."
_TELEPHONE_ERROR = "Enter a valid 10-digit phone number starting with 0, e.g. 0771234567."

_NAME_SEARCH_MIN_CHARS = 2
_NAME_SEARCH_DEBOUNCE_MS = 150
_NAME_SEARCH_MAX_RESULTS = 5


class PatientSection(CollapsibleSection):
    # Emitted with the section's real current validity (Name/Telephone/BHT
    # all pass, or not) after every blur that could change it, and after
    # populate(). Editor listens so it can disable Save/Print until all
    # three are actually valid — see module docstring.
    validity_changed = Signal(bool)

    # Emitted with the full matched row after a typeahead selection —
    # this section only owns/autofills its own Age/Sex/Telephone/Blood
    # Group fields; Past Medical/Surgical History and Allergies belong to
    # ClinicalHistorySection, which Editor (not this section) has a
    # reference to. Same "announce, don't reach into a sibling" shape as
    # Editor's own duplicated/deleted signals.
    name_suggestion_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(title="Patient & Admission", collapsed=False, parent=parent)
        self._controller = None
        self._name_matches = []  # current debounced query's rows, parallel to the completer's string list

        # Name — the one field that should expand with the window.
        self.name_input = self._line_edit()
        self.body_layout.addWidget(LabeledField("Name", self.name_input, required=True))
        self._name_error_label = self._make_error_label()
        self.body_layout.addWidget(self._name_error_label)
        self._bht_note_label = QLabel("")
        self._bht_note_label.setObjectName("Muted")
        self._bht_note_label.setWordWrap(True)
        self._bht_note_label.setVisible(False)
        self.body_layout.addWidget(self._bht_note_label)

        # Qt's own popup-below-a-QLineEdit mechanism (module docstring) —
        # UnfilteredPopupCompletion shows the model's current contents
        # as-is, since search_patients_by_name() already did the actual
        # filtering server-side.
        self._name_completer = QCompleter([], self)
        self._name_completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.name_input.setCompleter(self._name_completer)
        self._name_completer.activated[str].connect(self._on_name_suggestion_activated)

        self._name_search_debounce = QTimer(self)
        self._name_search_debounce.setSingleShot(True)
        self._name_search_debounce.timeout.connect(self._show_name_suggestions)
        # textEdited (not textChanged) fires only on actual user typing —
        # our own setText() calls (autofill, populate()) must NOT re-open
        # this popup on themselves.
        self.name_input.textEdited.connect(self._on_name_text_edited)

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
        # One shared error label below the row, same shape as the date
        # warning label below dates_row — BHT is the only field in this
        # row with a format to validate, so it's the only one that ever
        # populates this text.
        self._bht_error_label = self._make_error_label()
        self.body_layout.addWidget(self._bht_error_label)

        # Contact / physical — Telephone expands a little, Blood Group stays compact.
        contact_row = QHBoxLayout()
        contact_row.setSpacing(theme.FIELD_GAP)

        self.telephone_input = self._line_edit(theme.WIDTH_TELEPHONE)
        contact_row.addWidget(LabeledField("Telephone", self.telephone_input, required=True))

        self.blood_group_input = QComboBox()
        self.blood_group_input.addItems(BLOOD_GROUPS)
        self.blood_group_input.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.blood_group_input.setMaximumWidth(theme.WIDTH_S)
        self.blood_group_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.blood_group_input.setFocusPolicy(Qt.StrongFocus)  # see Sex combobox comment above
        contact_row.addWidget(LabeledField("Blood Group", self.blood_group_input))

        contact_row.addStretch()
        self.body_layout.addLayout(contact_row)
        self._telephone_error_label = self._make_error_label()
        self.body_layout.addWidget(self._telephone_error_label)

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
        by Editor after construction — see app/ui/editor_controller.py.

        Name/Telephone/BHT go through a validate-then-maybe-save wrapper
        instead of calling set_field() directly — an invalid value is
        flagged and simply never handed to the controller, so it can't
        reach the DB. Every other field here still saves unconditionally
        on blur, same as before."""
        self._controller = controller  # needed by the name-typeahead selection handler, outside any blur
        self.name_input.editingFinished.connect(lambda: self._on_name_blur(controller))
        self.age_input.editingFinished.connect(lambda: controller.set_field("age", int(self.age_input.text()) if self.age_input.text() else None))
        self.sex_input.currentTextChanged.connect(lambda text: controller.set_field("sex", text))
        self.bht_input.editingFinished.connect(lambda: self._on_bht_blur(controller))
        self.ward_input.editingFinished.connect(lambda: controller.set_field("ward", self.ward_input.text()))
        self.telephone_input.editingFinished.connect(lambda: self._on_telephone_blur(controller))
        self.blood_group_input.currentTextChanged.connect(lambda text: controller.set_field("blood_group", text))
        self.admission_date.value_changed.connect(lambda iso: controller.set_field("date_admission", iso))
        self.surgery_date.value_changed.connect(lambda iso: controller.set_field("date_surgery", iso))
        self.discharge_date.value_changed.connect(lambda iso: controller.set_field("date_discharge", iso))
        self.admission_date.value_changed.connect(self._revalidate_dates)
        self.surgery_date.value_changed.connect(self._revalidate_dates)
        self.discharge_date.value_changed.connect(self._revalidate_dates)

    def _on_name_blur(self, controller):
        text = self.name_input.text()
        valid = validate_name(text)
        self._set_field_validity(self.name_input, self._name_error_label, valid, _NAME_ERROR)
        if valid:
            controller.set_field("patient_name", text)
        self.validity_changed.emit(self.is_valid())

    def _on_bht_blur(self, controller):
        text = self.bht_input.text()
        valid = validate_bht(text)
        self._set_field_validity(self.bht_input, self._bht_error_label, valid, _BHT_ERROR)
        if valid:
            controller.set_field("bht_number", text)
        # The doctor has now made their own call on this admission's BHT
        # (per the typeahead note below) — stop showing the old one.
        self._bht_note_label.setVisible(False)
        self.validity_changed.emit(self.is_valid())

    def _on_telephone_blur(self, controller):
        text = self.telephone_input.text()
        valid = validate_telephone(text)
        self._set_field_validity(self.telephone_input, self._telephone_error_label, valid, _TELEPHONE_ERROR)
        if valid:
            controller.set_field("telephone", text)
        self.validity_changed.emit(self.is_valid())

    def _on_name_text_edited(self, _text):
        self._name_search_debounce.start(_NAME_SEARCH_DEBOUNCE_MS)

    def _show_name_suggestions(self):
        """Queries past admissions matching the current Name text and
        loads them into the completer's model — only once a summary is
        actually open (nothing to autofill into otherwise) and the query
        is long enough to be a real search, not noise on the first
        keystroke."""
        self._name_matches = []
        if self._controller is None or self._controller.summary_id is None:
            return
        query = self.name_input.text().strip()
        if len(query) < _NAME_SEARCH_MIN_CHARS:
            return

        matches = summaries.search_patients_by_name(
            self._controller.conn, query, exclude_id=self._controller.summary_id, limit=_NAME_SEARCH_MAX_RESULTS
        )
        if not matches:
            return

        self._name_matches = matches
        display_strings = [
            f"{row['patient_name']}   ·   BHT {row['bht_number']}   ·   "
            f"{print_layout.format_date(row['date_discharge']) or 'not discharged'}"
            for row in matches
        ]
        self._name_completer.model().setStringList(display_strings)
        self._name_completer.complete()

    def _on_name_suggestion_activated(self, display_text):
        """Autofills Age/Sex/Telephone/Blood Group from the selected past
        admission — through the SAME blur handlers a manual edit would
        use (_on_name_blur/_on_telephone_blur), so this is validated and
        saved identically to typing it in by hand, not a separate path.
        BHT is deliberately left for the doctor to decide (module
        docstring). Matched by display string against this section's own
        last query results — set together in _show_name_suggestions, so
        they're always in step."""
        try:
            index = self._name_completer.model().stringList().index(display_text)
        except ValueError:
            return
        row = self._name_matches[index]

        self.name_input.setText(row["patient_name"])
        self.age_input.setText(str(row["age"]) if row["age"] is not None else "")
        self.sex_input.setCurrentText(row["sex"] or "")  # fires currentTextChanged -> saves itself
        self.telephone_input.setText(row["telephone"] or "")
        self.blood_group_input.setCurrentText(row["blood_group"] or "")  # fires currentTextChanged -> saves itself

        self._on_name_blur(self._controller)
        self._on_telephone_blur(self._controller)
        self._controller.set_field("age", int(self.age_input.text()) if self.age_input.text() else None)

        discharge = print_layout.format_date(row["date_discharge"]) or "not discharged (still admitted)"
        self._bht_note_label.setText(
            f"This patient's last BHT was {row['bht_number']} ({discharge}). Enter this admission's BHT yourself — "
            f"the same number if this continues that admission, a new one if it doesn't."
        )
        self._bht_note_label.setVisible(True)

        # Past Medical/Surgical History + Allergies belong to
        # ClinicalHistorySection, which this section has no reference to —
        # Editor listens and fills those in (module docstring).
        self.name_suggestion_selected.emit(row)

    def is_valid(self):
        """The section's real current validity — Name/Telephone/BHT all
        pass — regardless of whether any of them is currently shown red.
        A brand-new card is correctly invalid here (blank Name/BHT/
        Telephone) even though nothing is flagged yet, since nothing's
        been blurred (docs/decisions.md)."""
        return not self.missing_required_fields()

    def missing_required_fields(self):
        """Labels of whichever required fields are currently invalid.
        Nothing here shows red until the user's own blur (module
        docstring), so a silently-disabled Save/Print needs another way
        to say why — Editor uses this to fill in the actual field
        names rather than leaving the doctor to guess."""
        missing = []
        if not validate_name(self.name_input.text()):
            missing.append("Name")
        if not validate_telephone(self.telephone_input.text()):
            missing.append("Telephone")
        if not validate_bht(self.bht_input.text()):
            missing.append("BHT")
        return missing

    @staticmethod
    def _set_field_validity(widget, error_label, valid, message):
        """Same unpolish()/polish() idiom as _PatientCard.set_selected()
        (app/ui/patient_list.py) and the investigations abnormal-value
        flag — dynamic Qt properties need it to actually repaint."""
        widget.setProperty("invalid", not valid)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        error_label.setText("" if valid else message)
        error_label.setVisible(not valid)

    def _make_error_label(self):
        label = QLabel("")
        label.setObjectName("Danger")
        label.setWordWrap(True)
        label.setVisible(False)
        return label

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
        self.ward_input.setText(summary.ward or DEFAULT_WARD)
        self.telephone_input.setText(summary.telephone or "")
        self.blood_group_input.setCurrentText(summary.blood_group or "")
        self.admission_date.set_iso(summary.date_admission or "")
        self.surgery_date.set_iso(summary.date_surgery or "")
        self.discharge_date.set_iso(summary.date_discharge or "")
        self._revalidate_dates()
        # Always cleared here, regardless of whether the loaded data is
        # actually valid — a brand-new blank card (or any record with a
        # not-yet-conforming Telephone/BHT saved before this validation
        # existed) must not show red the instant it's opened, only after
        # the user actually blurs an invalid value themselves. Also
        # prevents a previous record's red state leaking onto the next
        # one when switching cards.
        self._set_field_validity(self.name_input, self._name_error_label, True, _NAME_ERROR)
        self._set_field_validity(self.bht_input, self._bht_error_label, True, _BHT_ERROR)
        self._set_field_validity(self.telephone_input, self._telephone_error_label, True, _TELEPHONE_ERROR)
        # Not shown red (above), but Save/Print must still reflect REAL
        # validity — a freshly created or reopened record with a blank/
        # invalid required field is not actually ready to be treated as
        # done, even though nothing here looks alarming yet.
        self.validity_changed.emit(self.is_valid())
        # A stale debounce/popup/note from whatever was open before must
        # not carry over onto the newly loaded record.
        self._name_search_debounce.stop()
        self._name_completer.popup().hide()
        self._bht_note_label.setVisible(False)

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
