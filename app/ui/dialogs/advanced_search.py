"""Advanced Search dialog — replaces the patient list's old inline search
box entirely (docs/decisions.md). Patient Name and Doctor filter live (no
Search click needed — docs/decisions.md); Keyword and the date ranges
only apply when Search is clicked, since a full clinical-text scan or an
unindexed date-range scan isn't something to fire on every keystroke.

Selecting a row updates the read-only quick-view panel automatically —
no separate View button (docs/decisions.md). A "Full View" button opens
the same content bigger, in its own dialog (app/ui/dialogs/summary_full_view.py).
Print/Edit remain explicit per-row actions since those are real,
consequential operations.
"""

import tempfile

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import theme
from app.db import attachments as attachments_db
from app.db import doctors as doctors_db
from app.db import summaries
from app.printing import layout as print_layout
from app.ui.dialogs.print_preview import PrintPreviewDialog
from app.ui.dialogs.summary_full_view import SummaryFullViewDialog
from app.ui.widgets.datefield import DateField
from app.ui.widgets.labeled import LabeledField
from app.ui.widgets.scrollframe import ScrollFrame
from app.ui.widgets.summary_view import populate_summary_view
from app.util.screen import clamped_dialog_size

ALL_DOCTORS_LABEL = "All doctors"
NAME_DEBOUNCE_MS = 150
ACTION_BUTTON_HEIGHT = 26  # explicit, not the natural QSS sizeHint — see docs/decisions.md
_ACTIONS_CELL_MARGIN_Y = 2  # _build_actions_cell's own QHBoxLayout top/bottom margin
# The default row height (theme.INPUT_HEIGHT_PX) is sized for a single line
# of table TEXT, not for the Actions column's real buttons — and
# QTableWidget::item's own vertical padding (theme.TABLE_ITEM_PADDING_Y,
# same inset already accounted for horizontally in COLUMN_WIDTH_PADDING
# below) eats into a *cell widget's* available height too, not just a
# text item's. A row sized to exactly fit the buttons with no allowance
# for that inset clips them top and bottom — confirmed by measuring a
# real cell widget's actual on-screen height against the row height that
# contained it, same method used for the horizontal clipping fix.
_ROW_HEIGHT = ACTION_BUTTON_HEIGHT + 2 * _ACTIONS_CELL_MARGIN_Y + 2 * theme.TABLE_ITEM_PADDING_Y

_COLUMNS = ["Patient Name", "BHT", "Ward", "Doctor", "Discharge Date", "Created", "Modified", "Actions"]

# Column 0 (Patient Name) stretches; every other column needs an explicit
# width or Qt's ~100px default truncates doctor names/timestamps and
# squeezes the three Actions buttons (Full View/Print/Edit) into
# unreadable slivers.
#
# Widths below three separate hand-tuned-by-screenshot passes this
# project went through (clipped Actions buttons twice, a truncated
# header once) — computed instead, from real font metrics against the
# actual content each column holds, so a font/DPI change on the target
# laptop can't silently reintroduce the same clipping.
#
# QTableWidget::item's own QSS rule (app/theme.py: "padding: 6px
# {INPUT_PADDING_X}px") eats 2*INPUT_PADDING_X off every cell's usable
# width before content ever gets drawn — confirmed by measurement, not
# assumed: a cell widget set via setCellWidget() came out exactly
# 2*INPUT_PADDING_X (+ a rounding pixel) narrower than the column width
# that contained it. That's true for a text item eliding at the exact
# same point too, not just widget cells. Every computed width below has
# to add this back, plus a little genuine breathing room on top of it —
# a first pass that only added breathing room (no inset) exactly fit the
# sample text with zero slack and still clipped on real data.
_CELL_CONTENT_INSET = 2 * theme.INPUT_PADDING_X
_BREATHING_ROOM = 6
COLUMN_WIDTH_PADDING = _CELL_CONTENT_INSET + _BREATHING_ROOM

# BHT/Ward are plain digit strings (see docs/schema.md; test fixtures use
# 5-digit BHTs like "10178", 2-digit wards like "45") — these samples are
# deliberately a digit longer than typical real data as headroom, not a guess.
_BHT_SAMPLE = "999999"
_WARD_SAMPLE = "999"
# Fixed DD/MM/YYYY / DD/MM/YYYY HH:MM formats (app/printing/layout.format_date,
# _format_timestamp above) are fully reproducible from a literal sample —
# not a guess either, just the widest string that format can ever produce.
_DISCHARGE_DATE_SAMPLE = "31/12/2026"
_TIMESTAMP_SAMPLE = "31/12/2026 23:59"
# (label, QSS objectName) — one shared source for both the real cell
# (_build_actions_cell) and the width computation below, so a label
# change can't silently desync the two.
_ACTION_BUTTONS = (
    ("Full View", "SecondaryCompact"),
    ("Print", "SecondaryCompact"),
    ("Edit", "PrimaryCompact"),
)


def _compute_column_widths(table):
    """Deterministic widths for every fixed (non-stretching, non-Doctor)
    column, from the real font the table renders with — not a hardcoded
    pixel guess. Doctor stays a separate, documented judgment call
    (below): names are genuinely unbounded, so no sample is "the" widest one.
    """
    cell_metrics = QFontMetrics(table.font())
    header_metrics = QFontMetrics(table.horizontalHeader().font())

    def _sized(sample, header_text):
        return max(cell_metrics.horizontalAdvance(sample), header_metrics.horizontalAdvance(header_text)) + COLUMN_WIDTH_PADDING

    # Real, throwaway buttons (never shown, never parented into any
    # layout) rather than a hand-derived "text width + fixed chrome"
    # formula — measuring the actual sizeHint() can't drift out of sync
    # with what _build_actions_cell constructs.
    buttons_width = sum(_make_action_button(label, object_name).sizeHint().width()
                         for label, object_name in _ACTION_BUTTONS)
    actions_width = buttons_width
    actions_width += 2 * theme.SPACING_UNIT  # row_layout.setSpacing() between the three buttons
    actions_width += 2 * 4  # _build_actions_cell's own left/right QHBoxLayout margins
    actions_width += COLUMN_WIDTH_PADDING  # same QTableWidget::item inset applies to setCellWidget() cells too

    return {
        1: _sized(_BHT_SAMPLE, "BHT"),
        2: _sized(_WARD_SAMPLE, "Ward"),
        # Doctor: unbounded free text (doctor display names), not
        # computable from a sample the way every other column here is —
        # truncation is expected and acceptable, this is a judgment call.
        3: 90,
        4: _sized(_DISCHARGE_DATE_SAMPLE, "Discharge Date"),
        5: _sized(_TIMESTAMP_SAMPLE, "Created"),
        6: _sized(_TIMESTAMP_SAMPLE, "Modified"),
        7: actions_width,
    }


def _make_action_button(label, object_name):
    button = QPushButton(label)
    button.setObjectName(object_name)
    return button


def _format_timestamp(iso_timestamp):
    """Full ISO datetime -> 'DD/MM/YYYY HH:MM'. Blank -> ''."""
    if not iso_timestamp:
        return ""
    date_part, _, time_part = iso_timestamp.partition("T")
    y, m, d = date_part.split("-")
    hh_mm = time_part[:5]
    return f"{d}/{m}/{y} {hh_mm}"


class AdvancedSearchDialog(QDialog):
    def __init__(self, conn, main_window, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._main_window = main_window
        self.setWindowTitle("Advanced Search")
        # Clamped to the actual screen (app/util/screen.py) — same
        # off-screen-bottom-row risk as Print Preview/Full View on the
        # target 1366x768 Windows screen, just less severe here since
        # only the table area shrinks, not a button row.
        self.resize(*clamped_dialog_size(self, 1260, 700))

        self._doctors_by_id = {d.id: d for d in doctors_db.list_all(self._conn)}

        self._name_debounce = QTimer(self)
        self._name_debounce.setSingleShot(True)
        self._name_debounce.timeout.connect(self._run_search)

        root = QVBoxLayout(self)
        root.setContentsMargins(
            theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING
        )
        root.setSpacing(theme.FIELD_GAP)

        root.addLayout(self._build_filter_row())

        self._status_label = QLabel("")
        self._status_label.setObjectName("Muted")
        self._status_label.setVisible(False)
        root.addWidget(self._status_label)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_results_table())
        splitter.addWidget(self._build_view_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        # setStretchFactor alone only governs how *resize* deltas are
        # divided — QSplitter's initial layout still splits evenly (or
        # worse, gives the second widget most of the space) unless the
        # starting sizes are set explicitly.
        splitter.setSizes([1020, 200])
        root.addWidget(splitter, stretch=1)

        self._run_search()

    # --- Filters --------------------------------------------------------

    def _build_filter_row(self):
        # Grouped by kind rather than one flat row: identity filters
        # (who) on top, the broad keyword search (what) on its own row
        # since it's a different kind of match, then date ranges (when)
        # together, then the submit actions on their own row so they
        # don't compete for space with the last input field.
        #
        # Every row uses the same building block — an QHBoxLayout with an
        # explicit addStretch() collecting leftover space at the right
        # edge — so rows stay visually consistent instead of some
        # stretching edge-to-edge and others floating half-width with a
        # detached button row underneath (what made the previous version
        # read as unorganized). Search/Clear live at the end of the top
        # (widest) row, not stranded on their own line below a mostly
        # empty date row.
        container = QVBoxLayout()
        container.setSpacing(theme.FIELD_GAP)

        top_row = QHBoxLayout()
        top_row.setSpacing(theme.FIELD_GAP)
        self.patient_name_input = QLineEdit()
        self.patient_name_input.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        # Live filtering, debounced — matches the old inline patient-list
        # search's own debounce (docs/decisions.md). Keyword/dates below
        # deliberately get no such wiring; only Search applies those.
        self.patient_name_input.textChanged.connect(lambda _: self._name_debounce.start(NAME_DEBOUNCE_MS))
        top_row.addWidget(LabeledField("Patient Name / BHT", self.patient_name_input), stretch=1)

        self.doctor_picker = QComboBox()
        self.doctor_picker.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.doctor_picker.setFixedWidth(240)
        self.doctor_picker.addItem(ALL_DOCTORS_LABEL)
        self._doctor_ids_by_index = [None]
        for doctor in self._doctors_by_id.values():
            self.doctor_picker.addItem(doctor.display_name)
            self._doctor_ids_by_index.append(doctor.id)
        # Connected after populating — addItem() itself fires
        # currentIndexChanged once as the index moves from -1 to 0, which
        # would otherwise fire a premature search.
        self.doctor_picker.currentIndexChanged.connect(self._run_search)
        top_row.addWidget(LabeledField("Doctor", self.doctor_picker))

        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("Primary")
        self.search_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.search_button.clicked.connect(self._run_search)
        clear_button = QPushButton("Clear filters")
        clear_button.setObjectName("Secondary")
        clear_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        clear_button.clicked.connect(self._clear_filters)
        top_row.addWidget(self._button_row_aligned_with_inputs(self.search_button, clear_button))
        container.addLayout(top_row)

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("Search clinical notes...")
        self.keyword_input.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        container.addWidget(LabeledField("Keyword", self.keyword_input))

        dates_row = QHBoxLayout()
        dates_row.setSpacing(theme.FIELD_GAP)

        self.created_from = DateField()
        self.created_to = DateField()
        dates_row.addWidget(LabeledField("Created", self._date_range_widget(self.created_from, self.created_to)))

        self.modified_from = DateField()
        self.modified_to = DateField()
        dates_row.addWidget(LabeledField("Modified", self._date_range_widget(self.modified_from, self.modified_to)))
        dates_row.addStretch()
        container.addLayout(dates_row)

        return container

    @staticmethod
    def _button_row_aligned_with_inputs(*buttons):
        """Wraps buttons with a blank spacer label above them, matching
        LabeledField's own label-then-input structure — without it, a
        bare button sitting next to a LabeledField in the same row
        floats noticeably higher than the labeled inputs beside it."""
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        spacer_label = QLabel(" ")
        spacer_label.setObjectName("Muted")
        layout.addWidget(spacer_label)
        button_row = QHBoxLayout()
        button_row.setSpacing(theme.FIELD_GAP)
        for button in buttons:
            button_row.addWidget(button)
        layout.addLayout(button_row)
        return wrap

    @staticmethod
    def _date_range_widget(from_field, to_field):
        """A tight [from] to [to] group — explicit small spacing, no
        stretch, so the two DateFields and the 'to' label sit close
        together instead of spreading across whatever width their parent
        layout happens to grant them."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)  # else Qt's default margins push the boxes down from their label and right of it
        row.setSpacing(theme.SPACING_UNIT * 2)
        row.addWidget(from_field)
        to_label = QLabel("to")
        to_label.setObjectName("Muted")
        row.addWidget(to_label, alignment=Qt.AlignVCenter)
        row.addWidget(to_field)
        wrap = QWidget()
        wrap.setLayout(row)
        return wrap

    def _clear_filters(self):
        # Resetting patient_name_input/doctor_picker below fires their own
        # live-search signals (textChanged arms the debounce timer;
        # currentIndexChanged fires immediately) — blocked here so this
        # method's own single _run_search() call at the end is the only
        # one that actually runs, and no stray armed debounce timer is
        # left behind to fire a redundant search later.
        self._name_debounce.stop()
        self.patient_name_input.blockSignals(True)
        self.patient_name_input.clear()
        self.patient_name_input.blockSignals(False)

        self.doctor_picker.blockSignals(True)
        self.doctor_picker.setCurrentIndex(0)
        self.doctor_picker.blockSignals(False)

        self.keyword_input.clear()
        for field in (self.created_from, self.created_to, self.modified_from, self.modified_to):
            field.set_iso("")
        self._run_search()

    # --- Results table ----------------------------------------------------

    def _build_results_table(self):
        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Patient Name absorbs remaining space
        # QHeaderView.setMinimumSectionSize is deliberately NOT used here
        # to floor Patient Name's width — it applies to every section, not
        # just the Stretch one, so it would just inflate every Fixed
        # column up to the same floor instead of protecting this one.
        # Patient Name gets enough room by construction instead: the
        # splitter/dialog sizing below (docs/decisions.md) leaves headroom
        # beyond what the Fixed columns actually need.
        for col in range(1, len(_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
        # Fixed widths for every non-stretching column — left to Qt's
        # default (~100px), long doctor names/timestamps truncate and the
        # Actions buttons squeeze down to unreadable slivers.
        for col, width in _compute_column_widths(self.table).items():
            self.table.setColumnWidth(col, width)

        self.table.itemSelectionChanged.connect(self._on_row_selected)
        return self.table

    def _run_search(self):
        # Fully synchronous (no QThread anywhere in this codebase, and
        # CLAUDE.md rules out async generally) — the processEvents() pump
        # is what actually gets "Searching…" painted before the
        # (blocking) query runs, the standard trick for visible-but-
        # synchronous work in Qt.
        self.search_button.setEnabled(False)
        self._status_label.setText("Searching…")
        self._status_label.setVisible(True)
        QApplication.processEvents()
        try:
            doctor_id = self._doctor_ids_by_index[self.doctor_picker.currentIndex()]
            results = summaries.advanced_search(
                self._conn,
                patient_name=self.patient_name_input.text().strip(),
                keyword=self.keyword_input.text().strip(),
                doctor_id=doctor_id,
                created_from=self.created_from.get_iso() or None,
                created_to=self.created_to.get_iso() or None,
                modified_from=self.modified_from.get_iso() or None,
                modified_to=self.modified_to.get_iso() or None,
            )
            self._render_results(results)
        finally:
            self._status_label.setVisible(False)
            self.search_button.setEnabled(True)

    def _render_results(self, results):
        # setRowCount()/setItem() below fire itemSelectionChanged as Qt's
        # internal selection state shifts around — blocked so that churn
        # doesn't flicker the view panel through stale/empty rows before
        # the table settles.
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(results))
        for row_index, row in enumerate(results):
            doctor = self._doctors_by_id.get(row["created_by"])
            doctor_name = doctor.display_name if doctor else ""

            name_item = QTableWidgetItem(row["patient_name"] or "(unnamed)")
            name_item.setData(Qt.UserRole, row["id"])
            self.table.setItem(row_index, 0, name_item)
            self.table.setItem(row_index, 1, QTableWidgetItem(row["bht_number"]))
            self.table.setItem(row_index, 2, QTableWidgetItem(row["ward"]))
            self.table.setItem(row_index, 3, QTableWidgetItem(doctor_name))
            self.table.setItem(row_index, 4, QTableWidgetItem(print_layout.format_date(row["date_discharge"])))
            self.table.setItem(row_index, 5, QTableWidgetItem(_format_timestamp(row["created_at"])))
            self.table.setItem(row_index, 6, QTableWidgetItem(_format_timestamp(row["updated_at"])))
            self.table.setCellWidget(row_index, 7, self._build_actions_cell(row["id"]))
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)
        self._clear_view_panel(show_placeholder=True)

    def _build_actions_cell(self, summary_id):
        cell = QWidget()
        row_layout = QHBoxLayout(cell)
        row_layout.setContentsMargins(4, _ACTIONS_CELL_MARGIN_Y, 4, _ACTIONS_CELL_MARGIN_Y)
        row_layout.setSpacing(theme.SPACING_UNIT)

        # Built from the same _ACTION_BUTTONS table _compute_column_widths
        # measures against, so a label change can't silently make the
        # column too narrow for what's actually rendered here. Explicit
        # fixed height, not the buttons' natural QSS sizeHint — that's
        # what actually fits them inside the table's row height
        # (_ROW_HEIGHT above) without getting vertically clipped
        # (docs/decisions.md).
        handlers = {
            "Full View": lambda: self._on_full_view(summary_id),
            "Print": lambda: self._on_print(summary_id),
            "Edit": lambda: self._on_edit(summary_id),
        }
        for label, object_name in _ACTION_BUTTONS:
            button = _make_action_button(label, object_name)
            button.setFixedHeight(ACTION_BUTTON_HEIGHT)
            button.clicked.connect(handlers[label])
            row_layout.addWidget(button)

        return cell

    # --- View panel ---------------------------------------------------

    def _build_view_panel(self):
        self._view_scroll = ScrollFrame()

        self._view_placeholder = QLabel("Click a row to see the full record here.")
        self._view_placeholder.setObjectName("Muted")
        self._view_placeholder.setWordWrap(True)
        self._view_scroll.add_widget(self._view_placeholder)

        return self._view_scroll

    def _clear_view_panel(self, show_placeholder=False):
        for i in reversed(range(self._view_scroll.body_layout.count() - 1)):
            item = self._view_scroll.body_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        if show_placeholder:
            self._view_scroll.add_widget(self._view_placeholder)

    def _render_view_panel(self, summary, investigations, attachments):
        self._clear_view_panel()
        populate_summary_view(self._view_scroll, summary, investigations, self._doctors_by_id, attachments)

    # --- Row actions ----------------------------------------------------

    def _on_row_selected(self):
        """Clicking a row shows its full record in the quick-view panel
        directly — no separate View button (docs/decisions.md)."""
        row = self.table.currentRow()
        if row < 0:
            return
        name_item = self.table.item(row, 0)
        if name_item is None:
            return
        self._on_view(name_item.data(Qt.UserRole))

    def _on_view(self, summary_id):
        summary = summaries.get(self._conn, summary_id)
        investigations = summaries.list_investigations(self._conn, summary_id)
        attachments = attachments_db.list_for_summary(self._conn, summary_id)
        self._render_view_panel(summary, investigations, attachments)

    def _on_full_view(self, summary_id):
        summary = summaries.get(self._conn, summary_id)
        investigations = summaries.list_investigations(self._conn, summary_id)
        attachments = attachments_db.list_for_summary(self._conn, summary_id)
        dialog = SummaryFullViewDialog(summary, investigations, self._doctors_by_id, attachments, self)
        dialog.exec()

    def _on_print(self, summary_id):
        # Same "currently selected header doctor signs" rule as the
        # editor's own Print button (docs/decisions.md) — not whichever
        # doctor created this particular row.
        doctor_id = self._main_window.selected_doctor.id
        # ignore_cleanup_errors: see app/ui/editor.py's _on_print — the
        # external app Windows hands the "print" verb to can still hold
        # the PDF open when this exits (WinError 32); best-effort cleanup,
        # not a reason to interrupt the doctor closing the dialog.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            dialog = PrintPreviewDialog(self._conn, summary_id, tmp_dir, doctor_id, self)
            dialog.exec()

    def _on_edit(self, summary_id):
        self._main_window.editor.load_summary(summary_id)
        self._main_window.patient_list.select(summary_id)
        self.accept()
