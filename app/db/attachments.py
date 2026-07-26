"""CRUD for the attachments table. Files on disk, paths in the DB, never
blobs — docs/decisions.md. File removal (the actual disk delete) lives in
app/util/attachments.py, not here — this module only ever touches SQLite,
so DB and disk cleanup stay separately testable.
"""

from datetime import datetime, timezone

from app.models import Attachment


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_attachment(row):
    return Attachment(
        id=row["id"],
        summary_id=row["summary_id"],
        filename=row["filename"],
        stored_path=row["stored_path"],
        size_bytes=row["size_bytes"],
        added_at=row["added_at"],
    )


def add(conn, summary_id, filename, stored_path, size_bytes):
    cur = conn.execute(
        "INSERT INTO attachments (summary_id, filename, stored_path, size_bytes, added_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (summary_id, filename, stored_path, size_bytes, _now_iso()),
    )
    conn.commit()
    return get(conn, cur.lastrowid)


def get(conn, attachment_id):
    row = conn.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
    return _row_to_attachment(row) if row else None


def list_for_summary(conn, summary_id):
    rows = conn.execute(
        "SELECT * FROM attachments WHERE summary_id = ? ORDER BY added_at", (summary_id,)
    ).fetchall()
    return [_row_to_attachment(r) for r in rows]


def delete(conn, attachment_id):
    conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
    conn.commit()
