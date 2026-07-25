"""Clinical History section: collapsed by default, live 'n of 6 filled' counter."""

from app.ui.sections.clinical_history import ClinicalHistorySection


def test_starts_collapsed_with_zero_counter():
    sec = ClinicalHistorySection()
    sec.show()

    assert sec._title.text() == "CLINICAL HISTORY"
    assert sec.expanded is False
    assert sec.body.isVisible() is False
    assert sec._counter.text() == "0 of 6 filled"
    assert len(sec._fields) == 6


def test_counter_tracks_filled_fields_live():
    sec = ClinicalHistorySection()
    sec.show()

    sec.presenting_complaint_input.setPlainText("Neck swelling")
    assert sec._counter.text() == "1 of 6 filled"

    sec.allergies_input.setPlainText("NKDA")
    sec.findings_input.setPlainText("Firm, non-tender mass")
    assert sec._counter.text() == "3 of 6 filled"

    sec.allergies_input.clear()
    assert sec._counter.text() == "2 of 6 filled", "counter decreases when a field is cleared"

    sec.presenting_complaint_input.setPlainText("   ")
    assert sec._counter.text() == "1 of 6 filled", "whitespace-only text doesn't count as filled"


def test_clicking_the_header_expands_it():
    sec = ClinicalHistorySection()
    sec.show()
    sec._toggle()
    assert sec.expanded is True
    assert sec.body.isVisible() is True
