"""DateField widget in isolation — format-as-you-type, calendar picker,
today-default, ISO round-trip."""

from PySide6.QtCore import QDate

from app.ui.widgets.datefield import DateField


def test_starts_empty():
    df = DateField()
    assert df.get_iso() == ""


def test_set_iso_and_round_trip():
    df = DateField()
    df.set_iso("2026-01-22")
    assert df.line.text() == "22/01/2026"
    assert df.get_iso() == "2026-01-22"


def test_get_iso_reads_a_fully_typed_date():
    df = DateField()
    df.line.setText("05/03/2026")
    assert df.get_iso() == "2026-03-05"


def test_get_iso_returns_empty_for_an_incomplete_date():
    df = DateField()
    df.line.setText("22/01")
    assert df.get_iso() == ""


def test_set_iso_empty_clears_the_field():
    df = DateField()
    df.set_iso("2026-01-22")
    df.set_iso("")
    assert df.get_iso() == ""


def test_set_today():
    df = DateField()
    df.set_today()
    assert df.get_iso() == QDate.currentDate().toString("yyyy-MM-dd")


def test_calendar_picker_sets_the_field_and_hides_the_popup():
    df = DateField()
    picked = QDate(2026, 3, 15)
    df._on_calendar_date_picked(picked)
    assert df.get_iso() == "2026-03-15"
    assert df._calendar.isVisible() is False
