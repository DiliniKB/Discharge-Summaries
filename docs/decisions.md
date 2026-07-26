# Decisions

Non-obvious calls and the reasoning behind them. Read before re-litigating.

Most of these follow from one fact: the target machine has 4 GB of RAM and a **932 GB spinning hard disk running at 100% active time with 0 KB/s throughput**. The disk is the binding constraint, not the CPU or memory.

---

## Python over .NET WinForms

**Decision:** Python 3.11, PyInstaller.

.NET Framework 4.7.2 already ships with Windows 10 1809, so a .NET build would be a single exe with nothing to bundle — a better deployment story. Python was chosen for developer fluency and iteration speed on a small internal tool.

**What this costs:** a bundled runtime folder instead of one file, and slower cold start. Mitigated by `--onedir` (below). Verified acceptable on the target machine before committing.

**Revisit if:** startup exceeds ~4 seconds on the ward laptop, or deployment friction becomes a recurring support burden.

---

## PySide6 over Tkinter/ttk — and over PyQt6

**Decision:** PySide6 (Qt6) for the UI layer. Supersedes the original Tkinter/ttk choice below, which is kept for the record.

**Why the switch.** Tkinter's `ttk` widgets are flat by construction — no `border-radius`, no hover/pressed transitions, no shadows — and hitting even that ceiling meant hand-fixing real quirks along the way (a readonly `Combobox` pulling in the platform's default text-selection highlight was one; the scrollbar and button states were still unstyled when this decision was made). Evaluated and rejected before landing here:

- **Third-party ttk themes (Azure, sv_ttk)** — not real pip dependencies (vendored `.tcl` + ~125 PNG files pulled from GitHub), fixed palettes that don't map to this app's tokens, and the PNG-per-widget-state approach means many small file reads at every launch — the exact class of cost `--onedir` exists to avoid on this disk.
- **A local web app** (system browser or an embedded webview) — a browser tab alone commonly runs 200–500MB RAM, most or all of the ~1.6GB free on this machine. An embedded webview needs the WebView2 runtime, which Windows 10 1809 doesn't ship — bundling it adds ~150MB, downloading it on first run breaks offline-by-design entirely.
- **Electron** — same WebView2-class runtime and RAM cost as the webview option, worse.

Qt6 (via `QSS`, its CSS-like stylesheet system) gives real `border-radius`, hover/pressed states, and shadows without a browser or webview runtime — the thing ttk structurally can't do, without the cost the web-based options carry.

**PySide6, not PyQt6.** Same Qt6 engine underneath, same `QSS` styling, same widget set. PyQt6 is GPLv3-or-commercial with no free path for closed-source distribution — a real question for a hospital-internal tool, not one worth leaving unresolved. PySide6 is the Qt Company's own binding, LGPL, free for this use, functionally a drop-in equivalent.

**What this costs:**
- Qt6's DLLs typically add 60–100MB+ to the PyInstaller `--onedir` output versus Tkinter's near-zero (stdlib).
- A bare Qt window commonly runs 80–150MB RAM at idle versus Tkinter's ~20–40MB. Real, but nowhere near the 200–500MB+ a browser-based option costs — see rejected options above.
- Every piece of Tkinter-specific code and every Tkinter-specific line across `CLAUDE.md` and `docs/` needed rewriting, not patching. Done as part of this decision, not left half-migrated.
- `build.spec` needs the same exclusion discipline that trimmed `matplotlib`/`numpy`/`PyQt5` before — now trimming unused Qt6 modules (`QtNetwork`, `QtSql`, `QtQml`, `WebEngine`) so PyInstaller doesn't pull them in speculatively.

**Revisit if:** cold-start time on the actual ward laptop exceeds what `--onedir` bought back under Tkinter, once measured. This hasn't been verified on target hardware yet — flagged as an open item below.

---

## `--onedir`, never `--onefile`

**Decision:** PyInstaller `--onedir`. Ship a zipped folder.

`--onefile` produces a single exe, which is tidier to email. It also unpacks the entire Python runtime to `%TEMP%` on **every launch**. On an SSD that's a second. On this disk it's 5–10 seconds, every time, and it writes hundreds of megabytes to a drive that is already saturated.

A folder that staff unzip once is worth the loss of tidiness.

---

## SQLite over JSON files or a server database

**Decision:** SQLite via stdlib `sqlite3`.

- **JSON files** — no index. Search means reading every file on the slowest component in the machine. Rejected.
- **SQL Server Express / LocalDB / Postgres** — needs an installer, admin rights, and a running service consuming RAM. Wrong for a single-user offline ward PC. Rejected.
- **SQLite** — one file, no server, no install, in the standard library. Search, sort, and referential integrity for effectively zero operational cost.

---

## `synchronous = NORMAL`, not `FULL`

**Decision:** `PRAGMA synchronous = NORMAL` with WAL enabled.

`FULL` fsyncs on every commit. Combined with autosave-on-blur, that means a disk sync every time the user tabs between fields — on this drive, a visible stall.

With WAL, `NORMAL` risks losing only the most recent transaction in an OS-level crash. Given autosave fires constantly, the exposure is one field. Accepted.

---

## No login screen

**Decision:** doctor selected from a header dropdown. No passwords, no accounts.

The original mockup had a username/password sign-in. On a shared ward machine the realistic outcomes are a single shared password written on a sticky note, or a monthly interruption to reset someone's account. Neither adds security — anyone with physical access to an unlocked ward PC already has the data.

**What accountability actually requires** is knowing who signed each summary. That's `summaries.created_by` and `last_edited_by`, populated from the dropdown. A field on the record, not an auth system.

**Considered and shelved:** a single admin PIN gating only destructive actions (delete summary, edit doctor list, change settings). Cheap to add later if the unit asks. Not built now because nobody has asked.

**Revisit if:** the hospital produces a written IT policy requiring per-user authentication. That's a compliance decision, not an engineering one.

---

## Doctors are deactivated, never deleted

**Decision:** `doctors.active` flag; no delete path in the UI.

MOs rotate through the unit. Deleting one would orphan the foreign key on every summary they signed, so old cards would print without a signing officer — corrupting a clinical record to tidy a dropdown.

---

## Investigations as a structured table, not free text

**Decision:** `investigations` table, seven standard analytes pre-created per summary, plus ad-hoc rows.

The paper form has a single free-text box. In practice it always contains the same seven values (FBS, SCr, AST, Na, K, S Ca, Hb).

**Gains:** faster keyboard entry, fewer transcription errors, and the values become queryable if the unit later wants trends or out-of-range flagging. Prints identically to the current card, so nothing changes for the reader.

`value` is TEXT, not REAL — lab reports contain results like `<0.5` and `Not done`, and a numeric column would either reject or silently lose them.

---

## Blood group added as a field

**Decision:** new `blood_group` column, not present on the printed paper form.

On the sample card it was **handwritten into the margin**. That's the form telling you it's missing something people need.

---

## Templates insert text; they don't link

**Decision:** selecting a template copies its body into `procedure_steps`. No ongoing relationship.

A discharge summary is a record of what happened on a specific date. If templates were linked, editing the "Thyroid lobectomy" template in 2027 would silently rewrite the operative note on a 2026 record. That's record corruption.

---

## All paper fields kept, clinical history collapsed by default

**Decision:** every field from the green form exists. The six clinical-history fields sit in a section collapsed by default, with a `n of 6 filled` counter on the header.

On the sample card, Presenting Complaint, Past Medical History, Past Surgical History, Allergies, Examination, and Findings were all blank. Showing sixteen fields on a 1366×768 screen means either tiny inputs or heavy scrolling.

Collapsed-with-a-counter means nothing is hidden — the count tells you there's content — while the fields actually in use get the top of the screen.

---

## Light theme, not dark

**Decision:** light UI.

The original mockup was dark. Ward lighting is fluorescent, and staff hold the printed white card next to the screen to cross-check. Matching them reduces eye strain and makes verification easier.

---

## Print preview before printing

**Decision:** a modal preview rendering the actual generated PDF at true A4 proportions.

The current process has no preview — a misprint wastes a pre-printed form. The preview shows the real PDF, not an HTML approximation, so what's on screen is what leaves the printer.

---

## Print layout redesigned, not a pixel copy of the green form

**Decision:** same field order, same grey label bands, but empty fields collapse to thin rows instead of reserving half a page.

The paper form allocates fixed vertical space to fields that are usually blank. Reproducing that wastes paper and pushes content to a second page.

**Open:** this needs sign-off from the unit against a real paper card. If ward staff reject it, falling back to an exact reproduction is a change confined to `app/printing/layout.py`.

---

## Attachments on disk, paths in the database

**Decision:** files in `%APPDATA%\DischargeSummaries\attachments\<summary_id>\`; only metadata in SQLite.

Blobs bloat the database file, slowing every query and making the on-exit backup copy expensive. Imports capped at 5 MB with images resized — a 40 MB phone photo of a histology report is a realistic way to exhaust memory here.

**Resizing uses `QImage` (PySide6), not Pillow.** Pillow is present in this environment only as a transitive dependency (pulled in by ReportLab) — it isn't in `requirements.txt`, and `build.spec` explicitly curates what actually ships in the PyInstaller bundle. Relying on an undeclared transitive import would be fragile. `QImage(path)` doubles as the "is this actually a readable image" check: if it loads and exceeds 1600px on its longest side, scale it down; if `.isNull()`, treat the file as a non-image and copy it through unchanged (PDF, DOCX, etc.) rather than guessing from the file extension.

**Stored filenames are generated (`uuid4().hex` + extension), not the original name.** Two different attachments named `report.pdf` — a common case with scanned lab reports — would otherwise collide on disk. The original name is kept in the `filename` column for display; only the on-disk path is anonymised.

**Removing an attachment is a hard delete with no confirmation.** Unlike `summaries` (soft-deleted, 30-day purge, confirm-by-typing-the-name), the `attachments` table has no `deleted_at` column. A single attached file is a low-stakes, single-item action — closer to investigations' existing ad-hoc-row remove (also no confirmation) than to deleting a whole clinical record.

---

## Soft delete with a 30-day purge

**Decision:** `deleted_at` timestamp; rows purged by a maintenance pass after 30 days. Delete confirms with a single Yes/No click; Recently Deleted (below) is the actual undo path.

There is one database file on one unmirrored drive. A misclick should not be terminal.

**Editor announces Duplicate/Delete via signals, not a direct reference to PatientList.** `Editor` has never held a reference to `PatientList`/`MainWindow` — it emits `duplicated`/`deleted`, and `MainWindow` connects them to `patient_list.refresh()`/`select()`, the same shape as the existing `controller.saved -> patient_list.refresh` wiring. Reaching into `PatientList` directly from `Editor` would tie two widgets together that today only know about each other through `MainWindow`.

**Duplicate copies clinical text but not investigation values or attachments.** A duplicated record shares the same rationale as `docs/decisions.md`'s existing "templates insert text, don't link" entry — reusing narrative text (procedure steps, findings, indication) as a starting point is a convenience. Reusing lab values or attached files would mean a new record silently carrying another patient's concrete clinical data forward, which is a safety risk, not a convenience — `create()` already reseeds the 7 blank standard investigation rows for any new record, duplicate included.

---

## Recently Deleted replaces typed-name delete confirmation

**Decision:** Delete confirms with a single `QMessageBox.question` Yes/No click. A new header action, Recently Deleted (`app/ui/dialogs/recently_deleted.py`), lists every soft-deleted summary with a Restore button — that's the real safety net now, not the confirmation step.

The typed-name confirmation (`ConfirmDeleteDialog`) existed because a soft delete, at the time, had no way back except editing the database directly. Once Restore exists, a misclick is a two-click recovery (open Recently Deleted, click Restore) rather than something the confirmation dialog had to prevent outright — the heavier friction stopped earning its keep, so it was removed rather than kept as a redundant extra step. `ConfirmDeleteDialog` was deleted outright, not left as dead code.

**Recently Deleted shows everything ever soft-deleted, not just the last 30 days.** No purge job exists in the code yet — filtering the view to 30 days would hide records that still physically exist in the database and would otherwise become unreachable through the UI entirely. Showing everything matches actual current behavior instead of pretending a purge runs. Revisit this once a real purge job exists.

**Header button, not tied to the open record.** Restoring isn't an action on "this patient" — it's a standalone maintenance action, same reasoning as Settings living in the header rather than the list pane or editor.

---

## Print signature follows the currently selected doctor, not the record's creator

**Decision:** `PrintPreviewDialog` now takes an explicit `doctor_id` parameter — the caller (Editor's Print button, Advanced Search's per-row Print) always passes whichever doctor is currently selected in the header (`controller.current_doctor_id` / `main_window.selected_doctor.id`). It no longer derives the signature from `summary.created_by`.

A different doctor can create a record than the one who actually discharges and signs it — the doctor physically at the PC, selected in the header at the moment of printing, is the one putting their name on the printed card, not whoever happened to start the digital entry. `created_by`/`last_edited_by` remain the DB audit trail (who touched the record and when); the printed signature is a separate, deliberately-current-moment decision now.

---

## Input text and field height reduced (16px/40px -> 14px/34px)

**Decision:** `theme.SIZE_INPUT` 16 -> 14, `theme.INPUT_HEIGHT_PX` 40 -> 34.

The original spec sizes were spacious enough that, at the target 1366×768 resolution, only Patient & Admission plus the start of Procedure fit before scrolling — for a form doctors are filling out quickly between patients, that read as more work than it needed to be. Confirmed by comparing real rendered screenshots at both sizes before changing anything: the smaller size fits meaningfully more of the form in the same viewport (all of Patient & Admission plus all of Procedure's short fields) while staying clearly legible. Field labels (13px) and the procedure-title/patient-name emphasis sizes were left alone — only the base input size and the box height around it changed.

---

## Advanced Search's loading state is synchronous, not threaded

**Decision:** disable the Search button and show a "Searching…" label, with a single `QApplication.processEvents()` call before the (blocking) query runs.

No `QThread`/async infrastructure exists anywhere in this codebase, and CLAUDE.md rules out async generally for this project. Rather than introduce threading for one dialog, this uses the standard synchronous-Qt trick: pump the event loop once so the "Searching…" state actually paints before the blocking call, then run the query in place. Barely visible on this dev machine's SSD; the whole point is the target laptop's HDD, where `advanced_search()`'s keyword filter (an accepted unindexed scan — see the Advanced Search entry above) is more likely to take long enough to matter.

---

## Patient Name and Doctor filter live; Keyword and date ranges don't

**Decision:** `patient_name_input` debounces 150ms (same debounce the old inline patient-list search used); `doctor_picker` re-queries immediately on selection (already a discrete, deliberate action — same reasoning as Sex/Blood Group saving immediately elsewhere). Keyword and the four date fields get no signal wiring at all — only clicking Search (or Clear, which calls the same method) applies those.

The split follows directly from what each filter actually costs: name/BHT hits two indexed columns (`idx_summaries_name`/`idx_summaries_bht`), cheap enough to re-run on every keystroke. Keyword is a broad `OR`-joined `LIKE` scan across eleven unindexed clinical-text columns, and the date ranges wrap `created_at`/`updated_at` in `date(...)`, which defeats any index — both are the "accepted unindexed scan, but only as an explicit action" tradeoff already documented above. Firing either on every keystroke would turn an accepted occasional cost into a per-character one.

**Clearing filters blocks signals during the reset**, not just at the end. `patient_name_input.clear()`/`doctor_picker.setCurrentIndex(0)` each fire their own live-search wiring — without blocking, `_clear_filters()` would trigger two redundant searches back to back, and leave the name debounce timer armed to fire a *third*, stray one later (the same class of bug this codebase has hit twice before — see `tests/test_editor.py`'s and `EditorController.clear()`'s history).

---

## Full View has its own visual design, not a bigger copy of the quick-view panel

**Decision (superseded once, see below):** the rendering logic that used to live directly in `AdvancedSearchDialog` (`_render_view_panel`/`_add_view_field`/`_add_view_section_header`) moved to a standalone function, `populate_summary_view()` in `app/ui/widgets/summary_view.py`, so the inline quick-view panel and the first version of `SummaryFullViewDialog` shared one implementation.

That held only as long as Full View was literally "the same thing, bigger." Once the ask became "more catchy, highlight important stuff, organized," the two views genuinely diverged in purpose — quick-view stays a flat, compact, instant glance for a narrow sidebar; Full View is now a dedicated detail screen with its own layout: a tinted hero header, bordered card sections (mirroring the editor's own section styling), Admission's short fields laid out side by side instead of stacked, and a red allergy alert box that's deliberately the loudest thing on the page — allergy status is the one field on a discharge summary that's genuinely safety-critical to not miss, everything else earns equal visual weight. `SummaryFullViewDialog` now builds this directly rather than calling `populate_summary_view()`; `app/ui/widgets/summary_view.py` still backs the quick-view panel alone. Two real, differently-purposed views are allowed to look different — the earlier "share everything" decision was right for what Full View was at the time, not a rule to preserve past the point it stopped fitting.

**New tokens added, not one-off colors inline:** `theme.DANGER_TINT` pairs with the existing `DANGER` token the same way `PRIMARY_TINT` already pairs with `PRIMARY` — the allergy alert's background follows the established tinting pattern rather than introducing an unrelated color.

---

## Action buttons get an explicit fixed height, not their natural QSS sizeHint

**Decision:** `Full View`/`Print`/`Edit` in the Advanced Search results table are `setFixedHeight(26)`.

Real bug, confirmed by screenshot: `theme.INPUT_HEIGHT_PX` (used for the table's row height) dropped from 40 to 34 in the form-density change, but nothing re-checked whether the action buttons' natural rendered height still fit inside that — it didn't, and the button text was vertically clipped top and bottom. An explicit height that's verified to fit is more robust than relying on a QSS sizeHint that depends on tokens changing elsewhere for unrelated reasons.

---

## Print signature — Save button copies, doesn't re-render

**Decision:** Print Preview's new Save button copies the already-rendered `pdf_path` to a chosen location via `shutil.copy2`; it doesn't call `render_summary()` again, and it doesn't `accept()`/`reject()` the dialog.

The PDF is already sitting on disk the moment the dialog opens (CLAUDE.md: "generate PDFs to a temp file") — there's nothing to regenerate. Not closing the dialog on Save matters because Save and Print aren't mutually exclusive: a doctor might save a copy and then still print, or save without printing at all (e.g. to email a colleague later). Print's own `accept()` on success stays as-is — printing is the terminal action that closes the modal; saving a copy isn't.

---

## Temp PDF cleanup doesn't block on a still-open external viewer (WinError 32)

**Decision:** both places that wrap a `PrintPreviewDialog` in `tempfile.TemporaryDirectory()` (`app/ui/editor.py`'s `_on_print`, `app/ui/dialogs/advanced_search.py`'s `_on_print`) now pass `ignore_cleanup_errors=True`.

`app/printing/printer.py` hands the rendered PDF to `os.startfile(path, "print")` — the OS's own default handler (e.g. the system PDF viewer) opens it to actually print, and can still hold the file open by the time the doctor closes the Print Preview dialog and the `with` block tries to delete the temp directory. Windows (unlike POSIX) refuses to delete an open file, raising `WinError 32`. That's the external viewer's own timing, not a bug in this app and not something it can force closed — the fix is to make the best-effort temp-file cleanup tolerate that instead of raising and breaking the "close the print window" action a doctor is mid-task on. Confirmed reproducible: the crash was reported closing Print Preview right after Print, i.e. exactly this race.

---

## A button click doesn't reliably blur a still-focused field — commit before reading state

**Decision:** `Editor._commit_focused_field()` force-blurs (`clearFocus()`) whatever field currently has focus, scoped to widgets inside the Editor. Called before `flush()` in `_on_save`, `_on_print`, `_on_duplicate`, and before `controller.load()` in `load_summary()` (switching to a different record).

Found by testing: clicking Save (or Print, or a different patient card) right after typing into a field, without first tabbing or clicking elsewhere, does not reliably move keyboard focus away from a `QLineEdit` on this platform (buttons are click-only for focus purposes on macOS's Cocoa HI guideline, and this codebase can't assume Windows behaves differently without a from-source verification of its own). Without a blur, `editingFinished` never fires, so `controller.set_field()`/`set_investigation()` never even sees the just-typed value — `flush()` then has nothing pending to write, and the record silently ends up missing whatever was still focused, while the UI (pre-fix) still claimed "Saved". This is a real data-loss bug, not just a cosmetic one, and it's also why the abnormal-lab-value styling (`app/ui/sections/investigations.py`) looked "stuck" — that recalculation hangs off the same `editingFinished` signal.

**Related:** `Editor._on_save()` now always calls `_on_saved()` (updates the "✓ Saved" label) after `flush()`, not only when `flush()` found something pending. `flush()` only emits its `saved` signal when it actually wrote something — right after an autosave already flushed the same edit, or on a freshly-created card nothing's been typed into yet, clicking Save found nothing pending and left the label stuck on "Not saved" even though the record was fully persisted. An explicit Save click is a confirmation of the current state either way.

---

## Paginated list queries

**Decision:** `LIMIT 50` on the list pane, full record loaded only on selection.

With a few hundred summaries, loading everything would work fine today and degrade badly by year three — on the machine least able to absorb it. Not premature optimisation on this hardware.

---

## Advanced Search replaces the inline search box entirely

**Decision:** the patient list pane's old debounced search box is gone. Finding a record now goes through a dedicated Advanced Search modal (`app/ui/dialogs/advanced_search.py`) with combinable filters — Patient Name/BHT, Doctor, Keyword, Created date range, Modified date range — a sortable results table, and per-row View/Print/Edit actions plus a read-only view panel.

**Why replace rather than add alongside.** The requested filter set (doctor, date ranges, keyword) doesn't fit in a 280px-wide sidebar alongside New Card and the card list — it needs real width for a table and a view panel. Rather than a second, parallel search surface, one clear entry point (the Advanced Search button, also `Ctrl+F`) avoids the user having to remember which box does what. The left pane keeps its plain, unfiltered, discharge-date-ordered browsing list for the common case of "what's here right now."

**Patient Name/BHT is one field, not two.** The old search matched name or BHT together; folding both into one filter field keeps that lookup working (BHT is the ward's primary identifier) without adding a field beyond what was actually requested.

**Doctor filter checks `created_by` OR `last_edited_by`.** A doctor searching for "their" cases wants ones they started as well as ones they most recently touched — checking only one field would hide half of what they're looking for.

**Keyword searches broad clinical text, not name/BHT.** Patient Name/BHT already has its own field; keyword instead covers procedure_title, indication, procedure_steps, presenting_complaint, past_medical_history, past_surgical_history, allergies, examination, findings, management, and histology_report — "find the summary that mentioned X."

**Date ranges accept an unindexed scan.** `date(created_at) BETWEEN ? AND ?` can't use a plain index (the function wrapper prevents it). Accepted because Advanced Search is an explicit, infrequent action (a button click) rather than the per-keystroke list-pane path CLAUDE.md's I/O rules are really aimed at. The doctor filter's `created_by`/`last_edited_by` columns *do* get a new index (migration `002_doctor_indexes.sql`) since that's a plain equality/OR comparison an index actually helps.

**View panel is a built-from-scratch read-only layout, not a re-rendered PDF.** `PrintPreviewDialog` already renders the real PDF and could technically be embedded per-row, but that means writing a temp file and invoking ReportLab on every single row selection — slow, and wasteful for what's meant to be a quick glance before deciding whether to Print or Edit. A plain read-only field layout, grouped the same way as the editor's own sections, is instant.

**Selecting a row shows the record — no separate View button.** Looking at a record is non-destructive and instant (the view panel is a plain read-only layout, not a render), so making the user click an extra button first added a step without protecting against anything. Print and Edit stayed as explicit buttons: both are real, consequential actions — Print produces a physical page, Edit switches what the main window has open — so they deserve a deliberate click rather than firing on selection.

**View panel leads with identity, hides blanks, and shows investigation values.** First pass just dumped every field in a flat list, including blank ones shown as "—" — accurate but not how a doctor actually scans a record. Reworked to: an identity line up top (name, age/sex, BHT, ward) so "is this the right patient?" is answered in one glance, not by reading a field labelled "Patient Name" partway down a list; doctor attribution (created/last edited by, with timestamps) since this dialog exists specifically to search across doctors; blank fields omitted entirely rather than shown as empty, reusing the same "omit if nothing to show" rule `app/printing/layout.py` already applies to the printed card (`has_clinical_history`, `format_investigations`, `DETAIL_FIELDS`/`CLINICAL_HISTORY_FIELDS`/`TAIL_FIELDS`) rather than re-deriving it; and investigation values shown inline, which the first pass omitted entirely — a real gap, since lab results are exactly what a doctor scanning a record wants to see.

**Attachments were missing from both view panel and Full View entirely — added as filename + size + Open.** Genuine gap: a doctor searching a record has no way to know it even has a wound photo or a pathology PDF attached without opening it in the editor first. Both `populate_summary_view` (quick-view panel) and `SummaryFullViewDialog` now take an `attachments` list (fetched via `attachments_db.list_for_summary`) and append an ATTACHMENTS section listing `filename · size` + an Open button per file — same read-only, glance-first shape as everything else in these views. Omitted entirely (not a muted "none" line) when there are none, since most records won't have any and a near-permanent empty section would be noise.

---

## Previewing an attachment opens it in the OS's default viewer — no in-app preview

**Decision:** `app.util.attachments.open_attachment_file(stored_relative_path)` calls `os.startfile(path)`, handing the file to whatever the OS has set as the default handler for its type (Photos, Edge, Acrobat, etc). Wired to an "Open" button on every attachment row — the editor's own `AttachmentsSection`, Advanced Search's quick-view panel, and the Full View dialog all use it (the latter two reuse `app/ui/widgets/summary_view.py`'s `_build_attachment_row`, so the open-file wiring exists in exactly one place).

Rejected an in-app image preview (thumbnail + click-to-enlarge dialog): it only helps images, still needs the "open externally" fallback for PDFs/DOCX anyway, and is real UI to build and maintain (thumbnail rendering, memory for decoded images on a 4GB machine) for a need `os.startfile` already covers with one line. Same "warn, don't block" shape as the rest of this app: `open_attachment_file` raises `AttachmentMissingError` (file no longer on disk) or `AttachmentOpenUnsupportedError` (dev/test runs on non-Windows, mirroring `printer.py`'s `PrintUnsupportedError`) rather than crashing — every caller catches both and shows an inline message instead.

**Filter rows all use the same layout pattern; Search/Clear attach to the top row.** An earlier pass fixed cramped date-field spacing but left the panel feeling disorganized: the identity and keyword rows stretched edge-to-edge while the date row stayed half-width, and Search/Clear sat stranded on their own line below a mostly-empty row. Every row now uses the same `QHBoxLayout` + trailing `addStretch()` pattern for consistency, and the buttons moved onto the top (widest) row instead of floating below — a small `_button_row_aligned_with_inputs()` helper gives them a blank spacer label matching `LabeledField`'s own label-then-input structure, so they sit level with the inputs beside them rather than floating higher.

---

## Abnormal lab flagging, date-order warning, computed column widths

**Decision:** three follow-ups from a "how could this improve, mathematically" review. All three warn, never block — same precedent as duplicate BHT.

**Abnormal lab styling (`app/util/lab_ranges.py`, `app/ui/sections/investigations.py`).** `NORMAL_RANGES` holds a general adult reference range per standard analyte; `is_abnormal(label, value_text)` returns `True` only when the value parses as a plain float and falls outside that range — non-numeric lab text ("<0.5", "Not done") and unknown labels are never flagged, for the same reason `investigations.value` is TEXT rather than REAL. An out-of-range field gets a red border/tint (`QLineEdit[abnormal="true"]` in `app/theme.py`) on blur and again when a saved record is reopened. **These are general adult ranges, not a diagnostic tool** — a prompt to double-check, not a claim of clinical precision. Hb in particular is genuinely sex-dependent in practice; one unisex range here is a deliberate, disclosed simplification. Scoped to the editor's `InvestigationsSection` only — Advanced Search's view panel joins investigations into one string (`format_investigations`) that doesn't support per-token styling without a bigger rework, and that panel is a quick glance before Edit, not where values get entered.

**Date-order warning (`app/util/validators.py`, `app/ui/sections/patient.py`).** `validate_date_order(admission, surgery, discharge)` compares the three ISO date strings as plain text (no parsing needed) and returns a warning for each out-of-order pair. A pair is only checked when both sides are filled — a blank date is never itself a warning. `PatientSection` shows the joined warning text in a hidden-by-default label below the dates row, on every date edit and on `populate()`. This is the `app/util/validators.py` module CLAUDE.md's layout named from the very start but never built.

**Computed Advanced Search column widths (`app/ui/dialogs/advanced_search.py`).** The old `_COLUMN_WIDTHS` dict was hand-tuned by screenshot three separate times this project (clipped Actions buttons twice, a truncated header once). `_compute_column_widths(table)` replaces it, deriving BHT/Ward/Discharge Date/Created/Modified/Actions from real `QFontMetrics` against the actual content each column can hold — realistic-with-headroom digit samples for BHT/Ward, the widest string the fixed date/timestamp format can ever produce, and the three Actions button labels plus the QSS's own known padding/border for Actions. A font or DPI change on the target laptop can no longer silently reintroduce the clipping. **Doctor stays a fixed, documented judgment call** (90px) — display names are genuinely unbounded text, so there's no "widest sample" to compute from; truncation there is expected and acceptable.

**A fourth clipping bug turned up after computing widths from font metrics alone — `QTableWidget::item`'s own QSS padding (`app/theme.py`, `padding: {TABLE_ITEM_PADDING_Y}px {INPUT_PADDING_X}px`) eats `2*INPUT_PADDING_X` off a cell's usable *width* before any content is drawn, confirmed by measuring a real `setCellWidget()` widget's actual on-screen size against its column width, not assumed.** This applies to text items (they simply elide instead of visibly clipping) and to widget cells alike — the Actions column's buttons were being sized to exactly fit their own `sizeHint()`, then handed a cell 24px narrower than that. `COLUMN_WIDTH_PADDING` now includes this inset plus real breathing room on top of it (a first attempt added only breathing room with no inset, which exactly fit the sample text with zero slack and still clipped on real data). Fixing this pushed the Fixed columns' combined width up enough to squeeze the Stretch column (Patient Name) toward zero on the dialog's original 1200px width — `QHeaderView.setMinimumSectionSize` was tried and rejected here, since it floors *every* section, not just the Stretch one, and just inflated the Fixed columns further. The actual fix was sizing headroom: the dialog widened (now 1300px, still comfortably under the target 1366×768 screen) and the splitter's initial table/view-panel split adjusted so Patient Name gets a reasonable width by construction instead of a floor fighting the other columns for space.

**A fifth bug, same root cause but the vertical axis: the same `QTableWidget::item` padding also eats height, not just width, so the Actions buttons (fixed at `ACTION_BUTTON_HEIGHT`) were vertically clipped inside the default row height even after every horizontal fix above.** Confirmed the same way — a real cell widget's on-screen height (21px) measured well short of the row height that contained it (34px), an inset of `2*TABLE_ITEM_PADDING_Y` (plus a border pixel). `_ROW_HEIGHT` is now computed from `ACTION_BUTTON_HEIGHT` + the actions cell's own top/bottom layout margin + that same padding, instead of reusing `theme.INPUT_HEIGHT_PX` (which was sized for a single line of table *text*, never for this column's real buttons). `theme.TABLE_ITEM_PADDING_Y` was named and pulled out of the QSS literal specifically so both the horizontal (`COLUMN_WIDTH_PADDING`) and vertical (`_ROW_HEIGHT`) fixes read from one source instead of two independently-copied "6"s.

**Actions buttons stay text-only — icons were tried and reverted.** `QStyle.standardIcon` built-ins were added briefly (Full View/Print/Edit), but three icon+text buttons in one narrow table cell read as visually noisy rather than clearer, and Qt's standard set has no icon that actually means "print" or "edit" — the closest matches (`SP_FileDialogContentsView`, `SP_DialogOpenButton`) were approximations, not a real fit. `_ACTION_BUTTONS` stays a shared `(label, QSS objectName)` tuple used by both `_build_actions_cell` and `_compute_column_widths`, so a label change still can't silently desync the two — that drift-safety property didn't depend on icons and was kept.

---

## Application icon

**Decision:** `assets/app_icon.ico` (a document-with-medical-cross glyph, built from the app's own theme colors — `app/theme.py` `PRIMARY`/`DANGER`) is the app's icon everywhere it appears: the `.exe`'s own icon (`build.spec`'s `EXE(..., icon=...)` — what shows on the desktop shortcut, taskbar before any window is open, and Explorer) and the window/taskbar icon once running (`run.py` calls `app.setWindowIcon(...)` once, at startup, covering every window including the top-level exception dialog). `app/config.py`'s `get_app_icon_path()` resolves the file relative to its own location, same pattern as `app/db/connection.py`'s `MIGRATIONS_DIR` — works from source and from inside the PyInstaller `--onedir` bundle without a separate "is this frozen" branch, since `build.spec` bundles `assets/app_icon.ico` at the same relative path via `datas`.

Generated with a one-off Pillow script (not committed, not a runtime dependency — same "Pillow is dev-tooling, not shipped" reasoning already established for `app/util/attachments.py`), producing every standard `.ico` resolution (16 through 256px) from one vector-ish source so it stays crisp at every size Windows actually uses it at (taskbar, title bar, Explorer thumbnail, Alt-Tab).

---

## Button icons on Advanced Search's Actions column — tried, reverted

Covered under "Computed Advanced Search column widths" above: `QStyle.standardIcon` built-ins were added to Full View/Print/Edit, then removed — three icon+text buttons in one narrow table cell read as visually noisy, and Qt's standard icon set has no real "print" or "edit" icon, only approximations. The row-height fix that came with them (below) was kept; the icons weren't.

---

## Dialogs clamped to the actual screen, not just a fixed pixel guess

**Decision:** `app/util/screen.py`'s `clamped_dialog_size(dialog, width, height)` caps a dialog's requested size to its screen's *available* geometry (screen minus the OS taskbar) before the first `resize()`. Applied to `PrintPreviewDialog` (700×900 requested), `SummaryFullViewDialog` (760×820 requested), and `AdvancedSearchDialog` (1260×700 requested).

**Why this was a real bug, not a theoretical one.** The target laptop's screen is 1366×768 (CLAUDE.md) — a dialog requesting 900px or 820px of height is taller than that *entire* screen, let alone the area left over once Windows' taskbar is subtracted. Confirmed by the actual failure mode reported on the target OS: Print Preview's Save/Cancel/Print row and Full View's Close button were pushed off-screen, unreachable without manually dragging the window up first. This didn't show up during development because the dev machine's screen is taller — exactly the kind of bug that "looks fine on my machine" hides.

**Why a helper function, not per-dialog fixed heights.** A second hardcoded height picked to fit 768px today just becomes the same bug again the day someone tests on a different screen (a second monitor, a different laptop) — computing against the *actual* screen at the moment the dialog opens is correct in both directions, on a smaller screen and a larger one alike. `_HEIGHT_MARGIN`/`_WIDTH_MARGIN` (80px/40px) are a deliberately generous approximation of taskbar + title bar rather than an exact figure, since exact chrome size varies by Windows theme/DPI setting and this only needs to be "comfortably enough," not pixel-perfect.

---

## Open items

| Item | Blocks |
|---|---|
| Sign-off on the redesigned A4 layout vs the green form | `printing/layout.py` |
| Confirm S Ca units at this lab (mmol/L assumed) | Investigations grid |
| Backup target — mapped network drive or USB | `util/backup.py` |
| Whether encryption at rest is required | Scoped change, ask before building |
| Verify PySide6 cold-start time on the actual ward laptop | Only tested on dev machines so far; the whole Tkinter→PySide6 switch was justified on styling, not measured startup cost |

---

## Raised with the machine's owner, outside this project's scope

These aren't code changes, but they affect whether the app feels usable:

1. **Second RAM stick.** One of two SODIMM slots is free. Cheap, immediate.
2. **Replace the HDD with a SATA SSD.** The single biggest cause of the machine feeling dead.
3. **Windows 10 1809 has been unsupported since May 2021.** An unpatched machine holding clinical records is a real risk and worth escalating to whoever owns hospital IT.
