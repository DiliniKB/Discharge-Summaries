"""Patient & Admission section: fields, defaults, and the keyboard-first
tab order requirement (docs/ui-spec.md §1)."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.ui.sections.patient import PatientSection


class _StubController:
    """bind_controller() only needs set_field to exist — the date-warning
    tests care about the label, not persistence."""

    def set_field(self, *args, **kwargs):
        pass


class _RecordingController:
    """Same minimal interface as _StubController, but remembers every
    set_field() call — the Name/Telephone/BHT validation tests need to
    assert an invalid value never reaches the controller at all, not
    just that the field looks red."""

    def __init__(self):
        self.calls = []

    def set_field(self, field_name, value):
        self.calls.append((field_name, value))


def test_section_title_and_default_state():
    sec = PatientSection()
    sec.show()
    assert sec._title.text() == "PATIENT & ADMISSION"
    assert sec.expanded is True, "open by default"
    assert sec.ward_input.text() == "46"
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


def _set_date(field, iso_date):
    # set_iso() alone doesn't fire value_changed (see datefield.py) — real
    # calendar-pick/blur behaviour emits it explicitly, so tests do the same.
    field.set_iso(iso_date)
    field.value_changed.emit(iso_date)


def test_date_warning_hidden_by_default():
    sec = PatientSection()
    sec.show()
    assert sec._date_warning_label.isVisible() is False


def test_surgery_before_admission_shows_warning():
    sec = PatientSection()
    sec.show()
    sec.bind_controller(_StubController())
    _set_date(sec.admission_date, "2026-01-10")
    _set_date(sec.surgery_date, "2026-01-05")

    assert sec._date_warning_label.isVisible() is True
    assert "Surgery date is before Admission date." in sec._date_warning_label.text()


def test_fixing_the_date_hides_the_warning_again():
    sec = PatientSection()
    sec.show()
    sec.bind_controller(_StubController())
    _set_date(sec.admission_date, "2026-01-10")
    _set_date(sec.surgery_date, "2026-01-05")
    assert sec._date_warning_label.isVisible() is True

    _set_date(sec.surgery_date, "2026-01-12")
    assert sec._date_warning_label.isVisible() is False


def test_blank_name_is_flagged_and_never_saved():
    sec = PatientSection()
    sec.show()
    controller = _RecordingController()
    sec.bind_controller(controller)

    sec.name_input.setText("")
    sec.name_input.editingFinished.emit()

    assert sec.name_input.property("invalid") is True
    assert sec._name_error_label.isVisible() is True
    assert "required" in sec._name_error_label.text().lower()
    assert controller.calls == [], "a blank name must never reach the controller"


def test_valid_name_saves_and_clears_the_flag():
    sec = PatientSection()
    sec.show()
    controller = _RecordingController()
    sec.bind_controller(controller)

    sec.name_input.setText("")
    sec.name_input.editingFinished.emit()
    sec.name_input.setText("W.D. Kusuma Wijerathna")
    sec.name_input.editingFinished.emit()

    assert sec.name_input.property("invalid") is False
    assert sec._name_error_label.isVisible() is False
    assert controller.calls == [("patient_name", "W.D. Kusuma Wijerathna")]


def test_bht_wrong_format_is_flagged_and_never_saved():
    sec = PatientSection()
    sec.show()
    controller = _RecordingController()
    sec.bind_controller(controller)

    sec.bht_input.setText("10178")  # missing the -YYYY suffix
    sec.bht_input.editingFinished.emit()

    assert sec.bht_input.property("invalid") is True
    assert sec._bht_error_label.isVisible() is True
    assert controller.calls == []


def test_bht_correct_format_saves():
    sec = PatientSection()
    sec.show()
    controller = _RecordingController()
    sec.bind_controller(controller)

    sec.bht_input.setText("10178-2026")
    sec.bht_input.editingFinished.emit()

    assert sec.bht_input.property("invalid") is False
    assert sec._bht_error_label.isVisible() is False
    assert controller.calls == [("bht_number", "10178-2026")]


def test_telephone_blank_is_flagged_and_never_saved():
    sec = PatientSection()
    sec.show()
    controller = _RecordingController()
    sec.bind_controller(controller)

    sec.telephone_input.setText("")
    sec.telephone_input.editingFinished.emit()

    assert sec.telephone_input.property("invalid") is True
    assert sec._telephone_error_label.isVisible() is True
    assert controller.calls == [], "a blank telephone must never reach the controller"


def test_telephone_wrong_format_is_flagged_and_never_saved():
    sec = PatientSection()
    sec.show()
    controller = _RecordingController()
    sec.bind_controller(controller)

    sec.telephone_input.setText("12345")
    sec.telephone_input.editingFinished.emit()

    assert sec.telephone_input.property("invalid") is True
    assert sec._telephone_error_label.isVisible() is True
    assert controller.calls == []


def test_telephone_correct_format_saves():
    sec = PatientSection()
    sec.show()
    controller = _RecordingController()
    sec.bind_controller(controller)

    sec.telephone_input.setText("0771234567")
    sec.telephone_input.editingFinished.emit()

    assert sec.telephone_input.property("invalid") is False
    assert controller.calls == [("telephone", "0771234567")]


def test_invalid_bht_does_not_block_other_fields_from_saving():
    # Blocking is per-field, not per-record — an invalid BHT must not
    # stop Name (already valid) from autosaving on its own blur.
    sec = PatientSection()
    sec.show()
    controller = _RecordingController()
    sec.bind_controller(controller)

    sec.name_input.setText("W.D. Kusuma Wijerathna")
    sec.name_input.editingFinished.emit()
    sec.bht_input.setText("not-a-valid-bht")
    sec.bht_input.editingFinished.emit()

    assert ("patient_name", "W.D. Kusuma Wijerathna") in controller.calls
    assert all(field != "bht_number" for field, _ in controller.calls)


def test_is_valid_reflects_real_state_even_when_nothing_is_flagged_red():
    # A brand-new blank card has never been blurred, so nothing shows
    # red — but is_valid() must still report the truth: it isn't
    # actually valid yet. Editor relies on this to gate Save/Print
    # (docs/decisions.md), separately from what's currently shown red.
    sec = PatientSection()
    sec.show()
    assert sec.is_valid() is False

    sec.bind_controller(_StubController())
    sec.name_input.setText("W.D. Kusuma Wijerathna")
    sec.name_input.editingFinished.emit()
    assert sec.is_valid() is False, "BHT and Telephone are still blank"

    sec.bht_input.setText("10178-2026")
    sec.bht_input.editingFinished.emit()
    assert sec.is_valid() is False, "Telephone is still blank"

    sec.telephone_input.setText("0771234567")
    sec.telephone_input.editingFinished.emit()
    assert sec.is_valid() is True


def test_validity_changed_emits_after_every_relevant_blur_and_populate():
    from app.models import Summary

    sec = PatientSection()
    sec.show()
    sec.bind_controller(_StubController())
    emitted = []
    sec.validity_changed.connect(emitted.append)

    sec.name_input.setText("W.D. Kusuma Wijerathna")
    sec.name_input.editingFinished.emit()
    assert emitted[-1] is False  # BHT/Telephone still blank

    sec.bht_input.setText("10178-2026")
    sec.bht_input.editingFinished.emit()
    sec.telephone_input.setText("0771234567")
    sec.telephone_input.editingFinished.emit()
    assert emitted[-1] is True

    sec.populate(Summary(patient_name="", bht_number=""))
    assert emitted[-1] is False, "populate() reports the newly loaded record's real validity too"


def test_populate_never_flags_a_blank_new_card_immediately():
    from app.models import Summary

    sec = PatientSection()
    sec.show()
    # A brand-new card (summaries.create() with no args) has blank
    # Name/BHT/Telephone from the moment it's created — must NOT look
    # already-invalid before the user has touched anything. The flag
    # only ever appears from this section's own blur handlers.
    summary = Summary(patient_name="", bht_number="")

    sec.populate(summary)

    assert sec.name_input.property("invalid") is False
    assert sec.bht_input.property("invalid") is False
    assert sec.telephone_input.property("invalid") is False
    assert sec._name_error_label.isVisible() is False
    assert sec._bht_error_label.isVisible() is False
    assert sec._telephone_error_label.isVisible() is False


def test_populate_clears_invalid_flag_left_over_from_a_previous_record():
    from app.models import Summary

    sec = PatientSection()
    sec.show()
    sec.bind_controller(_StubController())

    # Leave the Name field flagged red via a real blur, as if the user
    # had typed something invalid and moved on without fixing it.
    sec.name_input.setText("")
    sec.name_input.editingFinished.emit()
    assert sec.name_input.property("invalid") is True

    # Switching to a different (valid) record must not carry that stale
    # red flag over onto the newly loaded one.
    sec.populate(Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178-2026", telephone="0771234567"))

    assert sec.name_input.property("invalid") is False
    assert sec._name_error_label.isVisible() is False


def test_populate_with_inconsistent_saved_dates_shows_warning_immediately():
    from app.models import Summary

    sec = PatientSection()
    sec.show()
    summary = Summary(
        patient_name="Test Patient",
        bht_number="1",
        date_admission="2026-01-15",
        date_surgery="2026-01-12",
        date_discharge="2026-01-10",
    )

    sec.populate(summary)

    assert sec._date_warning_label.isVisible() is True
