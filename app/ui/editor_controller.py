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

    def set_investigation(self, label, value, unit="", sort_order=99):
        """unit/sort_order only matter the first time a new (ad-hoc) label
        is set — existing rows (the 7 standard analytes, or an ad-hoc row
        already in the DB) keep their own stored unit/sort_order."""
        if self.summary_id is None:
            return
        current = self._db_investigations.get(label)
        if current is not None:
            if current["value"] == value:
                return
            updated = dict(current)
            updated["value"] = value
        else:
            updated = {
                "id": None,
                "summary_id": self.summary_id,
                "label": label,
                "value": value,
                "unit": unit,
                "sort_order": sort_order,
            }
        self._db_investigations[label] = updated
        self._pending_investigations[label] = updated
        self._timer.start(COALESCE_MS)

    @property
    def investigations(self):
        """Read-only snapshot of the current summary's investigation rows,
        keyed by label — used by InvestigationsSection.populate()."""
        return dict(self._db_investigations)

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
            for label, row in self._pending_investigations.items():
                real_id = summaries.upsert_investigation(
                    self._conn, row["id"], self.summary_id, row["label"], row["value"], row["unit"], row["sort_order"]
                )
                # A brand-new ad-hoc row starts with id=None; record the
                # real id so a second edit updates in place instead of
                # inserting a duplicate.
                self._db_investigations[label]["id"] = real_id
            self._pending_investigations = {}
            wrote_anything = True

        if wrote_anything:
            self.saved.emit()
