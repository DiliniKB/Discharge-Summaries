"""Cross-field date-order validation — warns, never raises."""

from app.util.validators import validate_date_order


def test_correctly_ordered_dates_produce_no_warnings():
    warnings = validate_date_order("2026-01-10", "2026-01-12", "2026-01-15")
    assert warnings == []


def test_surgery_before_admission_warns():
    warnings = validate_date_order("2026-01-10", "2026-01-05", "2026-01-15")
    assert warnings == ["Surgery date is before Admission date."]


def test_discharge_before_surgery_warns():
    warnings = validate_date_order("2026-01-10", "2026-01-12", "2026-01-11")
    assert warnings == ["Discharge date is before Surgery date."]


def test_discharge_before_admission_warns():
    warnings = validate_date_order("2026-01-10", "", "2026-01-05")
    assert warnings == ["Discharge date is before Admission date."]


def test_all_three_out_of_order_warns_for_each_pair():
    warnings = validate_date_order("2026-01-15", "2026-01-12", "2026-01-10")
    assert set(warnings) == {
        "Surgery date is before Admission date.",
        "Discharge date is before Surgery date.",
        "Discharge date is before Admission date.",
    }


def test_missing_dates_are_skipped_not_warned_about():
    assert validate_date_order("", "", "") == []
    assert validate_date_order("2026-01-10", "", "") == []
    assert validate_date_order("", "2026-01-12", "") == []


def test_equal_dates_are_not_a_warning():
    # Same-day admission/surgery/discharge is realistic (day surgery) —
    # only strictly-earlier is a warning, not "not later".
    warnings = validate_date_order("2026-01-10", "2026-01-10", "2026-01-10")
    assert warnings == []
