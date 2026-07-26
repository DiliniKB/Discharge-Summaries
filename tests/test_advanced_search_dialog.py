"""Advanced Search dialog — replaced the patient list's old inline search
box entirely (docs/decisions.md). Filters, sortable results table,
per-row Print/Edit actions, and a read-only view panel that updates on
row selection (no separate View button)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from app.db import doctors as doctors_db
from app.db import summaries
from app.models import Summary

from app.ui.dialogs.advanced_search import AdvancedSearchDialog
from app.ui.dialogs.print_preview import PrintPreviewDialog


class _FakeMainWindow:
    """Stand-in for MainWindow in tests that don't need a full window —
    just records what the Edit action would have done."""

    def __init__(self):
        self.loaded_summary_id = None
        self.selected_summary_id = None
        self.editor = self
        self.patient_list = self

    def load_summary(self, summary_id):
        self.loaded_summary_id = summary_id

    def select(self, summary_id):
        self.selected_summary_id = summary_id


def _seed_two(conn):
    doctors_db.seed_if_empty(conn)
    doc_a, doc_b = doctors_db.list_active(conn)[:2]
    first = summaries.create(conn, Summary(
        patient_name="W.D. Kusuma Wijerathna", bht_number="10178", ward="45", created_by=doc_a.id,
    ))
    second = summaries.create(conn, Summary(
        patient_name="A.B. Perera", bht_number="10202", ward="46", created_by=doc_b.id,
    ))
    return first, second, doc_a, doc_b


def test_dialog_opens_and_lists_everyone_with_no_filters(db_conn, qapp):
    _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    assert dialog.table.rowCount() == 2


def test_patient_name_filter_narrows_by_name_or_bht(db_conn, qapp):
    _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()

    dialog.patient_name_input.setText("wijerathna")
    dialog._run_search()
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "W.D. Kusuma Wijerathna"

    dialog.patient_name_input.setText("10202")
    dialog._run_search()
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "A.B. Perera"


def test_doctor_filter_narrows_the_results(db_conn, qapp):
    _first, _second, doc_a, _doc_b = _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()

    doc_a_index = next(i for i, d_id in enumerate(dialog._doctor_ids_by_index) if d_id == doc_a.id)
    dialog.doctor_picker.setCurrentIndex(doc_a_index)
    dialog._run_search()
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "W.D. Kusuma Wijerathna"


def test_clear_filters_restores_the_full_list(db_conn, qapp):
    _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()

    dialog.patient_name_input.setText("wijerathna")
    dialog._run_search()
    assert dialog.table.rowCount() == 1

    dialog._clear_filters()
    assert dialog.table.rowCount() == 2
    assert dialog.patient_name_input.text() == ""


def test_keyword_filter_matches_clinical_text_not_name(db_conn, qapp):
    summaries.create(db_conn, Summary(
        patient_name="Case One", bht_number="1", findings="unusual eosinophilic pattern",
    ))
    summaries.create(db_conn, Summary(patient_name="Case Two", bht_number="2"))
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()

    dialog.keyword_input.setText("eosinophilic")
    dialog._run_search()
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "Case One"


def test_sortable_header_reorders_by_patient_name(db_conn, qapp):
    _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    dialog.table.sortItems(0)  # Patient Name column, ascending
    names = [dialog.table.item(r, 0).text() for r in range(dialog.table.rowCount())]
    assert names == sorted(names)


def test_clicking_a_row_populates_the_view_panel_with_real_data(db_conn, qapp):
    first, _second, _doc_a, _doc_b = _seed_two(db_conn)
    summaries.update(db_conn, first.id, allergies="NKDA", procedure_title="thyroidectomy")
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    row = next(r for r in range(dialog.table.rowCount()) if dialog.table.item(r, 0).data(Qt.UserRole) == first.id)
    dialog.table.selectRow(row)
    qapp.processEvents()

    all_labels = dialog._view_scroll.body.findChildren(type(dialog._view_placeholder))
    texts = [w.text() for w in all_labels]
    assert any("NKDA" in t for t in texts)
    assert any("THYROIDECTOMY" in t for t in texts), "procedure title renders uppercase, matching the printed card"
    assert any("Wijerathna" in t for t in texts)


def test_view_panel_omits_blank_fields_and_shows_investigations_and_attribution(db_conn, qapp):
    first, _second, doc_a, _doc_b = _seed_two(db_conn)
    for row in summaries.list_investigations(db_conn, first.id):
        if row["label"] == "Hb":
            summaries.upsert_investigation(db_conn, row["id"], first.id, "Hb", "11.7", "g/dL", row["sort_order"])
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    row_index = next(r for r in range(dialog.table.rowCount()) if dialog.table.item(r, 0).data(Qt.UserRole) == first.id)
    dialog.table.selectRow(row_index)
    qapp.processEvents()

    all_labels = dialog._view_scroll.body.findChildren(type(dialog._view_placeholder))
    texts = [w.text() for w in all_labels]

    assert any("Hb 11.7" in t for t in texts), "investigation values are shown — previously missing entirely"
    assert any("No clinical history recorded." in t for t in texts), "blank clinical history group says so, not a wall of blanks"
    assert "Telephone" not in texts, "blank Telephone (never set on this fixture) is omitted entirely, not shown as '—'"
    assert any(f"Created by {doc_a.name}" in t for t in texts), "doctor attribution shown — who created this record"


def test_view_panel_resets_to_placeholder_on_a_fresh_search(db_conn, qapp):
    first, _second, _doc_a, _doc_b = _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    dialog.table.selectRow(0)
    qapp.processEvents()
    assert dialog._view_placeholder not in [
        dialog._view_scroll.body_layout.itemAt(i).widget() for i in range(dialog._view_scroll.body_layout.count())
    ]

    dialog._run_search()  # a fresh search should clear any prior selection's detail
    all_labels = dialog._view_scroll.body.findChildren(type(dialog._view_placeholder))
    assert any(w.text() == "Click a row to see the full record here." for w in all_labels)


def test_print_button_launches_print_preview_dialog(db_conn, qapp, monkeypatch):
    first, _second, _doc_a, _doc_b = _seed_two(db_conn)

    captured = {}

    def _fake_exec(self):
        captured["bytes"] = self.pdf_path.read_bytes()
        self.show()

    monkeypatch.setattr(PrintPreviewDialog, "exec", _fake_exec)

    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    dialog._on_print(first.id)
    assert b"Wijerathna" in captured.get("bytes", b"")


def test_edit_button_loads_the_summary_selects_it_and_closes_the_dialog(db_conn, qapp):
    first, _second, _doc_a, _doc_b = _seed_two(db_conn)
    fake_main_window = _FakeMainWindow()
    dialog = AdvancedSearchDialog(db_conn, fake_main_window)
    dialog.show()
    qapp.processEvents()

    dialog._on_edit(first.id)
    assert fake_main_window.loaded_summary_id == first.id
    assert fake_main_window.selected_summary_id == first.id
    assert dialog.result() == QDialog.Accepted
