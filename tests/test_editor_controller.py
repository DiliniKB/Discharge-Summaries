"""EditorController: diff/coalesce autosave, flush, investigations, summary switching."""

from PySide6.QtTest import QTest

from app.db import summaries
from app.models import Summary
from app.ui.editor_controller import EditorController


def test_new_summary_creates_a_real_db_row_immediately(db_conn):
    ctrl = EditorController(db_conn)
    created = ctrl.new_summary()
    assert created.id is not None
    assert ctrl.summary_id == created.id
    assert summaries.get(db_conn, created.id) is not None


def test_set_field_noop_when_value_unchanged(db_conn):
    ctrl = EditorController(db_conn)
    ctrl.new_summary()
    ctrl.set_field("patient_name", "")  # already blank — matches current DB value
    assert not ctrl._timer.isActive()


def test_set_field_diffs_and_coalesces_rapid_changes_into_one_write(db_conn, qapp, monkeypatch):
    ctrl = EditorController(db_conn)
    created = ctrl.new_summary()

    saved_events = {"count": 0}
    ctrl.saved.connect(lambda: saved_events.__setitem__("count", saved_events["count"] + 1))

    write_calls = {"count": 0}
    original_update = summaries.update

    def counting_update(conn_arg, summary_id, **fields):
        write_calls["count"] += 1
        return original_update(conn_arg, summary_id, **fields)

    monkeypatch.setattr(summaries, "update", counting_update)

    ctrl.set_field("patient_name", "W.D. Kusuma Wijerathna")
    ctrl.set_field("bht_number", "10178")
    ctrl.set_field("ward", "45")
    assert ctrl._timer.isActive(), "timer is running after rapid field changes (not yet flushed)"
    assert write_calls["count"] == 0, "no write has happened yet — still coalescing"

    QTest.qWait(350)  # real wait past the 200ms coalesce window
    qapp.processEvents()

    assert write_calls["count"] == 1, "exactly ONE write call covers all 3 rapid field changes"
    assert saved_events["count"] == 1

    reloaded = summaries.get(db_conn, created.id)
    assert (reloaded.patient_name, reloaded.bht_number, reloaded.ward) == (
        "W.D. Kusuma Wijerathna",
        "10178",
        "45",
    )


def test_flush_force_writes_and_skips_when_nothing_pending(db_conn, qapp):
    ctrl = EditorController(db_conn)
    created = ctrl.new_summary()

    saved_events = {"count": 0}
    ctrl.saved.connect(lambda: saved_events.__setitem__("count", saved_events["count"] + 1))

    ctrl.set_field("telephone", "0771234567")
    assert ctrl._timer.isActive()
    ctrl.flush()
    assert not ctrl._timer.isActive()
    assert summaries.get(db_conn, created.id).telephone == "0771234567"
    assert saved_events["count"] == 1

    # Calling flush() with nothing pending must NOT emit 'saved' again (would
    # be a false "✓ Saved" with no actual change behind it).
    ctrl.flush()
    assert saved_events["count"] == 1


def test_set_investigation_persists_and_noops_when_unchanged(db_conn, qapp):
    ctrl = EditorController(db_conn)
    created = ctrl.new_summary()

    ctrl.set_investigation("FBS", "86")
    QTest.qWait(350)
    qapp.processEvents()
    inv = {i["label"]: i for i in summaries.list_investigations(db_conn, created.id)}
    assert inv["FBS"]["value"] == "86"
    assert len(inv) == 7, "still exactly 7 investigation rows, not duplicated"

    ctrl.set_investigation("FBS", "86")  # unchanged — should no-op
    assert not ctrl._timer.isActive()


def test_switching_summaries_auto_flushes_the_previous_one(db_conn):
    ctrl = EditorController(db_conn)
    created = ctrl.new_summary()

    ctrl.set_field("age", "54")
    assert ctrl._timer.isActive()

    second = summaries.create(db_conn, Summary(patient_name="A.B. Perera", bht_number="10202"))
    ctrl.load(second.id)

    assert summaries.get(db_conn, created.id).age == 54, "switching flushes the previous summary's pending change"
    assert ctrl.summary_id == second.id
    assert ctrl._pending_fields == {}
