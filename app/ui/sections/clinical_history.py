"""Clinical History section. Collapsed by default, with a live 'n of 6
filled' counter. See docs/ui-spec.md §3.3, docs/decisions.md.

On the sample card these six fields were all blank — collapsed-with-a-
counter means nothing is hidden (the count says there's content) while the
fields actually in use get the top of the screen.

Fields are small auto-growing text areas (1-3 lines), not rigid single-line
boxes: entries like "Past Medical History" or "Examination" routinely run
longer than one line in real use ("DM type 2 on metformin, HTN on
amlodipine, IHD s/p PCI 2019"), and a single-line box forces internal
horizontal scrolling to review — bad for a doctor cross-checking against
the paper form at a glance. Smaller cap than Procedure Steps (§4.5's
6-line auto-grow), since these are meant to stay compact, not become a
second free-text essay field.
"""

from app.ui.widgets.autogrow_textedit import AutoGrowTextEdit
from app.ui.widgets.collapsible import CollapsibleSection
from app.ui.widgets.labeled import LabeledField


class ClinicalHistorySection(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__(title="Clinical History", collapsed=True, parent=parent)

        self.presenting_complaint_input = self._text_area()
        self.body_layout.addWidget(LabeledField("Presenting Complaint", self.presenting_complaint_input))

        self.past_medical_history_input = self._text_area()
        self.body_layout.addWidget(LabeledField("Past Medical History", self.past_medical_history_input))

        self.past_surgical_history_input = self._text_area()
        self.body_layout.addWidget(LabeledField("Past Surgical History", self.past_surgical_history_input))

        self.allergies_input = self._text_area()
        self.body_layout.addWidget(LabeledField("Allergies", self.allergies_input))

        self.examination_input = self._text_area()
        self.body_layout.addWidget(LabeledField("Examination", self.examination_input))

        self.findings_input = self._text_area()
        self.body_layout.addWidget(LabeledField("Findings", self.findings_input))

        self._fields = [
            self.presenting_complaint_input,
            self.past_medical_history_input,
            self.past_surgical_history_input,
            self.allergies_input,
            self.examination_input,
            self.findings_input,
        ]
        for field in self._fields:
            field.textChanged.connect(self._update_counter)
        self._update_counter()

    def _update_counter(self):
        filled = sum(1 for field in self._fields if field.toPlainText().strip())
        self.set_counter(f"{filled} of {len(self._fields)} filled")

    def _text_area(self):
        return AutoGrowTextEdit(min_lines=1, max_lines=3)
