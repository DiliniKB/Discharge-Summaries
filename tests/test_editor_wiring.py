"""Real UI widgets wired to the controller, end to end — through the actual
Editor and real DB, not just calling handler functions directly."""

from PySide6.QtTest import QTest

from app.db import summaries
from app.db import templates as templates_db
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

    assert editor.print_button.isEnabled()
    assert editor._name_label.text() == "(unnamed)"

    editor.close()


def test_patient_section_widgets_persist_to_the_db_on_blur(db_conn, qapp):
    editor, controller = _make_editor(db_conn)
    created = controller.new_summary()
    editor.load_summary(created.id)
    qapp.processEvents()

    ps = editor.patient_section
    ps.name_input.setText("W.D. Kusuma Wijerathna")
    ps.name_input.editingFinished.emit()  # simulates real focus-loss
    ps.bht_input.setText("10178")
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
    assert row.bht_number == "10178"
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
