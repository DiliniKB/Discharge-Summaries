"""Shared fixtures. Database and printing tests use fictional patient
data only — see README.md "Tests".

qapp is provided by pytest-qt (session-scoped QApplication) — every test
that touches a widget needs it, directly or transitively.
"""

import os
import shutil

import pytest

from app import theme


@pytest.fixture(scope="session", autouse=True)
def _apply_theme_once(qapp):
    """Applied once per test session so no individual test has to
    remember to call it — widget sizes/styles depend on it."""
    theme.apply_theme(qapp)


@pytest.fixture
def isolated_data_dir(tmp_path):
    """Points DS_DATA_DIR at a fresh temp directory for the duration of
    one test — config.get_data_dir()/get_db_path() respect this override
    (see app/config.py), so MainWindow (which opens its own connection
    internally) and direct connection.connect() calls both land here,
    never touching a real dev/user database."""
    data_dir = tmp_path / "data"
    os.environ["DS_DATA_DIR"] = str(data_dir)
    yield data_dir
    del os.environ["DS_DATA_DIR"]
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def db_conn(isolated_data_dir):
    """A real, isolated SQLite connection — migrated fresh, closed and
    discarded after the test."""
    from app.db import connection

    conn = connection.connect()
    yield conn
    connection.close(conn)
