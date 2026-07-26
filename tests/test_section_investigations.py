"""Investigations & Management section: the 7 fixed analytes (no numeric
validator — docs/decisions.md), '+ Other' ad-hoc rows, auto-growing text areas."""

from app.ui.sections.investigations import ANALYTES_ROW_1, ANALYTES_ROW_2, InvestigationsSection


class _StubController:
    """bind_controller() only needs set_field/set_investigation to exist —
    the abnormal-styling tests care about the property, not persistence."""

    def set_field(self, *args, **kwargs):
        pass

    def set_investigation(self, *args, **kwargs):
        pass


def test_section_title_and_seven_fixed_analytes():
    sec = InvestigationsSection()
    sec.show()

    assert sec._title.text() == "INVESTIGATIONS & MANAGEMENT"
    assert sec.expanded is True

    expected = {name for name, _ in ANALYTES_ROW_1 + ANALYTES_ROW_2}
    assert set(sec.analyte_inputs.keys()) == expected
    assert len(sec.analyte_inputs) == 7


def test_analyte_fields_accept_non_numeric_lab_results():
    # docs/decisions.md: investigations.value is TEXT, not REAL — "<0.5"
    # and "Not done" are real lab results, not invalid input.
    sec = InvestigationsSection()
    sec.show()

    sec.analyte_inputs["FBS"].setText("86")
    sec.analyte_inputs["SCr"].setText("<0.5")
    sec.analyte_inputs["Hb"].setText("Not done")

    assert sec.analyte_inputs["FBS"].text() == "86"
    assert sec.analyte_inputs["SCr"].text() == "<0.5"
    assert sec.analyte_inputs["Hb"].text() == "Not done"
    assert sec.analyte_inputs["FBS"].validator() is None


def test_analyte_placeholder_shows_the_unit_not_the_label():
    sec = InvestigationsSection()
    sec.show()
    assert sec.analyte_inputs["FBS"].placeholderText() == "mg/dL"
    assert sec.analyte_inputs["SCr"].placeholderText() == "µmol/L"


def test_add_other_rows_add_fill_and_remove():
    sec = InvestigationsSection()
    sec.show()
    assert len(sec.other_rows) == 0

    sec.add_other_button.click()
    assert len(sec.other_rows) == 1

    row = sec.other_rows[0]
    row.label_input.setText("CRP")
    row.value_input.setText("12")
    assert row.label_input.text() == "CRP"
    assert row.value_input.text() == "12"

    sec.add_other_button.click()
    assert len(sec.other_rows) == 2

    first_row = sec.other_rows[0]
    sec._remove_other_row(first_row)
    assert len(sec.other_rows) == 1
    assert sec.other_rows[0] is not first_row, "the remaining row is the second one added"


def test_management_and_histology_are_auto_growing():
    sec = InvestigationsSection()
    sec.show()
    assert hasattr(sec.management_input, "_adjust_height")
    assert hasattr(sec.histology_input, "_adjust_height")

    sec.management_input.setPlainText("T. Paracetamol 1g PO PRN")
    assert sec.management_input.toPlainText() == "T. Paracetamol 1g PO PRN"


def test_out_of_range_value_flags_abnormal_on_blur():
    # FBS normal range is 70-100 (app/util/lab_ranges.py) — 250 is well outside it.
    sec = InvestigationsSection()
    sec.show()
    sec.bind_controller(_StubController())
    fbs = sec.analyte_inputs["FBS"]

    fbs.setText("250")
    fbs.editingFinished.emit()
    assert fbs.property("abnormal") is True


def test_normal_value_clears_abnormal_flag():
    sec = InvestigationsSection()
    sec.show()
    sec.bind_controller(_StubController())
    fbs = sec.analyte_inputs["FBS"]

    fbs.setText("250")
    fbs.editingFinished.emit()
    assert fbs.property("abnormal") is True

    fbs.setText("86")
    fbs.editingFinished.emit()
    assert fbs.property("abnormal") is False


def test_non_numeric_lab_result_never_flagged_abnormal():
    # docs/decisions.md: "<0.5" / "Not done" are real lab results, not
    # invalid input — there's nothing numeric to compare against a range.
    sec = InvestigationsSection()
    sec.show()
    sec.bind_controller(_StubController())
    scr = sec.analyte_inputs["SCr"]

    scr.setText("<0.5")
    scr.editingFinished.emit()
    assert scr.property("abnormal") is False


def test_populate_flags_a_saved_abnormal_value_immediately():
    from app.models import Summary

    sec = InvestigationsSection()
    sec.show()
    summary = Summary(patient_name="Test Patient", bht_number="1")
    investigations_by_label = {"K": {"value": "6.8"}, "FBS": {"value": "86"}}

    sec.populate(summary, investigations_by_label)

    assert sec.analyte_inputs["K"].property("abnormal") is True
    assert sec.analyte_inputs["FBS"].property("abnormal") is False
