"""Header doctor dropdown: real DB doctors, last-selected persistence,
attribution wiring (created_by/last_edited_by)."""

from app.db import app_meta, doctors as doctors_db, summaries
from app.ui.main_window import LAST_DOCTOR_KEY, MANAGE_DOCTORS_LABEL, MainWindow


def test_doctor_dropdown_backed_by_real_db(isolated_data_dir):
    win = MainWindow()
    win.show()
    picker = win._doctor_picker

    assert picker.isEditable() is False, "combobox is not editable (dropdown-only)"
    assert len(doctors_db.list_active(win._conn)) == 4, "doctors were seeded into the real DB on first launch"

    expected_values = [d.name for d in doctors_db.list_active(win._conn)] + [MANAGE_DOCTORS_LABEL]
    actual_values = [picker.itemText(i) for i in range(picker.count())]
    assert actual_values == expected_values, "dropdown values match the real DB doctors, in sort_order, plus the sentinel"

    assert win.selected_doctor.name == "Dr. S. Herath", "default selected_doctor is the consultant (sort_order=0)"
    assert picker.currentText() == win.selected_doctor.name

    win.close()


def test_selecting_a_doctor_updates_attribution_and_persists(isolated_data_dir):
    win = MainWindow()
    win.show()
    picker = win._doctor_picker

    picker.setCurrentIndex(2)
    assert win.selected_doctor.name == doctors_db.list_active(win._conn)[2].name
    assert win._controller.current_doctor_id == win.selected_doctor.id, "attribution wiring updates too"
    assert app_meta.get(win._conn, LAST_DOCTOR_KEY) == str(win.selected_doctor.id), "selection persists to app_meta immediately"

    assert win.header.height() == 56

    win.close()


def test_created_by_and_last_edited_by_are_stamped_correctly(isolated_data_dir):
    win = MainWindow()
    win.show()
    picker = win._doctor_picker

    created = win._controller.new_summary()
    assert created.created_by == win.selected_doctor.id, "new_summary() stamps created_by with the selected doctor"
    assert created.last_edited_by == win.selected_doctor.id

    win.editor.patient_section.name_input.setText("Test Patient")
    win.editor.patient_section.name_input.editingFinished.emit()
    win._controller.flush()
    reloaded = summaries.get(win._conn, created.id)
    assert reloaded.last_edited_by == win.selected_doctor.id

    # Switch doctor mid-session, edit again — last_edited_by should follow.
    first_doctor_id = win.selected_doctor.id
    picker.setCurrentIndex(0)
    win.editor.patient_section.bht_input.setText("99999")
    win.editor.patient_section.bht_input.editingFinished.emit()
    win._controller.flush()
    reloaded2 = summaries.get(win._conn, created.id)
    assert reloaded2.last_edited_by == win.selected_doctor.id, "last_edited_by follows a mid-session doctor switch"
    assert reloaded2.created_by == first_doctor_id, "created_by stays fixed, not overwritten by later edits"

    win.close()


def test_last_selected_doctor_persists_across_a_restart(isolated_data_dir):
    win = MainWindow()
    win.show()
    picker = win._doctor_picker
    picker.setCurrentIndex(0)
    expected_name = win.selected_doctor.name
    win.close()

    win2 = MainWindow()
    win2.show()
    assert win2.selected_doctor.name == expected_name, "re-opening the app restores the last-selected doctor"
    win2.close()
