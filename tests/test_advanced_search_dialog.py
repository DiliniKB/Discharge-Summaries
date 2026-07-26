"""Advanced Search dialog — replaced the patient list's old inline search
box entirely (docs/decisions.md). Filters, sortable results table,
per-row Print/Edit actions, and a read-only view panel that updates on
row selection (no separate View button)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from app.db import doctors as doctors_db
from app.db import summaries
from app.models import Summary

from app.ui.dialogs.advanced_search import (
    NAME_DEBOUNCE_MS,
    AdvancedSearchDialog,
    COLUMN_WIDTH_PADDING,
    _ACTION_BUTTON_LABELS,
    _compute_column_widths,
)
from app.ui.dialogs.print_preview import PrintPreviewDialog
from app.ui.dialogs.summary_full_view import SummaryFullViewDialog


class _FakeMainWindow:
    """Stand-in for MainWindow in tests that don't need a full window —
    just records what the Edit action would have done."""

    def __init__(self, selected_doctor=None):
        self.loaded_summary_id = None
        self.selected_summary_id = None
        self.selected_doctor = selected_doctor
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


def test_search_shows_a_loading_state_while_running(db_conn, qapp, monkeypatch):
    _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()

    observed = {}
    original_advanced_search = summaries.advanced_search

    def _instrumented_search(*args, **kwargs):
        # This is the only way to observe the transient loading state in
        # a fully synchronous call — by the time _run_search() returns to
        # the caller, the label is already hidden again.
        observed["label_visible"] = dialog._status_label.isVisible()
        observed["label_text"] = dialog._status_label.text()
        observed["button_enabled"] = dialog.search_button.isEnabled()
        return original_advanced_search(*args, **kwargs)

    monkeypatch.setattr(summaries, "advanced_search", _instrumented_search)
    dialog._run_search()

    assert observed["label_visible"] is True
    assert observed["label_text"] == "Searching…"
    assert observed["button_enabled"] is False

    # Back to the resting state once the (synchronous) search returns.
    assert dialog._status_label.isVisible() is False
    assert dialog.search_button.isEnabled() is True


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

    # setText() arms the 150ms debounce QTimer via textChanged. Bypassing
    # it with an immediate _run_search() for a deterministic test — but
    # the armed timer must be stopped too, or it fires for real later
    # (possibly during a LATER test, once db_conn's teardown has already
    # closed this connection — the exact bug this pattern caught before,
    # see tests/test_patient_list.py's history).
    dialog.patient_name_input.setText("wijerathna")
    dialog._name_debounce.stop()
    dialog._run_search()
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "W.D. Kusuma Wijerathna"

    dialog.patient_name_input.setText("10202")
    dialog._name_debounce.stop()
    dialog._run_search()
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "A.B. Perera"


def test_doctor_filter_narrows_the_results(db_conn, qapp):
    _first, _second, doc_a, _doc_b = _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()

    # Doctor filters live — no Search click needed (docs/decisions.md).
    doc_a_index = next(i for i, d_id in enumerate(dialog._doctor_ids_by_index) if d_id == doc_a.id)
    dialog.doctor_picker.setCurrentIndex(doc_a_index)
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "W.D. Kusuma Wijerathna"


def test_patient_name_debounce_fires_search_without_clicking(db_conn, qapp):
    _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    assert dialog.table.rowCount() == 2

    dialog.patient_name_input.setText("wijerathna")  # never calls _run_search() or clicks Search
    QTest.qWait(NAME_DEBOUNCE_MS + 200)
    qapp.processEvents()

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "W.D. Kusuma Wijerathna"


def test_keyword_and_date_filters_do_not_auto_search(db_conn, qapp):
    summaries.create(db_conn, Summary(
        patient_name="Case One", bht_number="1", findings="unusual eosinophilic pattern",
    ))
    summaries.create(db_conn, Summary(patient_name="Case Two", bht_number="2"))
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    assert dialog.table.rowCount() == 2

    dialog.keyword_input.setText("eosinophilic")
    qapp.processEvents()
    assert dialog.table.rowCount() == 2, "keyword typing alone must not narrow the results"

    dialog.created_from.set_iso("2020-01-01")
    qapp.processEvents()
    assert dialog.table.rowCount() == 2, "setting a date alone must not narrow the results"

    dialog.search_button.click()
    assert dialog.table.rowCount() == 1, "clicking Search finally applies the pending keyword filter"


def test_full_view_button_opens_summary_full_view_dialog(db_conn, qapp, monkeypatch):
    first, _second, _doc_a, _doc_b = _seed_two(db_conn)

    opened = {}

    def _fake_exec(self):
        opened["dialog"] = self
        self.show()

    monkeypatch.setattr(SummaryFullViewDialog, "exec", _fake_exec)

    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    dialog._on_full_view(first.id)
    assert "dialog" in opened
    assert opened["dialog"].windowTitle() == "W.D. Kusuma Wijerathna"


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


def test_view_panel_shows_attachments(db_conn, qapp):
    from app.db import attachments as attachments_db

    first, _second, _doc_a, _doc_b = _seed_two(db_conn)
    attachments_db.add(db_conn, first.id, "discharge-photo.jpg", "/fake/discharge-photo.jpg", 51200)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    row_index = next(r for r in range(dialog.table.rowCount()) if dialog.table.item(r, 0).data(Qt.UserRole) == first.id)
    dialog.table.selectRow(row_index)
    qapp.processEvents()

    all_labels = dialog._view_scroll.body.findChildren(type(dialog._view_placeholder))
    texts = [w.text() for w in all_labels]
    assert any("discharge-photo.jpg" in t for t in texts)


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
    first, _second, doc_a, doc_b = _seed_two(db_conn)

    captured = {}

    def _fake_exec(self):
        captured["bytes"] = self.pdf_path.read_bytes()
        self.show()

    monkeypatch.setattr(PrintPreviewDialog, "exec", _fake_exec)

    # first.id was created_by doc_a, but the header has doc_b selected —
    # the printed signature should follow the CURRENTLY selected doctor,
    # not whoever created the record (docs/decisions.md).
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow(selected_doctor=doc_b))
    dialog.show()
    qapp.processEvents()

    dialog._on_print(first.id)
    assert b"Wijerathna" in captured.get("bytes", b"")
    assert doc_b.name.encode() in captured["bytes"]
    assert doc_a.name.encode() not in captured["bytes"]


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


def test_computed_column_widths_fit_the_real_actions_buttons(db_conn, qapp):
    # Independently reconstruct the expected Actions width from real font
    # metrics + the QSS's own known padding/border (app/theme.py) — this
    # verifies the reasoning behind _compute_column_widths, not a copy of
    # the same magic number it produces.
    from app import theme

    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    metrics = QFontMetrics(dialog.table.font())
    expected_actions_width = sum(
        metrics.horizontalAdvance(label) + 2 * (1 + theme.INPUT_PADDING_X) for label in _ACTION_BUTTON_LABELS
    )
    expected_actions_width += 2 * theme.SPACING_UNIT + 2 * 4
    # QTableWidget::item's own QSS padding (app/theme.py) eats this much
    # off every cell's usable width, including setCellWidget() cells —
    # confirmed by direct measurement, see docs/decisions.md.
    expected_actions_width += COLUMN_WIDTH_PADDING

    widths = _compute_column_widths(dialog.table)
    assert widths[7] == expected_actions_width


def test_no_horizontal_scrollbar_with_real_seeded_data(db_conn, qapp):
    _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.resize(1200, 600)
    dialog.show()
    qapp.processEvents()

    assert dialog.table.horizontalScrollBar().isVisible() is False


def test_actions_column_actually_fits_the_rendered_buttons(db_conn, qapp):
    # Regression test: setCellWidget() places a widget inside the cell's
    # *content* rect, which QTableWidget::item's own QSS padding
    # (app/theme.py) shrinks below the raw column width — a column sized
    # to exactly fit the buttons' own sizeHint (ignoring that inset)
    # clips "Full View" visibly. Assert against the real cell widget's
    # actual on-screen size, not the column width number.
    from PySide6.QtWidgets import QPushButton

    first, _second, _doc_a, _doc_b = _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    row_index = next(r for r in range(dialog.table.rowCount()) if dialog.table.item(r, 0).data(Qt.UserRole) == first.id)
    cell = dialog.table.cellWidget(row_index, 7)
    buttons = cell.findChildren(QPushButton)
    assert len(buttons) == 3
    needed_width = sum(b.sizeHint().width() for b in buttons) + cell.layout().spacing() * 2
    margins = cell.layout().contentsMargins()
    needed_width += margins.left() + margins.right()
    assert cell.width() >= needed_width, "Actions cell is narrower than its own buttons need — they'll clip"


def test_patient_name_column_keeps_a_reasonable_width(db_conn, qapp):
    # Regression test: a naive fix for the Actions-column clipping (widen
    # every Fixed column) starved the Stretch column (Patient Name) down
    # toward 0 once the Fixed columns' computed widths added up close to
    # the available space — the single most important column disappearing
    # is worse than the bug it was fixing.
    _seed_two(db_conn)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    assert dialog.table.columnWidth(0) >= 140


def test_view_panel_open_button_calls_open_attachment_file(db_conn, qapp, monkeypatch):
    from app.db import attachments as attachments_db
    from PySide6.QtWidgets import QPushButton

    first, _second, _doc_a, _doc_b = _seed_two(db_conn)
    attachments_db.add(db_conn, first.id, "discharge-photo.jpg", "1/discharge-photo.jpg", 51200)
    dialog = AdvancedSearchDialog(db_conn, _FakeMainWindow())
    dialog.show()
    qapp.processEvents()

    called = {}
    monkeypatch.setattr(
        "app.ui.widgets.summary_view.open_attachment_file",
        lambda stored_path: called.setdefault("stored_path", stored_path),
    )

    row_index = next(r for r in range(dialog.table.rowCount()) if dialog.table.item(r, 0).data(Qt.UserRole) == first.id)
    dialog.table.selectRow(row_index)
    qapp.processEvents()

    open_buttons = [b for b in dialog._view_scroll.body.findChildren(QPushButton) if b.text() == "Open"]
    assert len(open_buttons) == 1
    open_buttons[0].click()
    assert called["stored_path"] == "1/discharge-photo.jpg"
