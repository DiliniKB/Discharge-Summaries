"""Smoke test for the fixture setup itself — not a real feature test."""

from app.db import doctors as doctors_db, summaries
from app.models import Summary


def test_db_conn_fixture_gives_a_working_migrated_connection(db_conn):
    doctors_db.seed_if_empty(db_conn)
    assert len(doctors_db.list_active(db_conn)) == 4


def test_isolated_data_dir_actually_isolates_between_tests(db_conn):
    # If a previous test's data leaked in, this would already have summaries.
    assert summaries.list_page(db_conn) == []
    summaries.create(db_conn, Summary(patient_name="Test", bht_number="1"))
    assert len(summaries.list_page(db_conn)) == 1


def test_main_window_opens_its_own_connection_to_the_same_isolated_dir(isolated_data_dir):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    assert win.patient_list is not None
    win.close()
