"""PatientList: real DB-backed browsing list + selection. Searching lives
entirely in the Advanced Search dialog now (docs/decisions.md) — see
tests/test_advanced_search_dialog.py."""

from app.db import summaries
from app.models import Summary
from app.ui.patient_list import PatientList

FIXTURES = [
    ("W.D. Kusuma Wijerathna", "10178", "45", "2026-01-22"),
    ("A.B. Perera", "10202", "45", "2026-01-21"),
    ("K.M. Silva", "10166", "45", "2026-01-19"),
    ("R.P.N. Gunawardena", "10190", "45", "2026-01-18"),
    ("S.K. Jayasuriya", "10151", "45", "2026-01-15"),
]


def _seed(conn):
    ids = {}
    for name, bht, ward, discharge in FIXTURES:
        s = summaries.create(conn, Summary(patient_name=name, bht_number=bht, ward=ward, date_discharge=discharge))
        ids[name] = s.id
    return ids


def test_renders_real_summaries_sorted_by_discharge_date_desc(db_conn):
    _seed(db_conn)
    pl = PatientList(db_conn)
    pl.show()

    assert len(pl._cards) == 5
    assert [c.patient["bht_number"] for c in pl._cards] == ["10178", "10202", "10166", "10190", "10151"]


def test_card_selection_is_exclusive(db_conn):
    _seed(db_conn)
    pl = PatientList(db_conn)
    pl.show()

    assert pl._selected_id is None
    target = pl._cards[1]
    pl._on_card_clicked(target)
    assert target.property("selected") is True
    assert sum(1 for c in pl._cards if c.property("selected")) == 1

    other = pl._cards[3]
    pl._on_card_clicked(other)
    assert target.property("selected") is False, "previous selection cleared"
    assert other.property("selected") is True
    assert isinstance(other.patient["id"], int), "card click carries a real summary_id, not a fixture dict"


def test_advanced_search_button_opens_the_dialog_instead_of_an_inline_search_box(db_conn):
    pl = PatientList(db_conn)
    pl.show()

    assert not hasattr(pl, "search_box"), "inline search was replaced entirely — no search box left"
    assert pl.advanced_search_button.text() == "Advanced Search"


def test_no_summaries_yet_empty_state(db_conn):
    pl = PatientList(db_conn)
    pl.show()

    assert len(pl._cards) == 0
    assert pl._no_results_label.isVisible() is True

    summaries.create(db_conn, Summary(patient_name="A.B. Perera", bht_number="10202"))
    pl.refresh()
    assert pl._no_results_label.isVisible() is False


def test_undischarged_card_pins_to_the_top(db_conn):
    _seed(db_conn)
    pl = PatientList(db_conn)
    pl.show()

    blank = summaries.create(db_conn, Summary(patient_name="", bht_number=""))
    pl.refresh()
    assert pl._cards[0].patient["id"] == blank.id, "a brand-new undischarged card sorts to the top — ui-spec.md §3.2"


def test_selection_survives_a_refresh(db_conn):
    ids = _seed(db_conn)
    pl = PatientList(db_conn)
    pl.show()

    pl.select(ids["K.M. Silva"])
    matching = [c for c in pl._cards if c.patient["id"] == ids["K.M. Silva"]][0]
    assert matching.property("selected") is True

    pl.refresh()
    still_matching = [c for c in pl._cards if c.patient["id"] == ids["K.M. Silva"]][0]
    assert still_matching.property("selected") is True, "list rebuild preserves the highlight"
