"""Recently Deleted dialog — the actual safety net for Delete now that
Delete itself is a single Yes/No click (docs/decisions.md)."""

from app.db import summaries
from app.models import Summary
from app.ui.dialogs.recently_deleted import RecentlyDeletedDialog


class _FakeMainWindow:
    def __init__(self, conn):
        from app.ui.patient_list import PatientList

        self.patient_list = PatientList(conn)


def test_empty_state_when_nothing_deleted(db_conn, qapp):
    dialog = RecentlyDeletedDialog(db_conn, _FakeMainWindow(db_conn))
    dialog.show()

    assert len(dialog._rows) == 0
    assert dialog._empty_label.isVisible() is True


def test_lists_real_soft_deleted_records(db_conn, qapp):
    created = summaries.create(db_conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))
    summaries.soft_delete(db_conn, created.id)

    dialog = RecentlyDeletedDialog(db_conn, _FakeMainWindow(db_conn))
    dialog.show()

    assert len(dialog._rows) == 1
    assert dialog._empty_label.isVisible() is False


def test_restore_removes_the_row_and_clears_deleted_at(db_conn, qapp):
    created = summaries.create(db_conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178"))
    summaries.soft_delete(db_conn, created.id)

    fake_main_window = _FakeMainWindow(db_conn)
    dialog = RecentlyDeletedDialog(db_conn, fake_main_window)
    dialog.show()
    assert len(dialog._rows) == 1

    record = summaries.list_deleted(db_conn)[0]
    dialog._on_restore(record)

    assert len(dialog._rows) == 0, "restored row disappears from this dialog's own list immediately"
    assert dialog._empty_label.isVisible() is True
    assert summaries.get(db_conn, created.id).deleted_at is None
    assert len(fake_main_window.patient_list._cards) == 1, "main patient list refreshed too, not just this dialog"
