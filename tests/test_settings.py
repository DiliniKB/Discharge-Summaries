"""Settings dialog + real backup-on-exit."""

import time

from app.db import app_meta, connection
from app.ui.dialogs.doctors import DoctorsDialog
from app.ui.dialogs.settings import BACKUP_PATH_KEY, SettingsDialog
from app.util import backup as backup_util


def test_backup_now_copies_the_db_file(tmp_path):
    fake_db = tmp_path / "fake.db"
    fake_db.write_text("not a real sqlite file, just testing the copy mechanics")
    backup_dir = tmp_path / "backup"

    assert backup_util.backup_now(str(fake_db) + "-missing", str(backup_dir)) is False

    ok = backup_util.backup_now(str(fake_db), str(backup_dir))
    assert ok is True
    stamp = time.strftime("%Y-%m-%d")
    expected_dest = backup_dir / f"data-{stamp}.db"
    assert expected_dest.exists()
    assert backup_dir.is_dir()
    assert expected_dest.read_text() == "not a real sqlite file, just testing the copy mechanics"


def test_settings_dialog_persists_backup_path_and_backs_up(db_conn, tmp_path, qapp):
    backup_dir = tmp_path / "backup"
    assert app_meta.get(db_conn, BACKUP_PATH_KEY) is None

    sd = SettingsDialog(db_conn)
    sd.show()
    qapp.processEvents()
    assert sd.path_input.text() == ""

    sd.path_input.setText(str(backup_dir))
    sd._on_done()
    assert app_meta.get(db_conn, BACKUP_PATH_KEY) == str(backup_dir)

    sd2 = SettingsDialog(db_conn)
    sd2.show()
    qapp.processEvents()
    assert sd2.path_input.text() == str(backup_dir), "re-opening the dialog shows the previously saved path"

    sd2.status_label.setText("")
    sd2._on_backup_now()
    qapp.processEvents()
    assert sd2.status_label.text() == "Backed up."

    sd3 = SettingsDialog(db_conn)
    sd3.path_input.setText("")
    sd3._on_backup_now()
    assert sd3.status_label.text() == "Set a backup path first.", "empty path shows a helpful message, doesn't crash"


def test_closing_the_app_with_a_configured_backup_path_creates_a_backup(isolated_data_dir, tmp_path, qapp, monkeypatch):
    monkeypatch.setattr(DoctorsDialog, "exec", lambda self: self.show())  # avoid blocking on an unrelated modal

    backup_dir = tmp_path / "backup"

    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    qapp.processEvents()
    app_meta.set(win._conn, BACKUP_PATH_KEY, str(backup_dir))
    win.close()  # triggers closeEvent -> checkpoint + backup_now

    stamp = time.strftime("%Y-%m-%d")
    assert (backup_dir / f"data-{stamp}.db").exists()
