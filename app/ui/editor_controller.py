"""Mediates between section widgets and app/db/summaries.py. Diffs on each
field blur, coalesces rapid blurs into one write. See docs/decisions.md
"Editor talks to the DB through a controller, not directly".

Widgets call set_field()/set_investigation() on blur; this diffs against
the last-known-saved snapshot and only calls summaries.update()/
upsert_investigation() for what actually changed, debounced so a user
tabbing quickly through several short fields doesn't trigger a write per
field. Wiring this to live widget blur events is a separate chunk — this
module is tested standalone against a real DB.
"""

import dataclasses

from PySide6.QtCore import QObject, QTimer, Signal

from app.db import summaries
from app.models import Summary

COALESCE_MS = 200

_SUMMARY_COLUMNS = [f.name for f in dataclasses.fields(Summary) if f.name != "id"]


class EditorController(QObject):
    saved = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.summary_id = None
        self._db_values = {}
        self._pending_fields = {}
        self._db_investigations = {}
        self._pending_investigations = {}

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.flush)

    def new_summary(self):
        """'+ New Card' — creates a blank record immediately, per
        docs/ui-spec.md §3.2 ('Creates a blank record and focuses the Name field')."""
        created = summaries.create(self._conn, Summary())
        self._load_snapshot(created)
        return created

    def load(self, summary_id):
        summary = summaries.get(self._conn, summary_id)
        self._load_snapshot(summary)
        return summary

    def _load_snapshot(self, summary):
        self.flush()  # save whatever was open before, silently — §7
        self.summary_id = summary.id
        self._db_values = {col: getattr(summary, col) for col in _SUMMARY_COLUMNS}
        self._pending_fields = {}
        self._db_investigations = {
            row["label"]: dict(row) for row in summaries.list_investigations(self._conn, summary.id)
        }
        self._pending_investigations = {}

    def set_field(self, field_name, value):
        if self.summary_id is None:
            return
        if self._db_values.get(field_name) == value:
            return
        self._db_values[field_name] = value
        self._pending_fields[field_name] = value
        self._timer.start(COALESCE_MS)

    def set_investigation(self, label, value):
        if self.summary_id is None:
            return
        current = self._db_investigations.get(label)
        if current is None or current["value"] == value:
            return
        updated = dict(current)
        updated["value"] = value
        self._db_investigations[label] = updated
        self._pending_investigations[label] = updated
        self._timer.start(COALESCE_MS)

    def flush(self):
        """Force-write anything pending immediately — used by Ctrl+S/Save,
        and internally before switching to a different summary."""
        self._timer.stop()
        wrote_anything = False

        if self._pending_fields:
            summaries.update(self._conn, self.summary_id, **self._pending_fields)
            self._pending_fields = {}
            wrote_anything = True

        if self._pending_investigations:
            for row in self._pending_investigations.values():
                summaries.upsert_investigation(
                    self._conn, row["id"], self.summary_id, row["label"], row["value"], row["unit"], row["sort_order"]
                )
            self._pending_investigations = {}
            wrote_anything = True

        if wrote_anything:
            self.saved.emit()
