"""CRUD for the summaries table (+ its investigations rows). See
docs/schema.md.

update() takes **fields and writes only the columns passed — shaped
deliberately for app/ui/editor_controller.py (not built yet): the
controller diffs before calling this, so an untouched field never
triggers a write. Never call update() with a full record; that defeats
the whole point of diffing first.

CLAUDE.md hard rule: never SELECT * the summaries table into memory. The
list pane uses list_page(); Advanced Search uses advanced_search(). Both
only ever select the columns their respective views actually display.
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


_ORDER_UNDISCHARGED_FIRST = (
    "ORDER BY (date_discharge IS NULL OR date_discharge = '') DESC, date_discharge DESC, id DESC"
)
# Plain "ORDER BY date_discharge DESC" would sort a blank date_discharge
# (a brand new, not-yet-discharged card) to the BOTTOM — empty string is
# the smallest possible value, so DESC puts it last. docs/ui-spec.md is
# explicit: "Unsaved new cards pin to the top." This ordering puts every
# undischarged summary first (newest such row first via id DESC), then
# discharged ones newest-first — not just newly-created ones.


def list_page(conn, limit=50, offset=0):
    """List pane, never loads full records — docs/schema.md 'Query patterns'."""
    rows = conn.execute(
        f"SELECT id, patient_name, bht_number, ward, date_discharge "
        f"FROM summaries WHERE deleted_at IS NULL "
        f"{_ORDER_UNDISCHARGED_FIRST} LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


# Broad clinical-text columns for the Advanced Search keyword filter — NOT
# patient_name/bht_number, which have their own dedicated "Patient Name /
# BHT" filter field in that dialog (docs/decisions.md).
_KEYWORD_COLUMNS = [
    "procedure_title",
    "indication",
    "procedure_steps",
    "presenting_complaint",
    "past_medical_history",
    "past_surgical_history",
    "allergies",
    "examination",
    "findings",
    "management",
    "histology_report",
]


def advanced_search(
    conn,
    patient_name="",
    keyword="",
    doctor_id=None,
    created_from=None,
    created_to=None,
    modified_from=None,
    modified_to=None,
    limit=200,
):
    """Backs the Advanced Search dialog — a deliberate, explicit action
    (button click), not the hot per-keystroke list-pane path, so an
    unindexed date(...) scan on created_at/updated_at is an accepted
    tradeoff here (docs/decisions.md). Still respects CLAUDE.md's "never
    SELECT * the summaries table into memory" — only the columns the
    results table displays are selected; the full record loads only when
    a row is actually viewed/edited, via get()."""
    where = ["deleted_at IS NULL"]
    params = []

    if patient_name:
        # Matches BHT too — the old quick search covered both, and BHT is
        # the ward's primary identifier; folding it into one field keeps
        # that lookup working without adding a field the user didn't ask
        # for (docs/decisions.md).
        like = f"%{patient_name}%"
        where.append("(patient_name LIKE ? OR bht_number LIKE ?)")
        params += [like, like]

    if keyword:
        like = f"%{keyword}%"
        keyword_clause = " OR ".join(f"{col} LIKE ?" for col in _KEYWORD_COLUMNS)
        where.append(f"({keyword_clause})")
        params.extend([like] * len(_KEYWORD_COLUMNS))

    if doctor_id is not None:
        where.append("(created_by = ? OR last_edited_by = ?)")
        params += [doctor_id, doctor_id]

    if created_from or created_to:
        where.append("date(created_at) BETWEEN ? AND ?")
        params += [created_from or "0000-01-01", created_to or "9999-12-31"]

    if modified_from or modified_to:
        where.append("date(updated_at) BETWEEN ? AND ?")
        params += [modified_from or "0000-01-01", modified_to or "9999-12-31"]

    where_sql = " AND ".join(where)
    rows = conn.execute(
        f"SELECT id, patient_name, bht_number, ward, date_discharge, "
        f"created_at, updated_at, created_by, last_edited_by "
        f"FROM summaries WHERE {where_sql} "
        f"{_ORDER_UNDISCHARGED_FIRST} LIMIT ?",
        (*params, limit),
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


def list_deleted(conn, limit=200):
    """Backs the Recently Deleted dialog. No purge job exists yet
    (docs/decisions.md), so this shows every soft-deleted row, not just
    the last 30 days — that matches actual current behavior rather than
    pretending a purge runs. Still not SELECT * (CLAUDE.md hard rule)."""
    rows = conn.execute(
        "SELECT id, patient_name, bht_number, ward, deleted_at FROM summaries "
        "WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def restore(conn, summary_id):
    conn.execute("UPDATE summaries SET deleted_at = NULL WHERE id = ?", (summary_id,))
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
    """Returns the row's id — callers with investigation_id=None (a brand
    new ad-hoc row) need the real id back, or a second edit to the same
    label would insert a duplicate instead of updating in place."""
    if investigation_id:
        conn.execute(
            "UPDATE investigations SET label = ?, value = ?, unit = ?, sort_order = ? WHERE id = ?",
            (label, value, unit, sort_order, investigation_id),
        )
        conn.commit()
        return investigation_id
    else:
        cur = conn.execute(
            "INSERT INTO investigations (summary_id, label, value, unit, sort_order) VALUES (?, ?, ?, ?, ?)",
            (summary_id, label, value, unit, sort_order),
        )
        conn.commit()
        return cur.lastrowid
