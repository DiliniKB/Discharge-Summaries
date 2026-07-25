"""doctors.py, templates.py, summaries.py."""

import time

import pytest

from app.db import doctors, summaries, templates
from app.models import Summary


def test_doctors_seed_add_deactivate(db_conn):
    conn = db_conn
    assert len(doctors.list_all(conn)) == 0
    doctors.seed_if_empty(conn)
    seeded = doctors.list_active(conn)
    assert len(seeded) == 4
    assert seeded[0].name == "Dr. S. Herath", "seeded doctors are consultant-first (sort_order 0 first)"

    doctors.seed_if_empty(conn)  # calling again must not duplicate
    assert len(doctors.list_active(conn)) == 4

    new_doc = doctors.add(conn, "Dr. Test Doctor", "Intern", sort_order=9)
    assert new_doc.id is not None
    assert any(d.id == new_doc.id for d in doctors.list_active(conn))

    doctors.deactivate(conn, new_doc.id)
    assert not any(d.id == new_doc.id for d in doctors.list_active(conn))
    assert any(d.id == new_doc.id for d in doctors.list_all(conn)), "deactivate, never delete"


def test_templates_seed_and_get(db_conn):
    conn = db_conn
    templates.seed_if_empty(conn)
    seeded_templates = templates.list_active(conn)
    assert len(seeded_templates) == 3
    assert any(t.name == "Thyroid lobectomy" for t in seeded_templates)
    fetched = templates.get(conn, seeded_templates[0].id)
    assert fetched.body == seeded_templates[0].body


def test_summaries_create_and_seed_investigations(db_conn):
    conn = db_conn
    assert len(summaries.list_page(conn)) == 0

    new_summary = Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178", ward="45", age=54)
    created = summaries.create(conn, new_summary)
    assert created.id is not None
    assert created.created_at != "" and created.updated_at != ""
    assert created.patient_name == "W.D. Kusuma Wijerathna"

    investigations = summaries.list_investigations(conn, created.id)
    assert len(investigations) == 7
    assert {i["label"] for i in investigations} == {"FBS", "SCr", "AST", "Na", "K", "S Ca", "Hb"}
    assert all(i["value"] == "" for i in investigations)


def test_list_page_and_search(db_conn):
    conn = db_conn
    created = summaries.create(
        conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178", ward="45", age=54)
    )

    # list_page / search — never SELECT * (CLAUDE.md hard rule).
    page = summaries.list_page(conn)
    assert len(page) == 1
    assert set(page[0].keys()) == {"id", "patient_name", "bht_number", "ward", "date_discharge"}

    results = summaries.search(conn, "wijerathna")
    assert len(results) == 1, "search matches by patient name substring, case-insensitive"
    results_bht = summaries.search(conn, "10178")
    assert len(results_bht) == 1, "search matches by BHT substring"
    no_results = summaries.search(conn, "nonexistent")
    assert len(no_results) == 0


def test_update_is_diff_shaped(db_conn):
    conn = db_conn
    created = summaries.create(conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))

    original_updated_at = created.updated_at
    time.sleep(1.1)  # ISO timestamp has second resolution — ensure updated_at actually changes
    summaries.update(conn, created.id, telephone="0771234567")
    reloaded = summaries.get(conn, created.id)
    assert reloaded.telephone == "0771234567"
    assert reloaded.patient_name == "W.D. Kusuma Wijerathna", "update() leaves other fields untouched"
    assert reloaded.updated_at != original_updated_at

    with pytest.raises(ValueError):
        summaries.update(conn, created.id, not_a_real_column="x")


def test_upsert_investigation_updates_existing_and_inserts_adhoc(db_conn):
    conn = db_conn
    created = summaries.create(conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))

    inv = summaries.list_investigations(conn, created.id)
    fbs_row = next(i for i in inv if i["label"] == "FBS")
    summaries.upsert_investigation(conn, fbs_row["id"], created.id, "FBS", "86", "mg/dL", 0)
    inv_after = summaries.list_investigations(conn, created.id)
    fbs_after = next(i for i in inv_after if i["label"] == "FBS")
    assert fbs_after["value"] == "86" and len(inv_after) == 7, "updates existing row (by id) rather than duplicating"

    summaries.upsert_investigation(conn, None, created.id, "CRP", "12", "mg/L", 7)
    inv_with_adhoc = summaries.list_investigations(conn, created.id)
    assert len(inv_with_adhoc) == 8, "no id inserts a new ad-hoc row"


def test_soft_delete(db_conn):
    conn = db_conn
    created = summaries.create(conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))

    summaries.soft_delete(conn, created.id)
    assert len(summaries.list_page(conn)) == 0
    still_there = conn.execute("SELECT COUNT(*) AS c FROM summaries WHERE id = ?", (created.id,)).fetchone()["c"]
    assert still_there == 1, "soft-deleted row still physically exists (not a hard delete)"
