"""Field-level validation (Name/Telephone/BHT format — blocks the save
for that field) and cross-field date-order validation (warns, never
raises)."""

import pytest

from app.util.validators import validate_bht, validate_date_order, validate_name, validate_telephone


@pytest.mark.parametrize("name", ["W.D. Kusuma Wijerathna", "A", "  Trimmed Inside  "])
def test_non_blank_name_is_valid(name):
    assert validate_name(name) is True


@pytest.mark.parametrize("name", ["", "   ", None])
def test_blank_name_is_invalid(name):
    assert validate_name(name) is False


@pytest.mark.parametrize("bht", ["12345-2026", "1-2026", "999999-2026"])
def test_number_hyphen_year_bht_is_valid(bht):
    assert validate_bht(bht) is True


@pytest.mark.parametrize(
    "bht",
    [
        "",
        "12345",           # no year at all
        "12345-26",        # 2-digit year, not 4
        "12345/2026",      # slash, not hyphen
        "abc-2026",        # not digits before the hyphen
        "12345-abcd",      # not digits after the hyphen
        "-2026",           # no digits before the hyphen
        "12345-",          # no year after the hyphen
    ],
)
def test_malformed_bht_is_invalid(bht):
    assert validate_bht(bht) is False


def test_blank_telephone_is_invalid_the_field_is_required():
    assert validate_telephone("") is False
    assert validate_telephone(None) is False
    assert validate_telephone("   ") is False


@pytest.mark.parametrize("telephone", ["0771234567", "0112345678"])
def test_ten_digit_number_starting_with_zero_is_valid(telephone):
    assert validate_telephone(telephone) is True


@pytest.mark.parametrize(
    "telephone",
    [
        "123456789",     # 9 digits, one short
        "07712345678",   # 11 digits, one over
        "1771234567",    # doesn't start with 0
        "077-123-4567",  # punctuation, not stripped
        "+94771234567",  # country-code form not accepted
    ],
)
def test_malformed_telephone_is_invalid(telephone):
    assert validate_telephone(telephone) is False


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
