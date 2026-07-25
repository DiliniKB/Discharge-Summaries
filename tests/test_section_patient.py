"""Patient & Admission section: fields, defaults, and the keyboard-first
tab order requirement (docs/ui-spec.md §1)."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.ui.sections.patient import PatientSection


def test_section_title_and_default_state():
    sec = PatientSection()
    sec.show()
    assert sec._title.text() == "PATIENT & ADMISSION"
    assert sec.expanded is True, "open by default"
    assert sec.ward_input.text() == "45"
    assert [sec.sex_input.itemText(i) for i in range(sec.sex_input.count())] == ["", "Female", "Male"]


def test_fields_hold_entered_values():
    sec = PatientSection()
    sec.show()
    sec.name_input.setText("W.D. Kusuma Wijerathna")
    sec.bht_input.setText("10178")
    sec.admission_date.set_iso("2026-01-10")

    assert sec.name_input.text() == "W.D. Kusuma Wijerathna"
    assert sec.bht_input.text() == "10178"
    assert sec.admission_date.get_iso() == "2026-01-10"


def test_discharge_date_defaults_to_today_admission_and_surgery_stay_blank():
    from PySide6.QtCore import QDate

    sec = PatientSection()
    assert sec.discharge_date.get_iso() == QDate.currentDate().toString("yyyy-MM-dd")
    assert sec.admission_date.get_iso() == ""
    assert sec.surgery_date.get_iso() == ""


def test_tab_order_follows_the_paper_form_top_to_bottom(qapp):
    # Comboboxes are skipped by Tab on macOS by default (Cocoa HI
    # guideline) regardless of their reported focusPolicy, which is why
    # Sex/Blood Group explicitly force Qt.StrongFocus in patient.py.
    #
    # show()+processEvents() alone isn't enough to guarantee real OS-level
    # keyboard focus lands on this widget once other tests in the same
    # session have left other top-level widgets open — window activation
    # must be explicitly waited for, or focusWidget() comes back None and
    # QTest.keyClick(None, ...) aborts the process.
    sec = PatientSection()
    sec.show()
    sec.raise_()
    sec.activateWindow()
    QTest.qWaitForWindowActive(sec)
    qapp.processEvents()

    named = {
        id(sec.name_input): "name",
        id(sec.age_input): "age",
        id(sec.sex_input): "sex",
        id(sec.bht_input): "bht",
        id(sec.ward_input): "ward",
        id(sec.telephone_input): "telephone",
        id(sec.blood_group_input): "blood_group",
        id(sec.admission_date.line): "admission",
        id(sec.surgery_date.line): "surgery",
        id(sec.discharge_date.line): "discharge",
    }
    sec.name_input.setFocus()
    qapp.processEvents()
    current = qapp.focusWidget()
    assert current is not None, "name_input must actually hold focus before tabbing from it"
    tab_order = ["name"]
    for _ in range(9):
        QTest.keyClick(current, Qt.Key_Tab)
        qapp.processEvents()
        current = qapp.focusWidget()
        if current is None:
            tab_order.append("NONE")
            break
        tab_order.append(named.get(id(current), f"UNKNOWN:{type(current).__name__}"))

    expected = ["name", "age", "sex", "bht", "ward", "telephone", "blood_group", "admission", "surgery", "discharge"]
    assert tab_order == expected, f"got: {' -> '.join(tab_order)}"
