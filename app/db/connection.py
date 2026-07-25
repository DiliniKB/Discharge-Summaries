"""Single SQLite connection, opened at startup, closed at exit. Never
per-operation. Applies the PRAGMAs and forward-only migrations.
See docs/schema.md, docs/decisions.md.
"""

import sqlite3
from pathlib import Path

from app import config

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(db_path=None):
    if db_path is None:
        db_path = config.get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 3000")
    _apply_migrations(conn)
    return conn


def close(conn):
    conn.close()


def _current_schema_version(conn):
    try:
        row = conn.execute("SELECT value FROM app_meta WHERE key = 'schema_version'").fetchone()
    except sqlite3.OperationalError:
        return 0  # app_meta doesn't exist yet — no migrations applied
    return int(row["value"]) if row else 0


def _available_migrations():
    numbered = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        prefix = path.stem.split("_", 1)[0]
        numbered.append((int(prefix), path))
    return sorted(numbered, key=lambda pair: pair[0])


def _apply_migrations(conn):
    current = _current_schema_version(conn)
    for version, path in _available_migrations():
        if version <= current:
            continue
        conn.executescript(path.read_text())
        conn.execute(
            "INSERT INTO app_meta (key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(version),),
        )
        conn.commit()
