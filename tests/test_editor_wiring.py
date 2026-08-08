"""Real UI widgets wired to the controller, end to end — through the actual
Editor and real DB, not just calling handler functions directly."""

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from app.db import summaries
from app.db import templates as templates_db
from app.models import Summary
from app.ui.editor import Editor
from app.ui.editor_controller import EditorController


def _make_editor(conn):
    controller = EditorController(conn)
    editor = Editor(controller)
    templates_db.seed_if_empty(conn)
    editor.procedure_section.set_templates(templates_db.list_active(conn))  # not owned by Editor — see main_window.py
    editor.show()
    return editor, controller


def test_loading_a_new_summary_enables_the_action_bar_and_shows_unnamed(db_conn, qapp):
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    # Overflow (Duplicate/Delete) only needs a summary open. Print/Save
    # additionally need Name/Telephone/BHT to be valid — a brand-new
    # blank card starts out invalid (nothing's been filled in yet), so
    # they stay disabled until that's fixed (docs/decisions.md).
    assert editor.overflow_button.isEnabled()
    assert not editor.print_button.isEnabled()
    assert not editor.save_button.isEnabled()
    assert editor._name_label.text() == "(unnamed)"
    # Disabled with no red shown anywhere yet (nothing's been blurred) —
    # the muted status text is the only visible explanation, so it must
    # actually name what's missing (docs/decisions.md).
    assert editor._save_state_label.text() == "Fill in Name, Telephone, BHT to save"

    editor.patient_section.name_input.setText("W.D. Kusuma Wijerathna")
    editor.patient_section.name_input.editingFinished.emit()
    assert editor._save_state_label.text() == "Fill in Telephone, BHT to save", "narrows as fields are fixed"

    editor.patient_section.bht_input.setText("10178-2026")
    editor.patient_section.bht_input.editingFinished.emit()
    editor.patient_section.telephone_input.setText("0771234567")
    editor.patient_section.telephone_input.editingFinished.emit()
    controller.flush()  # settle the coalesce timer now — a stray armed one firing after teardown hits a closed db_conn

    assert editor.print_button.isEnabled()
    assert editor.save_button.isEnabled()
    # controller.flush() above actually wrote the pending fields and
    # emitted `saved`, so this correctly reads "✓ Saved", not "Not saved".
    assert editor._save_state_label.text().startswith("✓ Saved"), "reflects the real save that just happened"

    editor.close()


def test_patient_section_widgets_persist_to_the_db_on_blur(db_conn, qapp):
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    ps = editor.patient_section
    ps.name_input.setText("W.D. Kusuma Wijerathna")
    ps.name_input.editingFinished.emit()  # simulates real focus-loss
    ps.bht_input.setText("10178-2026")  # number-year format — app/util/validators.py::validate_bht
    ps.bht_input.editingFinished.emit()
    ps.age_input.setText("54")
    ps.age_input.editingFinished.emit()
    ps.sex_input.setCurrentText("Female")  # combobox saves immediately on selection
    ps.blood_group_input.setCurrentText("O+")
    ps.admission_date.line.setText("10/01/2026")
    ps.admission_date.line.editingFinished.emit()
    qapp.processEvents()

    QTest.qWait(350)  # past the 200ms coalesce window
    qapp.processEvents()

    row = summaries.get(db_conn, created.id)
    assert row.patient_name == "W.D. Kusuma Wijerathna"
    assert row.bht_number == "10178-2026"
    assert row.age == 54, "Age typed as text converted to int and persisted"
    assert row.sex == "Female", "Sex combobox selection persisted immediately"
    assert row.blood_group == "O+", "Blood Group combobox selection persisted immediately"
    assert row.date_admission == "2026-01-10", "Admission date typed + blurred converted to ISO and persisted"

    editor.close()


def test_procedure_template_insert_persists_without_a_later_blur(db_conn, qapp):
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    proc = editor.procedure_section
    proc.template_picker.setCurrentText("Thyroid lobectomy")
    qapp.processEvents()
    QTest.qWait(350)
    qapp.processEvents()
    row2 = summaries.get(db_conn, created.id)
    assert "GA induced" in (row2.procedure_steps or "")

    proc.title_input.setText("COMPLETE THYROIDECTOMY UNDER GA")
    proc.title_input.editingFinished.emit()
    QTest.qWait(350)
    qapp.processEvents()
    assert summaries.get(db_conn, created.id).procedure_title == "COMPLETE THYROIDECTOMY UNDER GA"

    editor.close()


def test_clinical_history_autogrow_field_persists_via_editing_finished(db_conn, qapp):
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    ch = editor.clinical_history_section
    ch.allergies_input.setPlainText("NKDA")
    ch.allergies_input.editingFinished.emit()  # simulates focusOutEvent firing it
    QTest.qWait(350)
    qapp.processEvents()
    assert summaries.get(db_conn, created.id).allergies == "NKDA"

    editor.close()


def test_investigations_analyte_and_management_persist(db_conn, qapp):
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    inv = editor.investigations_section
    inv.analyte_inputs["FBS"].setText("86")
    inv.analyte_inputs["FBS"].editingFinished.emit()
    inv.management_input.setPlainText("T. Paracetamol 1g PO PRN")
    inv.management_input.editingFinished.emit()
    QTest.qWait(350)
    qapp.processEvents()

    inv_rows = {r["label"]: r for r in summaries.list_investigations(db_conn, created.id)}
    assert inv_rows["FBS"]["value"] == "86"
    assert summaries.get(db_conn, created.id).management == "T. Paracetamol 1g PO PRN", (
        "Management (summary column, not investigations table) persisted"
    )

    editor.close()


def test_round_trip_reload_redisplays_everything_correctly(db_conn, qapp):
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    ps = editor.patient_section
    ps.name_input.setText("W.D. Kusuma Wijerathna")
    ps.name_input.editingFinished.emit()
    ps.age_input.setText("54")
    ps.age_input.editingFinished.emit()
    ps.sex_input.setCurrentText("Female")
    ps.admission_date.line.setText("10/01/2026")
    ps.admission_date.line.editingFinished.emit()

    proc = editor.procedure_section
    proc.title_input.setText("COMPLETE THYROIDECTOMY UNDER GA")
    proc.title_input.editingFinished.emit()

    ch = editor.clinical_history_section
    ch.allergies_input.setPlainText("NKDA")
    ch.allergies_input.editingFinished.emit()

    inv = editor.investigations_section
    inv.analyte_inputs["FBS"].setText("86")
    inv.analyte_inputs["FBS"].editingFinished.emit()

    qapp.processEvents()
    QTest.qWait(350)
    qapp.processEvents()

    fresh_controller = EditorController(db_conn)
    fresh_editor = Editor(fresh_controller)
    fresh_editor.show()
    fresh_editor.load_summary(created.id)
    qapp.processEvents()

    assert fresh_editor.patient_section.name_input.text() == "W.D. Kusuma Wijerathna"
    assert fresh_editor.patient_section.age_input.text() == "54"
    assert fresh_editor.patient_section.sex_input.currentText() == "Female"
    assert fresh_editor.patient_section.admission_date.line.text() == "10/01/2026"
    assert fresh_editor.procedure_section.title_input.text() == "COMPLETE THYROIDECTOMY UNDER GA"
    assert fresh_editor.clinical_history_section.allergies_input.toPlainText() == "NKDA"
    assert fresh_editor.investigations_section.analyte_inputs["FBS"].text() == "86"

    # Save-state label updates on real save.
    assert editor._save_state_label.text().startswith("✓ Saved")

    editor.close()
    fresh_editor.close()


def test_attachment_added_through_the_real_editor_survives_a_reload(db_conn, qapp, tmp_path):
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    source = tmp_path / "histology.pdf"
    source.write_bytes(b"a real small attachment file")
    editor.attachments_section.set_enabled(True)
    editor.attachments_section._import_paths([str(source)])
    qapp.processEvents()

    assert len(editor.attachments_section.rows) == 1
    assert len(controller.list_attachments()) == 1

    fresh_controller = EditorController(db_conn)
    fresh_editor = Editor(fresh_controller)
    fresh_editor.show()
    fresh_editor.load_summary(created.id)
    qapp.processEvents()

    assert len(fresh_editor.attachments_section.rows) == 1
    assert fresh_editor.attachments_section.rows[0].attachment.filename == "histology.pdf"

    editor.close()
    fresh_editor.close()


def test_duplicate_creates_a_second_row_and_repopulates_the_editor(db_conn, qapp):
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    ps = editor.patient_section
    ps.name_input.setText("W.D. Kusuma Wijerathna")
    ps.name_input.editingFinished.emit()
    proc = editor.procedure_section
    proc.title_input.setText("THYROIDECTOMY")
    proc.title_input.editingFinished.emit()
    qapp.processEvents()
    QTest.qWait(350)
    qapp.processEvents()

    duplicated_ids = []
    editor.duplicated.connect(duplicated_ids.append)

    editor._on_duplicate()
    qapp.processEvents()

    assert len(duplicated_ids) == 1
    new_id = duplicated_ids[0]
    assert new_id != created.id
    assert editor.patient_section.name_input.text() == "W.D. Kusuma Wijerathna", "editor repopulated with the duplicate"
    assert editor.procedure_section.title_input.text() == "THYROIDECTOMY"

    new_row = summaries.get(db_conn, new_id)
    assert new_row.patient_name == "W.D. Kusuma Wijerathna"
    new_investigations = {i["label"]: i["value"] for i in summaries.list_investigations(db_conn, new_id)}
    assert all(v == "" for v in new_investigations.values()), "duplicate gets blank investigations, not copied values"

    editor.close()


def test_delete_confirmed_soft_deletes_and_resets_the_editor_to_empty(db_conn, qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)

    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    ps = editor.patient_section
    ps.name_input.setText("W.D. Kusuma Wijerathna")
    ps.name_input.editingFinished.emit()
    QTest.qWait(350)
    qapp.processEvents()

    deleted_events = {"count": 0}
    editor.deleted.connect(lambda: deleted_events.__setitem__("count", deleted_events["count"] + 1))

    editor._on_delete()
    qapp.processEvents()

    assert deleted_events["count"] == 1
    assert editor._name_label.text() == "No summary open"
    assert editor.print_button.isEnabled() is False
    assert controller.summary_id is None

    still_there = summaries.get(db_conn, created.id)
    assert still_there is not None, "soft delete — the row still physically exists"
    assert still_there.deleted_at is not None
    assert len(summaries.list_page(db_conn)) == 0, "but no longer shows up in the normal list"


def test_delete_declined_leaves_the_record_untouched(db_conn, qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)

    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    deleted_events = {"count": 0}
    editor.deleted.connect(lambda: deleted_events.__setitem__("count", deleted_events["count"] + 1))

    editor._on_delete()
    qapp.processEvents()

    assert deleted_events["count"] == 0
    assert controller.summary_id == created.id, "editor still has the record open"
    assert summaries.get(db_conn, created.id).deleted_at is None

    editor.close()


def test_save_button_force_flushes_with_no_wait(db_conn, qapp):
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    ps = editor.patient_section
    ps.telephone_input.setText("0771234567")
    ps.telephone_input.editingFinished.emit()
    editor._on_save()  # what the Save button / Ctrl+S actually calls
    assert summaries.get(db_conn, created.id).telephone == "0771234567"

    editor.close()


def test_save_click_does_not_confirm_saved_when_the_forced_blur_reveals_invalid_data(db_conn, qapp):
    # Regression test: Save can be enabled based on the last-BLURRED
    # value of BHT/Name/Telephone, but clicking Save forces a blur via
    # _commit_focused_field() — if the user was still mid-edit typing
    # something invalid there, that forced blur is the first time it's
    # actually validated. Save must not flush()/confirm "Saved" over a
    # value it just rejected.
    editor, controller = _make_editor(db_conn)
    created = summaries.create(db_conn, Summary(
        patient_name="W.D. Kusuma Wijerathna", bht_number="10178-2026", telephone="0771234567",
    ))
    controller.load(created.id)
    editor.load_summary(created.id)
    qapp.processEvents()
    assert editor.save_button.isEnabled() is True

    # Real OS-level focus (needed for _commit_focused_field()'s
    # QApplication.focusWidget() check to find this widget) isn't
    # guaranteed by setFocus() alone once other tests in the same
    # session have left other top-level widgets open — same window-
    # activation quirk noted in test_section_patient.py's tab-order test.
    editor.raise_()
    editor.activateWindow()
    QTest.qWaitForWindowActive(editor)
    qapp.processEvents()

    ps = editor.patient_section
    ps.bht_input.setFocus()
    qapp.processEvents()
    assert qapp.focusWidget() is ps.bht_input, "bht_input must actually hold focus before the forced-blur race can be tested"
    ps.bht_input.setText("garbage")  # typed, not yet blurred
    qapp.processEvents()
    assert editor.save_button.isEnabled() is True, "still reflects the last-blurred (valid) value"

    editor._on_save()  # what the Save button actually calls
    qapp.processEvents()

    assert ps.bht_input.property("invalid") is True, "the forced blur flagged it red"
    assert editor._save_state_label.text() != "✓ Saved", "must not claim saved over a value it just rejected"
    assert summaries.get(db_conn, created.id).bht_number == "10178-2026", "the bad value never reached the DB"

    editor.close()


def test_print_click_does_not_open_preview_when_the_forced_blur_reveals_invalid_data(db_conn, qapp, monkeypatch):
    from app.ui.dialogs.print_preview import PrintPreviewDialog

    # Tracks whether THIS test's _on_print() call constructs a preview —
    # scanning qapp.topLevelWidgets() for a PrintPreviewDialog instead
    # would false-positive on one left over from an earlier test in the
    # same session that hasn't been garbage-collected yet.
    constructed = []
    original_init = PrintPreviewDialog.__init__

    def _tracking_init(self, *args, **kwargs):
        constructed.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(PrintPreviewDialog, "__init__", _tracking_init)
    monkeypatch.setattr(PrintPreviewDialog, "exec", lambda self: None)

    editor, controller = _make_editor(db_conn)
    created = summaries.create(db_conn, Summary(
        patient_name="W.D. Kusuma Wijerathna", bht_number="10178-2026", telephone="0771234567",
    ))
    controller.load(created.id)
    editor.load_summary(created.id)
    qapp.processEvents()
    assert editor.print_button.isEnabled() is True

    editor.raise_()
    editor.activateWindow()
    QTest.qWaitForWindowActive(editor)
    qapp.processEvents()

    ps = editor.patient_section
    ps.telephone_input.setFocus()
    qapp.processEvents()
    assert qapp.focusWidget() is ps.telephone_input, "telephone_input must actually hold focus before the forced-blur race can be tested"
    ps.telephone_input.setText("not-a-phone-number")
    qapp.processEvents()
    assert editor.print_button.isEnabled() is True, "still reflects the last-blurred (valid) value"

    editor._on_print()  # what the Print button actually calls
    qapp.processEvents()

    assert ps.telephone_input.property("invalid") is True
    assert constructed == [], "must not open a preview for invalid data"

    editor.close()


def test_no_op_blur_on_an_already_saved_record_does_not_revert_the_label(db_conn, qapp):
    # Regression test: _update_save_print_enabled() runs on every blur of
    # Name/Telephone/BHT, valid or not, even ones where nothing actually
    # changed. It must not stomp a truthful "✓ Saved" back to "Not saved"
    # just because a field was clicked into and back out of again.
    editor, controller = _make_editor(db_conn)
    created = summaries.create(db_conn, Summary(
        patient_name="W.D. Kusuma Wijerathna", bht_number="10178-2026", telephone="0771234567",
    ))
    controller.load(created.id)
    editor.load_summary(created.id)
    qapp.processEvents()

    editor._on_saved()  # simulate a real save having just completed
    assert editor._save_state_label.text().startswith("✓ Saved")

    ps = editor.patient_section
    ps.name_input.editingFinished.emit()  # blur with no text change at all
    qapp.processEvents()

    assert editor._save_state_label.text().startswith("✓ Saved"), "an unrelated no-op blur must not revert this"

    editor.close()


def test_fill_in_message_reverts_to_not_saved_once_complete_before_any_flush(db_conn, qapp):
    # Isolates _update_save_print_enabled()'s "Fill in ..." -> "Not
    # saved" transition specifically, decoupled from an explicit flush()
    # (which would show "✓ Saved" instead — see the test above).
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()
    assert editor._save_state_label.text() == "Fill in Name, Telephone, BHT to save"

    ps = editor.patient_section
    ps.name_input.setText("W.D. Kusuma Wijerathna")
    ps.name_input.editingFinished.emit()
    ps.bht_input.setText("10178-2026")
    ps.bht_input.editingFinished.emit()
    ps.telephone_input.setText("0771234567")
    ps.telephone_input.editingFinished.emit()

    assert editor._save_state_label.text() == "Not saved"
    assert editor.save_button.isEnabled()

    controller.flush()  # settle the coalesce timer before teardown
    editor.close()
