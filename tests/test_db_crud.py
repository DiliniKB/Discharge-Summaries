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


def test_list_page(db_conn):
    conn = db_conn
    summaries.create(conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178", ward="45", age=54))

    # never SELECT * (CLAUDE.md hard rule).
    page = summaries.list_page(conn)
    assert len(page) == 1
    assert set(page[0].keys()) == {"id", "patient_name", "bht_number", "ward", "date_discharge"}


def test_advanced_search_patient_name_matches_name_or_bht(db_conn):
    conn = db_conn
    summaries.create(conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))

    by_name = summaries.advanced_search(conn, patient_name="wijerathna")
    assert len(by_name) == 1, "matches patient name substring, case-insensitive"
    by_bht = summaries.advanced_search(conn, patient_name="10178")
    assert len(by_bht) == 1, "matches BHT substring too"
    no_match = summaries.advanced_search(conn, patient_name="nonexistent")
    assert len(no_match) == 0

    cols = set(summaries.advanced_search(conn, patient_name="wijerathna")[0].keys())
    assert cols == {
        "id", "patient_name", "bht_number", "ward", "date_discharge",
        "created_at", "updated_at", "created_by", "last_edited_by",
    }


def test_advanced_search_keyword_matches_clinical_text_not_name_or_bht(db_conn):
    conn = db_conn
    summaries.create(conn, Summary(
        patient_name="Findable By Name Only", bht_number="99999", findings="a rare eosinophilic granuloma",
    ))

    by_keyword = summaries.advanced_search(conn, keyword="eosinophilic")
    assert len(by_keyword) == 1

    by_name_as_keyword = summaries.advanced_search(conn, keyword="Findable")
    assert len(by_name_as_keyword) == 0, "keyword does not match patient_name — that has its own field"
    by_bht_as_keyword = summaries.advanced_search(conn, keyword="99999")
    assert len(by_bht_as_keyword) == 0, "keyword does not match bht_number either"


def test_advanced_search_doctor_filter_matches_created_by_or_last_edited_by(db_conn):
    conn = db_conn
    doctors.seed_if_empty(conn)
    doc_a, doc_b = doctors.list_active(conn)[:2]

    created_by_a = summaries.create(conn, Summary(patient_name="Started by A", bht_number="1", created_by=doc_a.id))
    edited_by_a = summaries.create(conn, Summary(patient_name="Started by B, edited by A", bht_number="2", created_by=doc_b.id))
    summaries.update(conn, edited_by_a.id, last_edited_by=doc_a.id)
    only_b = summaries.create(conn, Summary(patient_name="Only B", bht_number="3", created_by=doc_b.id))

    results = summaries.advanced_search(conn, doctor_id=doc_a.id)
    result_ids = {r["id"] for r in results}
    assert result_ids == {created_by_a.id, edited_by_a.id}, "matches created_by OR last_edited_by, not just one"
    assert only_b.id not in result_ids


def test_advanced_search_created_and_modified_date_ranges(db_conn):
    conn = db_conn
    conn.execute(
        "INSERT INTO summaries (patient_name, bht_number, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("In range", "1", "2026-06-15T10:00:00", "2026-06-20T10:00:00"),
    )
    conn.execute(
        "INSERT INTO summaries (patient_name, bht_number, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("Out of range", "2", "2026-01-01T10:00:00", "2026-01-05T10:00:00"),
    )
    conn.commit()

    by_created = summaries.advanced_search(conn, created_from="2026-06-01", created_to="2026-06-30")
    assert [r["patient_name"] for r in by_created] == ["In range"]

    by_modified = summaries.advanced_search(conn, modified_from="2026-06-01", modified_to="2026-06-30")
    assert [r["patient_name"] for r in by_modified] == ["In range"]

    assert len(summaries.advanced_search(conn)) == 2, "no range given returns everyone"


def test_advanced_search_combines_all_filters(db_conn):
    conn = db_conn
    doctors.seed_if_empty(conn)
    doc = doctors.list_active(conn)[0]
    match = summaries.create(conn, Summary(
        patient_name="Combo Match", bht_number="5", created_by=doc.id, findings="unusual histology pattern",
    ))
    summaries.create(conn, Summary(patient_name="Combo Match", bht_number="6", findings="unusual histology pattern"))

    results = summaries.advanced_search(conn, patient_name="Combo", keyword="unusual", doctor_id=doc.id)
    assert [r["id"] for r in results] == [match.id]


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
