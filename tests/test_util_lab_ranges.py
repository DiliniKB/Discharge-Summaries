"""General adult reference ranges — flags outside-range values, never
crashes on non-numeric lab text."""

import pytest

from app.util.lab_ranges import NORMAL_RANGES, is_abnormal


@pytest.mark.parametrize("label", list(NORMAL_RANGES.keys()))
def test_value_inside_range_is_not_abnormal(label):
    low, high = NORMAL_RANGES[label]
    midpoint = (low + high) / 2
    assert is_abnormal(label, str(midpoint)) is False


@pytest.mark.parametrize("label", list(NORMAL_RANGES.keys()))
def test_value_outside_range_is_abnormal(label):
    low, high = NORMAL_RANGES[label]
    assert is_abnormal(label, str(low - 1)) is True
    assert is_abnormal(label, str(high + 1)) is True


@pytest.mark.parametrize("label", list(NORMAL_RANGES.keys()))
def test_boundary_values_are_inside_range(label):
    low, high = NORMAL_RANGES[label]
    assert is_abnormal(label, str(low)) is False
    assert is_abnormal(label, str(high)) is False


def test_non_numeric_lab_text_never_flagged():
    assert is_abnormal("SCr", "<0.5") is False
    assert is_abnormal("Hb", "Not done") is False


def test_blank_value_never_flagged():
    assert is_abnormal("FBS", "") is False


def test_unknown_label_never_flagged():
    assert is_abnormal("CRP", "500") is False
