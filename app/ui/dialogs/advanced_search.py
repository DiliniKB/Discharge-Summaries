"""Advanced Search dialog — replaces the patient list's old inline search
box entirely (docs/decisions.md). Filters combine (patient name, broad
keyword, doctor, created/modified date ranges); results are a sortable
table. Selecting a row updates the read-only view panel automatically —
no separate View button (docs/decisions.md); Print/Edit remain explicit
per-row actions since those are real, consequential operations.

The view panel is a built-from-scratch read-only field layout, not a
re-rendered PDF (docs/decisions.md) — instant on selection, no per-click
temp-file render cost.
"""

import tempfile

from PySide6.QtCore import Qt
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
from app.db import doctors as doctors_db
from app.db import summaries
from app.printing import layout as print_layout
from app.ui.dialogs.print_preview import PrintPreviewDialog
from app.ui.widgets.datefield import DateField
from app.ui.widgets.labeled import LabeledField
from app.ui.widgets.scrollframe import ScrollFrame

ALL_DOCTORS_LABEL = "All doctors"

_COLUMNS = ["Patient Name", "BHT", "Ward", "Doctor", "Discharge Date", "Created", "Modified", "Actions"]
# Column 0 (Patient Name) stretches; every other column needs an explicit
# width or Qt's ~100px default truncates doctor names/timestamps and
# squeezes the three Actions buttons into unreadable slivers.
_COLUMN_WIDTHS = {1: 65, 2: 60, 3: 145, 4: 110, 5: 110, 6: 110, 7: 150}

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
        self.resize(1200, 700)

        self._doctors_by_id = {d.id: d for d in doctors_db.list_all(self._conn)}

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
        splitter.setSizes([860, 280])
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
        top_row.addWidget(LabeledField("Patient Name / BHT", self.patient_name_input), stretch=1)

        self.doctor_picker = QComboBox()
        self.doctor_picker.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.doctor_picker.setFixedWidth(240)
        self.doctor_picker.addItem(ALL_DOCTORS_LABEL)
        self._doctor_ids_by_index = [None]
        for doctor in self._doctors_by_id.values():
            self.doctor_picker.addItem(doctor.display_name)
            self._doctor_ids_by_index.append(doctor.id)
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
        self.patient_name_input.clear()
        self.doctor_picker.setCurrentIndex(0)
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
        self.table.verticalHeader().setDefaultSectionSize(theme.INPUT_HEIGHT_PX)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Patient Name absorbs remaining space
        for col in range(1, len(_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
        # Fixed widths for every non-stretching column — left to Qt's
        # default (~100px), long doctor names/timestamps truncate and the
        # Actions buttons squeeze down to unreadable slivers.
        for col, width in _COLUMN_WIDTHS.items():
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
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(theme.SPACING_UNIT)

        print_button = QPushButton("Print")
        print_button.setObjectName("SecondaryCompact")
        print_button.clicked.connect(lambda: self._on_print(summary_id))
        row_layout.addWidget(print_button)

        edit_button = QPushButton("Edit")
        edit_button.setObjectName("PrimaryCompact")
        edit_button.clicked.connect(lambda: self._on_edit(summary_id))
        row_layout.addWidget(edit_button)

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

    def _add_view_field(self, label, value):
        """Omits the row entirely when blank — a doctor scanning a record
        wants to see what's actually documented, not a wall of '—'s for
        everything nobody filled in. Mirrors the same omission rule
        app/printing/layout.py already applies to the printed card."""
        if not value:
            return
        value_label = QLabel(str(value))
        value_label.setWordWrap(True)
        self._view_scroll.add_widget(LabeledField(label, value_label))

    def _add_view_section_header(self, heading):
        header = QLabel(heading)
        header.setObjectName("SectionHeader")
        self._view_scroll.add_widget(header)

    def _render_view_panel(self, summary, investigations):
        self._clear_view_panel()

        # Identity header, styled like the editor's own breadcrumb — the
        # first thing a doctor scanning search results needs is "is this
        # the right patient?", not a field labelled "Patient Name" buried
        # in a list.
        name_label = QLabel(summary.patient_name or "(unnamed)")
        name_label.setObjectName("PatientName")
        name_label.setWordWrap(True)
        self._view_scroll.add_widget(name_label)

        age_sex = f"{summary.age}{(summary.sex or '')[:1]}" if summary.age else (summary.sex or "")
        identity_bits = [b for b in [age_sex, f"BHT {summary.bht_number or '—'}"] if b]
        if summary.ward:
            identity_bits.append(f"Ward {summary.ward}")
        identity_label = QLabel(" · ".join(identity_bits))
        identity_label.setObjectName("Muted")
        self._view_scroll.add_widget(identity_label)

        # Who touched this record and when — directly relevant here since
        # the whole dialog exists to search across doctors.
        attribution_bits = []
        creator = self._doctors_by_id.get(summary.created_by)
        if creator:
            attribution_bits.append(f"Created by {creator.name} · {_format_timestamp(summary.created_at)}")
        last_editor = self._doctors_by_id.get(summary.last_edited_by)
        if last_editor:
            attribution_bits.append(f"Last edited by {last_editor.name} · {_format_timestamp(summary.updated_at)}")
        if attribution_bits:
            attribution_label = QLabel("   ·   ".join(attribution_bits))
            attribution_label.setObjectName("Muted")
            attribution_label.setWordWrap(True)
            self._view_scroll.add_widget(attribution_label)

        self._add_view_section_header("ADMISSION")
        self._add_view_field("Telephone", summary.telephone)
        self._add_view_field("Blood Group", summary.blood_group)
        self._add_view_field("Admission Date", print_layout.format_date(summary.date_admission))
        self._add_view_field("Surgery Date", print_layout.format_date(summary.date_surgery))
        self._add_view_field("Discharge Date", print_layout.format_date(summary.date_discharge))

        self._add_view_section_header("PROCEDURE")
        if summary.procedure_title:
            title_label = QLabel(summary.procedure_title.upper())
            title_label.setObjectName("ProcedureTitle")
            title_label.setWordWrap(True)
            self._view_scroll.add_widget(title_label)
        for label, attr, _preserve in print_layout.DETAIL_FIELDS:
            self._add_view_field(label, getattr(summary, attr))

        self._add_view_section_header("CLINICAL HISTORY")
        if print_layout.has_clinical_history(summary):
            for label, attr in print_layout.CLINICAL_HISTORY_FIELDS:
                self._add_view_field(label, getattr(summary, attr))
        else:
            empty_label = QLabel("No clinical history recorded.")
            empty_label.setObjectName("Muted")
            self._view_scroll.add_widget(empty_label)

        self._add_view_section_header("INVESTIGATIONS & MANAGEMENT")
        investigations_text = print_layout.format_investigations(investigations)
        if investigations_text or summary.management or summary.histology_report:
            self._add_view_field("Investigations", investigations_text)
            for label, attr, _preserve in print_layout.TAIL_FIELDS:
                self._add_view_field(label, getattr(summary, attr))
        else:
            empty_label = QLabel("No investigations or management recorded.")
            empty_label.setObjectName("Muted")
            self._view_scroll.add_widget(empty_label)

    # --- Row actions ----------------------------------------------------

    def _on_row_selected(self):
        """Clicking a row shows its full record in the view panel
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
        self._render_view_panel(summary, investigations)

    def _on_print(self, summary_id):
        # Same "currently selected header doctor signs" rule as the
        # editor's own Print button (docs/decisions.md) — not whichever
        # doctor created this particular row.
        doctor_id = self._main_window.selected_doctor.id
        with tempfile.TemporaryDirectory() as tmp_dir:
            dialog = PrintPreviewDialog(self._conn, summary_id, tmp_dir, doctor_id, self)
            dialog.exec()

    def _on_edit(self, summary_id):
        self._main_window.editor.load_summary(summary_id)
        self._main_window.patient_list.select(summary_id)
        self.accept()
