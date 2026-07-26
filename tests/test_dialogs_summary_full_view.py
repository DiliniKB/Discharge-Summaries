"""Full View dialog — a dedicated, visually organized detail popup
alongside Advanced Search's compact inline quick-view panel. Has its own
layout (hero header, card sections, allergy alert), not a bigger copy of
the quick-view panel's rendering (docs/decisions.md)."""

from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton

from app.db import doctors as doctors_db
from app.db import summaries
from app.models import Summary
from app.ui.dialogs.summary_full_view import SummaryFullViewDialog


def test_shows_the_real_record(db_conn, qapp):
    doctors_db.seed_if_empty(db_conn)
    doctor = doctors_db.list_active(db_conn)[0]
    created = summaries.create(db_conn, Summary(
        patient_name="W.D. Kusuma Wijerathna",
        bht_number="10178",
        procedure_title="thyroidectomy",
        allergies="NKDA",
        created_by=doctor.id,
    ))
    investigations = summaries.list_investigations(db_conn, created.id)
    doctors_by_id = {d.id: d for d in doctors_db.list_all(db_conn)}

    dialog = SummaryFullViewDialog(created, investigations, doctors_by_id)
    dialog.show()
    qapp.processEvents()

    assert dialog.windowTitle() == "W.D. Kusuma Wijerathna"
    texts = [label.text() for label in dialog.findChildren(QLabel)]
    assert any("Wijerathna" in t for t in texts)
    assert any("THYROIDECTOMY" in t for t in texts)
    assert any("NKDA" in t for t in texts)
    assert any(f"Created by {doctor.name}" in t for t in texts)


def test_allergy_alert_shown_when_present(db_conn, qapp):
    doctors_db.seed_if_empty(db_conn)
    created = summaries.create(db_conn, Summary(
        patient_name="W.D. Kusuma Wijerathna", bht_number="10178", allergies="Penicillin",
    ))
    investigations = summaries.list_investigations(db_conn, created.id)
    doctors_by_id = {d.id: d for d in doctors_db.list_all(db_conn)}

    dialog = SummaryFullViewDialog(created, investigations, doctors_by_id)
    dialog.show()
    qapp.processEvents()

    alert_cards = [w for w in dialog.findChildren(QFrame) if w.objectName() == "AlertCard"]
    assert len(alert_cards) == 1
    texts = [label.text() for label in dialog.findChildren(QLabel)]
    assert any("Allergies: Penicillin" in t for t in texts)


def test_allergy_alert_omitted_when_blank(db_conn, qapp):
    doctors_db.seed_if_empty(db_conn)
    created = summaries.create(db_conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))
    investigations = summaries.list_investigations(db_conn, created.id)
    doctors_by_id = {d.id: d for d in doctors_db.list_all(db_conn)}

    dialog = SummaryFullViewDialog(created, investigations, doctors_by_id)
    dialog.show()
    qapp.processEvents()

    alert_cards = [w for w in dialog.findChildren(QFrame) if w.objectName() == "AlertCard"]
    assert len(alert_cards) == 0


def test_admission_fields_laid_out_side_by_side_not_stacked(db_conn, qapp):
    doctors_db.seed_if_empty(db_conn)
    created = summaries.create(db_conn, Summary(
        patient_name="W.D. Kusuma Wijerathna", bht_number="10178",
        telephone="0771234567", blood_group="O+",
    ))
    investigations = summaries.list_investigations(db_conn, created.id)
    doctors_by_id = {d.id: d for d in doctors_db.list_all(db_conn)}

    dialog = SummaryFullViewDialog(created, investigations, doctors_by_id)
    dialog.show()
    qapp.processEvents()

    telephone_label = next(w for w in dialog.findChildren(QLabel) if w.text() == "0771234567")
    blood_group_label = next(w for w in dialog.findChildren(QLabel) if w.text() == "O+")
    # Side by side means roughly the same y position, not stacked below each other.
    assert abs(telephone_label.mapTo(dialog, telephone_label.rect().topLeft()).y()
               - blood_group_label.mapTo(dialog, blood_group_label.rect().topLeft()).y()) < 5


def test_clinical_history_card_omitted_entirely_when_blank(db_conn, qapp):
    doctors_db.seed_if_empty(db_conn)
    created = summaries.create(db_conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))
    investigations = summaries.list_investigations(db_conn, created.id)
    doctors_by_id = {d.id: d for d in doctors_db.list_all(db_conn)}

    dialog = SummaryFullViewDialog(created, investigations, doctors_by_id)
    dialog.show()
    qapp.processEvents()

    headers = [w.text() for w in dialog.findChildren(QLabel) if w.objectName() == "SectionHeader"]
    assert "CLINICAL HISTORY" not in headers
    assert "ADMISSION" in headers  # sanity: other sections still render


def test_close_button_accepts(db_conn, qapp):
    doctors_db.seed_if_empty(db_conn)
    created = summaries.create(db_conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))
    investigations = summaries.list_investigations(db_conn, created.id)
    doctors_by_id = {d.id: d for d in doctors_db.list_all(db_conn)}

    dialog = SummaryFullViewDialog(created, investigations, doctors_by_id)
    dialog.show()
    qapp.processEvents()

    close_buttons = [w for w in dialog.findChildren(QPushButton) if w.text() == "Close"]
    assert len(close_buttons) == 1
    close_buttons[0].click()
    assert dialog.result() == QDialog.Accepted
