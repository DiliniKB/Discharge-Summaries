"""Attachments section: collapsed by default, real file handling through
EditorController — file picker, drag-drop, remove, 5MB cap."""

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QFileDialog

from app.db import summaries
from app.models import Summary
from app.ui.editor_controller import EditorController
from app.ui.sections.attachments import AttachmentsSection


def _make_summary(conn):
    return summaries.create(conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))


def test_starts_collapsed_with_zero_files():
    sec = AttachmentsSection()
    sec.show()

    assert sec._title.text() == "ATTACHMENTS"
    assert sec.expanded is False
    assert sec.body.isVisible() is False
    assert sec._counter.text() == "0 files"
    assert sec.add_file_button.text() == "+ Add File"
    assert sec.add_file_button.isEnabled() is False, "disabled until a summary is open"


def test_clicking_the_header_expands_it():
    sec = AttachmentsSection()
    sec.show()
    sec._toggle()
    assert sec.expanded is True
    assert sec.body.isVisible() is True


def test_set_enabled_toggles_add_file_and_drag_drop():
    sec = AttachmentsSection()
    sec.show()
    assert sec.acceptDrops() is False

    sec.set_enabled(True)
    assert sec.add_file_button.isEnabled() is True
    assert sec.acceptDrops() is True

    sec.set_enabled(False)
    assert sec.add_file_button.isEnabled() is False
    assert sec.acceptDrops() is False


def test_populate_rebuilds_rows_from_real_db_data(db_conn, tmp_path):
    summary = _make_summary(db_conn)
    controller = EditorController(db_conn)
    controller.load(summary.id)

    source = tmp_path / "report.pdf"
    source.write_bytes(b"a real small file")
    controller.add_attachment(str(source))

    sec = AttachmentsSection()
    sec.bind_controller(controller)
    sec.populate()

    assert len(sec.rows) == 1
    assert sec.rows[0].attachment.filename == "report.pdf"
    assert sec._counter.text() == "1 file"


def test_add_file_button_imports_the_selected_files(db_conn, tmp_path, monkeypatch):
    summary = _make_summary(db_conn)
    controller = EditorController(db_conn)
    controller.load(summary.id)

    source = tmp_path / "scan.jpg"
    source.write_bytes(b"fake image bytes, not a real image, copies through unchanged")

    monkeypatch.setattr(QFileDialog, "exec", lambda self: True)
    monkeypatch.setattr(QFileDialog, "selectedFiles", lambda self: [str(source)])

    sec = AttachmentsSection()
    sec.bind_controller(controller)
    sec.set_enabled(True)
    sec._on_add_file_clicked()

    assert len(sec.rows) == 1
    assert sec.rows[0].attachment.filename == "scan.jpg"
    assert len(controller.list_attachments()) == 1, "persisted to the real DB, not just the widget list"


def test_remove_button_deletes_from_db_and_disk(db_conn, tmp_path):
    summary = _make_summary(db_conn)
    controller = EditorController(db_conn)
    controller.load(summary.id)

    source = tmp_path / "report.pdf"
    source.write_bytes(b"a real small file")
    controller.add_attachment(str(source))

    sec = AttachmentsSection()
    sec.bind_controller(controller)
    sec.populate()
    assert len(sec.rows) == 1

    row = sec.rows[0]
    stored_path = row.attachment.stored_path
    from app import config

    dest = config.get_attachments_dir() / stored_path
    assert dest.exists()

    sec._on_remove_row(row)

    assert len(sec.rows) == 0
    assert sec._counter.text() == "0 files"
    assert controller.list_attachments() == []
    assert not dest.exists(), "file removed from disk, not just the DB row"


def test_oversized_file_shows_inline_error_not_a_crash(db_conn, tmp_path, monkeypatch):
    summary = _make_summary(db_conn)
    controller = EditorController(db_conn)
    controller.load(summary.id)
    monkeypatch.setattr("app.util.attachments.MAX_ATTACHMENT_BYTES", 10)

    source = tmp_path / "huge.pdf"
    source.write_bytes(b"x" * 1000)

    sec = AttachmentsSection()
    sec.show()
    sec._toggle()  # expand — a hidden (collapsed) body means every descendant reports isVisible() False too
    sec.bind_controller(controller)
    sec._import_paths([str(source)])

    assert len(sec.rows) == 0
    assert sec._error_label.isVisible() is True
    assert "huge.pdf" in sec._error_label.text()


def test_drop_event_imports_files(db_conn, tmp_path):
    summary = _make_summary(db_conn)
    controller = EditorController(db_conn)
    controller.load(summary.id)

    source = tmp_path / "dropped.pdf"
    source.write_bytes(b"dropped file content")

    sec = AttachmentsSection()
    sec.bind_controller(controller)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(source))])
    event = QDropEvent(QPointF(sec.rect().center()), Qt.CopyAction, mime, Qt.NoButton, Qt.NoModifier)
    sec.dropEvent(event)

    assert len(controller.list_attachments()) == 1
    assert controller.list_attachments()[0].filename == "dropped.pdf"


def test_wired_into_the_real_editor_collapsed(isolated_data_dir):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    assert win.editor.attachments_section is not None
    assert win.editor.attachments_section.expanded is False
    win.close()
