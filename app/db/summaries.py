"""CRUD for the summaries table (+ its investigations rows). See
docs/schema.md.

update() takes **fields and writes only the columns passed — shaped
deliberately for app/ui/editor_controller.py (not built yet): the
controller diffs before calling this, so an untouched field never
triggers a write. Never call update() with a full record; that defeats
the whole point of diffing first.

CLAUDE.md hard rule: never SELECT * the summaries table into memory. The
list pane uses list_page()/search(), which only ever select the five
columns the list actually displays.
"""

import dataclasses
from datetime import datetime, timezone

from app.models import Summary

_SUMMARY_COLUMNS = [f.name for f in dataclasses.fields(Summary) if f.name != "id"]

STANDARD_ANALYTES = [
    ("FBS", "mg/dL", 0),
    ("SCr", "µmol/L", 1),
    ("AST", "U/L", 2),
    ("Na", "mmol/L", 3),
    ("K", "mmol/L", 4),
    ("S Ca", "mmol/L", 5),
    ("Hb", "g/dL", 6),
]


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_summary(row):
    return Summary(id=row["id"], **{col: row[col] for col in _SUMMARY_COLUMNS})


def list_page(conn, limit=50, offset=0):
    """List pane, never loads full records — docs/schema.md 'Query patterns'."""
    rows = conn.execute(
        "SELECT id, patient_name, bht_number, ward, date_discharge "
        "FROM summaries WHERE deleted_at IS NULL "
        "ORDER BY date_discharge DESC, id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def search(conn, query, limit=50):
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT id, patient_name, bht_number, ward, date_discharge "
        "FROM summaries WHERE deleted_at IS NULL "
        "AND (patient_name LIKE ? OR bht_number LIKE ?) "
        "ORDER BY date_discharge DESC LIMIT ?",
        (like, like, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get(conn, summary_id):
    """Full record — only on selection, one summary at a time."""
    row = conn.execute("SELECT * FROM summaries WHERE id = ?", (summary_id,)).fetchone()
    return _row_to_summary(row) if row else None


def create(conn, summary):
    now = _now_iso()
    columns = [c for c in _SUMMARY_COLUMNS if c not in ("created_at", "updated_at")]
    values = [getattr(summary, c) for c in columns]
    placeholders = ", ".join("?" for _ in columns)
    cur = conn.execute(
        f"INSERT INTO summaries ({', '.join(columns)}, created_at, updated_at) "
        f"VALUES ({placeholders}, ?, ?)",
        (*values, now, now),
    )
    conn.commit()
    new_id = cur.lastrowid
    create_default_investigations(conn, new_id)
    return get(conn, new_id)


def update(conn, summary_id, **fields):
    if not fields:
        return
    unknown = set(fields) - set(_SUMMARY_COLUMNS)
    if unknown:
        raise ValueError(f"Unknown summary column(s): {unknown}")
    fields = dict(fields)
    fields["updated_at"] = _now_iso()
    set_clause = ", ".join(f"{col} = ?" for col in fields)
    conn.execute(f"UPDATE summaries SET {set_clause} WHERE id = ?", (*fields.values(), summary_id))
    conn.commit()


def soft_delete(conn, summary_id):
    conn.execute("UPDATE summaries SET deleted_at = ? WHERE id = ?", (_now_iso(), summary_id))
    conn.commit()


def create_default_investigations(conn, summary_id):
    """Seven standard rows on every new summary — docs/decisions.md."""
    for label, unit, sort_order in STANDARD_ANALYTES:
        conn.execute(
            "INSERT INTO investigations (summary_id, label, value, unit, sort_order) VALUES (?, ?, '', ?, ?)",
            (summary_id, label, unit, sort_order),
        )
    conn.commit()


def list_investigations(conn, summary_id):
    rows = conn.execute(
        "SELECT * FROM investigations WHERE summary_id = ? ORDER BY sort_order", (summary_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_investigation(conn, investigation_id, summary_id, label, value, unit, sort_order):
    if investigation_id:
        conn.execute(
            "UPDATE investigations SET label = ?, value = ?, unit = ?, sort_order = ? WHERE id = ?",
            (label, value, unit, sort_order, investigation_id),
        )
    else:
        conn.execute(
            "INSERT INTO investigations (summary_id, label, value, unit, sort_order) VALUES (?, ?, ?, ?, ?)",
            (summary_id, label, value, unit, sort_order),
        )
    conn.commit()
