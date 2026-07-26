"""CRUD for the attachments table."""

from app.db import attachments, summaries
from app.models import Summary


def _seed_summary(conn):
    return summaries.create(conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))


def test_add_get_list_round_trip(db_conn):
    conn = db_conn
    created = _seed_summary(conn)

    row = attachments.add(conn, created.id, "report.pdf", f"{created.id}/abc123.pdf", 2048)
    assert row.id is not None
    assert row.filename == "report.pdf"
    assert row.stored_path == f"{created.id}/abc123.pdf"
    assert row.size_bytes == 2048
    assert row.added_at != ""

    fetched = attachments.get(conn, row.id)
    assert fetched == row

    listed = attachments.list_for_summary(conn, created.id)
    assert len(listed) == 1
    assert listed[0].id == row.id


def test_list_for_summary_ordered_and_scoped(db_conn):
    conn = db_conn
    first = _seed_summary(conn)
    second = summaries.create(conn, Summary(patient_name="A.B. Perera", bht_number="10202"))

    attachments.add(conn, first.id, "a.jpg", f"{first.id}/a.jpg", 100)
    attachments.add(conn, first.id, "b.jpg", f"{first.id}/b.jpg", 200)
    attachments.add(conn, second.id, "c.jpg", f"{second.id}/c.jpg", 300)

    first_rows = attachments.list_for_summary(conn, first.id)
    assert [r.filename for r in first_rows] == ["a.jpg", "b.jpg"]
    second_rows = attachments.list_for_summary(conn, second.id)
    assert [r.filename for r in second_rows] == ["c.jpg"]


def test_delete_removes_the_row(db_conn):
    conn = db_conn
    created = _seed_summary(conn)
    row = attachments.add(conn, created.id, "x.jpg", f"{created.id}/x.jpg", 100)

    attachments.delete(conn, row.id)
    assert attachments.get(conn, row.id) is None
    assert attachments.list_for_summary(conn, created.id) == []


def test_on_delete_cascade_removes_attachments_when_summary_deleted(db_conn):
    conn = db_conn
    created = _seed_summary(conn)
    row = attachments.add(conn, created.id, "x.jpg", f"{created.id}/x.jpg", 100)

    conn.execute("DELETE FROM summaries WHERE id = ?", (created.id,))
    conn.commit()

    assert attachments.get(conn, row.id) is None
