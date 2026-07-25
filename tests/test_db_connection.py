"""config.py, migrations/001_init.sql, connection.py."""

from app import config
from app.db import connection


def test_config_paths(isolated_data_dir):
    data_dir = config.get_data_dir()
    assert str(data_dir) == str(isolated_data_dir)
    assert data_dir.is_dir()
    assert config.get_db_path().parent == data_dir
    assert config.get_attachments_dir().is_dir()


def test_pragmas_and_schema(db_conn):
    conn = db_conn
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 3000

    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected_tables = {"summaries", "investigations", "doctors", "templates", "attachments", "app_meta"}
    assert expected_tables.issubset(tables)

    version_row = conn.execute("SELECT value FROM app_meta WHERE key = 'schema_version'").fetchone()
    assert version_row is not None and version_row["value"] == "1"

    indexes = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    expected_indexes = {"idx_summaries_bht", "idx_summaries_name", "idx_summaries_discharge"}
    assert expected_indexes.issubset(indexes)


def test_investigations_value_is_text_permissive(db_conn):
    conn = db_conn
    conn.execute(
        "INSERT INTO summaries (patient_name, bht_number, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("Test Patient", "12345", "2026-01-01T00:00:00", "2026-01-01T00:00:00"),
    )
    summary_id = conn.execute("SELECT id FROM summaries WHERE bht_number = '12345'").fetchone()["id"]
    conn.execute(
        "INSERT INTO investigations (summary_id, label, value, unit, sort_order) VALUES (?, ?, ?, ?, ?)",
        (summary_id, "SCr", "<0.5", "µmol/L", 1),
    )
    conn.commit()
    value = conn.execute("SELECT value FROM investigations WHERE summary_id = ?", (summary_id,)).fetchone()["value"]
    assert value == "<0.5"

    conn.execute("DELETE FROM summaries WHERE id = ?", (summary_id,))
    conn.commit()
    remaining = conn.execute(
        "SELECT COUNT(*) AS c FROM investigations WHERE summary_id = ?", (summary_id,)
    ).fetchone()["c"]
    assert remaining == 0, "ON DELETE CASCADE should remove investigations when their summary is deleted"


def test_reconnecting_does_not_reapply_migration(isolated_data_dir):
    conn = connection.connect()
    connection.close(conn)

    conn2 = connection.connect()
    assert conn2 is not None
    version_row2 = conn2.execute("SELECT value FROM app_meta WHERE key = 'schema_version'").fetchone()
    assert version_row2["value"] == "1"
    connection.close(conn2)
