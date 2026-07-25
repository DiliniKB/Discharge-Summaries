"""CRUD for the doctors table. Deactivate, never delete — docs/decisions.md:
MOs rotate through the unit; deleting one would orphan the FK on every
summary they signed, so old cards would print without a signing officer.
"""

from app.models import Doctor

# Seeded on first launch (docs/deployment.md). Fictional. Not yet wired to
# the UI fixtures in app/ui/main_window.py — that's a later chunk.
SEED_DOCTORS = [
    ("Dr. S. Herath", "SR Onco-surgery", 0),
    ("Dr. N. Ratnayake", "Consultant Surgeon", 1),
    ("Dr. P. Wickramasinghe", "Registrar", 2),
    ("Dr. A. Fonseka", "SHO", 3),
]


def _row_to_doctor(row):
    return Doctor(
        id=row["id"],
        name=row["name"],
        designation=row["designation"] or "",
        active=bool(row["active"]),
        sort_order=row["sort_order"],
    )


def seed_if_empty(conn):
    count = conn.execute("SELECT COUNT(*) AS c FROM doctors").fetchone()["c"]
    if count > 0:
        return
    for name, designation, sort_order in SEED_DOCTORS:
        conn.execute(
            "INSERT INTO doctors (name, designation, active, sort_order) VALUES (?, ?, 1, ?)",
            (name, designation, sort_order),
        )
    conn.commit()


def list_active(conn):
    """Consultant first, not alphabetical — docs/schema.md."""
    rows = conn.execute("SELECT * FROM doctors WHERE active = 1 ORDER BY sort_order").fetchall()
    return [_row_to_doctor(r) for r in rows]


def list_all(conn):
    rows = conn.execute("SELECT * FROM doctors ORDER BY sort_order").fetchall()
    return [_row_to_doctor(r) for r in rows]


def get(conn, doctor_id):
    row = conn.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    return _row_to_doctor(row) if row else None


def add(conn, name, designation, sort_order=0):
    cur = conn.execute(
        "INSERT INTO doctors (name, designation, active, sort_order) VALUES (?, ?, 1, ?)",
        (name, designation, sort_order),
    )
    conn.commit()
    return get(conn, cur.lastrowid)


def deactivate(conn, doctor_id):
    conn.execute("UPDATE doctors SET active = 0 WHERE id = ?", (doctor_id,))
    conn.commit()


def reactivate(conn, doctor_id):
    """Staff rotate back through the unit — deactivation isn't meant to be
    permanent, just "not currently on the ward.\""""
    conn.execute("UPDATE doctors SET active = 1 WHERE id = ?", (doctor_id,))
    conn.commit()
