"""Manage Doctors + Template Manager dialogs, including sentinel-triggered
opening through the real MainWindow header dropdowns."""

from app.db import doctors as doctors_db
from app.db import templates as templates_db
from app.ui.dialogs.doctors import DoctorsDialog
from app.ui.dialogs.templates import TemplatesDialog
from app.ui.main_window import MANAGE_DOCTORS_LABEL, MainWindow


def test_doctors_dialog_add_deactivate_reactivate(db_conn, qapp):
    doctors_db.seed_if_empty(db_conn)

    dd = DoctorsDialog(db_conn)
    dd.show()
    qapp.processEvents()
    assert len(dd._rows) == 4

    changed = {"count": 0}
    dd.doctors_changed.connect(lambda: changed.__setitem__("count", changed["count"] + 1))

    dd.name_input.setText("Dr. Test Intern")
    dd.designation_input.setText("Intern")
    dd.add_button.click()
    qapp.processEvents()
    assert len(doctors_db.list_active(db_conn)) == 5
    assert len(dd._rows) == 5
    assert changed["count"] == 1
    assert dd.name_input.text() == "" and dd.designation_input.text() == ""

    # Adding with a blank name must be a no-op — not silently create an unnamed doctor.
    count_before = len(doctors_db.list_active(db_conn))
    dd.name_input.setText("   ")
    dd.add_button.click()
    qapp.processEvents()
    assert len(doctors_db.list_active(db_conn)) == count_before

    target = doctors_db.list_active(db_conn)[-1]  # the one we just added
    assert target.active is True
    dd._on_deactivate(target)
    qapp.processEvents()
    assert target.id not in {d.id for d in doctors_db.list_active(db_conn)}
    assert any(d.id == target.id for d in doctors_db.list_all(db_conn)), "deactivated doctor still exists, not removed"
    assert changed["count"] == 2

    dd._on_reactivate(target)
    qapp.processEvents()
    assert target.id in {d.id for d in doctors_db.list_active(db_conn)}
    assert changed["count"] == 3

    # The dialog itself must render a Reactivate button for inactive doctors,
    # not just support it via the DB layer.
    doctors_db.deactivate(db_conn, target.id)
    dd.refresh()
    qapp.processEvents()
    found_reactivate_button = False
    for row in dd._rows:
        for child in row.findChildren(type(dd.add_button)):
            if child.text() == "Reactivate":
                found_reactivate_button = True
    assert found_reactivate_button

    dd.close()


def test_templates_dialog_edit_and_new(db_conn, qapp):
    templates_db.seed_if_empty(db_conn)

    td = TemplatesDialog(db_conn)
    td.show()
    qapp.processEvents()
    assert td.list_widget.count() == 3

    td.list_widget.setCurrentRow(0)
    qapp.processEvents()
    assert td.name_input.text() == td.list_widget.item(0).text()
    assert len(td.body_input.toPlainText()) > 0

    original_body = td.body_input.toPlainText()
    td.body_input.setPlainText(original_body + "\n6. Additional step added via the dialog.")
    td.save_button.click()
    qapp.processEvents()

    assert td._current_id is not None, "selection survives a Save (list rebuild doesn't lose it)"
    reloaded = templates_db.get(db_conn, td._current_id)
    assert "Additional step" in reloaded.body

    t_changed = {"count": 0}
    td.templates_changed.connect(lambda: t_changed.__setitem__("count", t_changed["count"] + 1))
    td.new_button.click()
    qapp.processEvents()
    assert len(templates_db.list_active(db_conn)) == 4
    assert td.name_input.text() == "New template"
    assert t_changed["count"] == 1
    td.close()


def test_manage_doctors_sentinel_opens_dialog_without_changing_selection(isolated_data_dir, qapp, monkeypatch):
    monkeypatch.setattr(DoctorsDialog, "exec", lambda self: self.show())

    win = MainWindow()
    win.show()
    qapp.processEvents()

    assert win._doctor_picker.itemText(win._doctor_picker.count() - 1) == MANAGE_DOCTORS_LABEL

    doctor_before = win.selected_doctor
    sentinel_index = win._doctor_picker.count() - 1
    win._doctor_picker.setCurrentIndex(sentinel_index)
    qapp.processEvents()
    assert win.selected_doctor.id == doctor_before.id
    assert win._doctor_picker.currentText() == doctor_before.name, "combobox snaps back to the real doctor's name"
    assert any(
        isinstance(w, DoctorsDialog) and w.isVisible() for w in qapp.topLevelWidgets()
    ), "selecting the sentinel genuinely opened the Manage Doctors dialog"
    for w in qapp.topLevelWidgets():
        if isinstance(w, DoctorsDialog):
            w.close()

    doctors_db.add(win._conn, "Dr. Newcomer", "SHO", sort_order=99)
    win._reload_doctors()
    qapp.processEvents()
    assert any(d.name == "Dr. Newcomer" for d in win._doctors)
    assert win._doctor_picker.itemText(win._doctor_picker.count() - 1) == MANAGE_DOCTORS_LABEL

    proc = win.editor.procedure_section
    assert proc.template_picker.itemText(proc.template_picker.count() - 1) == "Manage templates…"

    win.close()
