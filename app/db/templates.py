"""CRUD for the templates table. Templates insert, they don't link —
docs/decisions.md: selecting one copies its text into procedure_steps;
editing a template later must never alter an existing summary.
"""

from app.models import Template

# Seeded on first launch. Not yet wired to the UI fixtures in
# app/ui/sections/procedure.py — that's a later chunk.
SEED_TEMPLATES = [
    (
        "Thyroid lobectomy",
        "1. GA induced, patient supine, neck extended.\n"
        "2. Collar incision, subplatysmal flaps raised.\n"
        "3. Strap muscles separated in the midline.\n"
        "4. Affected lobe mobilised, isthmus divided.\n"
        "5. Haemostasis secured, wound closed in layers.",
        0,
    ),
    (
        "Complete thyroidectomy",
        "1. GA induced, patient supine, neck extended.\n"
        "2. Collar incision, subplatysmal flaps raised.\n"
        "3. Both lobes mobilised and delivered.\n"
        "4. Parathyroids identified and preserved.\n"
        "5. Haemostasis secured, wound closed in layers.",
        1,
    ),
    (
        "Total mastectomy",
        "1. GA induced, patient supine, arm abducted.\n"
        "2. Elliptical incision around the breast.\n"
        "3. Skin flaps raised, breast tissue excised off pectoralis fascia.\n"
        "4. Haemostasis secured, drain placed.\n"
        "5. Wound closed in layers.",
        2,
    ),
]


def _row_to_template(row):
    return Template(
        id=row["id"],
        name=row["name"],
        body=row["body"],
        sort_order=row["sort_order"] or 0,
        active=bool(row["active"]),
    )


def seed_if_empty(conn):
    count = conn.execute("SELECT COUNT(*) AS c FROM templates").fetchone()["c"]
    if count > 0:
        return
    for name, body, sort_order in SEED_TEMPLATES:
        conn.execute(
            "INSERT INTO templates (name, body, active, sort_order) VALUES (?, ?, 1, ?)",
            (name, body, sort_order),
        )
    conn.commit()


def list_active(conn):
    rows = conn.execute("SELECT * FROM templates WHERE active = 1 ORDER BY sort_order").fetchall()
    return [_row_to_template(r) for r in rows]


def get(conn, template_id):
    row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    return _row_to_template(row) if row else None
