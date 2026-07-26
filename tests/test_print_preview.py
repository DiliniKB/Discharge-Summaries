"""Print Preview dialog + Editor._on_print() wiring."""

from PySide6.QtWidgets import QFileDialog

from app.db import doctors as doctors_db
from app.db import summaries
from app.models import Summary
from app.ui.dialogs.print_preview import PrintPreviewDialog


def test_print_preview_dialog_renders_a_real_pdf(db_conn, tmp_path, qapp):
    doctors_db.seed_if_empty(db_conn)
    doctor = doctors_db.list_active(db_conn)[0]

    created = summaries.create(
        db_conn,
        Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178", ward="45", created_by=doctor.id, procedure_title="thyroidectomy"),
    )

    dialog = PrintPreviewDialog(db_conn, created.id, tmp_path, doctor.id)
    dialog.show()
    qapp.processEvents()

    assert dialog.pdf_path.exists()
    pdf_bytes = dialog.pdf_path.read_bytes()
    assert b"Wijerathna" in pdf_bytes
    assert doctor.name.encode() in pdf_bytes
    assert dialog._document.pageCount() > 0

    # Clicking Print on a non-Windows dev machine should show a clear status
    # message, not crash — os.startfile doesn't exist here.
    dialog._on_print()
    qapp.processEvents()
    assert "printer" in dialog.status_label.text().lower()

    dialog.close()


def test_save_button_copies_the_pdf_and_stays_open(db_conn, tmp_path, qapp, monkeypatch):
    doctors_db.seed_if_empty(db_conn)
    doctor = doctors_db.list_active(db_conn)[0]
    created = summaries.create(
        db_conn,
        Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178", ward="45", created_by=doctor.id),
    )

    dialog = PrintPreviewDialog(db_conn, created.id, tmp_path, doctor.id)
    dialog.show()
    qapp.processEvents()

    save_dest = tmp_path / "saved" / "discharge.pdf"
    save_dest.parent.mkdir()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(save_dest), "")))

    dialog._on_save()

    assert save_dest.exists()
    assert save_dest.read_bytes() == dialog.pdf_path.read_bytes()
    assert dialog.status_label.text() == "Saved."
    assert dialog.isVisible() is True, "Save doesn't close the dialog, unlike Print"
    assert dialog.result() == 0, "Save doesn't accept()/reject() either"

    dialog.close()


def test_save_button_cancelled_does_nothing(db_conn, tmp_path, qapp, monkeypatch):
    doctors_db.seed_if_empty(db_conn)
    doctor = doctors_db.list_active(db_conn)[0]
    created = summaries.create(
        db_conn,
        Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178", ward="45", created_by=doctor.id),
    )

    dialog = PrintPreviewDialog(db_conn, created.id, tmp_path, doctor.id)
    dialog.show()
    qapp.processEvents()

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    dialog._on_save()

    assert dialog.status_label.text() == ""
    dialog.close()


def test_editor_print_button_opens_a_real_preview_with_current_data(db_conn, tmp_path, qapp, monkeypatch):
    doctors_db.seed_if_empty(db_conn)
    creator, current = doctors_db.list_active(db_conn)[:2]
    created = summaries.create(
        db_conn,
        Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178", ward="45", created_by=creator.id, procedure_title="thyroidectomy"),
    )

    from app.ui.editor import Editor
    from app.ui.editor_controller import EditorController

    # Avoid blocking on the real modal .exec() — same technique as test_dialogs.py.
    # Read the PDF bytes WHILE mocked-exec runs, not after: Editor._on_print()
    # uses `with tempfile.TemporaryDirectory()`, which — since our mocked
    # exec() returns immediately instead of actually blocking like the real
    # one — exits and deletes the temp dir right after exec() returns. The
    # test just has to capture content before that happens.
    captured_pdf_bytes = {}

    def _fake_exec(self):
        captured_pdf_bytes["bytes"] = self.pdf_path.read_bytes()
        self.show()

    monkeypatch.setattr(PrintPreviewDialog, "exec", _fake_exec)

    controller = EditorController(db_conn)
    # A DIFFERENT doctor than the record's creator is currently selected —
    # the printed signature must follow this one, not created_by (docs/decisions.md).
    controller.current_doctor_id = current.id
    editor = Editor(controller)
    editor.show()
    qapp.processEvents()

    assert editor.print_button.isEnabled() is False
    editor._on_print()  # must be a safe no-op with nothing open

    controller.load(created.id)
    editor.load_summary(created.id)
    qapp.processEvents()
    assert editor.print_button.isEnabled() is True

    editor._on_print()
    qapp.processEvents()
    opened_previews = [w for w in qapp.topLevelWidgets() if isinstance(w, PrintPreviewDialog)]
    assert len(opened_previews) >= 1
    assert b"Wijerathna" in captured_pdf_bytes.get("bytes", b"")
    assert current.name.encode() in captured_pdf_bytes["bytes"]
    assert creator.name.encode() not in captured_pdf_bytes["bytes"]
    for w in opened_previews:
        w.close()

    editor.close()
