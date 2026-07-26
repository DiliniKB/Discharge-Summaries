# Discharge Summary System — UI Design Specification

**Target:** Surgical Oncology Unit, Teaching Hospital Kurunegala
**Machine:** Acer Aspire A515-53 · i3-8145U · 4 GB RAM · 932 GB HDD · Windows 10 (1809) · 1366×768
**Stack:** Python 3 + PySide6 (Qt6) + sqlite3 + ReportLab
**Deployment:** PyInstaller `--onedir`, zipped, no installation

---

## 1. Design principles

These follow from the machine and the setting, not from taste.

| Principle | Reason |
|---|---|
| Light theme | Ward lighting is fluorescent; the printed card is white paper. Screen and print should look alike when held side by side. |
| 16 px minimum body type, 40 px input height | Users are standing, hurried, and the screen is 1366×768. Desktop-default sizing is too small here. |
| Autosave on field blur | The machine is unpatched and under-resourced. Losing a half-filled card is the worst failure mode. |
| No login | Shared ward PC. Doctor selected from a dropdown for attribution; no passwords anyone will maintain. |
| Every paper field present | Staff cross-check the screen against the old green form. A missing field breaks that trust. |
| Keyboard-first | Tab order follows the paper form top to bottom. Mouse is optional for data entry. |

---

## 2. Screen inventory

1. **Main window** — patient list + editor (the primary and near-only screen)
2. **Advanced Search** — modal, filter/sort/browse every summary, view/print/edit any result
3. **Print preview** — modal, shows the A4 card at true proportions
4. **Template manager** — modal, edit canned procedure text
5. **Settings** — modal, printer default, backup path, doctor list
6. **Recently Deleted** — modal, reached from the header, restores a soft-deleted summary

---

## 3. Main window

**Fixed minimum 1280×720.** Opens maximised.

```
┌────────────────────────────────────────────────────────────────────────┐
│  Discharge Summaries · Surgical Oncology Unit    Dr [S. Herath  ▾]     │ 56px
├──────────────┬─────────────────────────────────────────────────────────┤
│ [+ New Card] │  W.D. Kusuma Wijerathna          [Print] [Save] [ ⋮ ]   │ 64px
│              │  BHT 10178 · Ward 45                    ✓ Saved 14:32   │
│ [Advanced    │                                                          │
│  Search    ] ├─────────────────────────────────────────────────────────┤
│              │                                                          │
│ ▸ Wijerathna │   ▼ PATIENT & ADMISSION                                 │
│   10178 · 45 │   ┌────────────────────────────────────────────────┐    │
│   22 Jan     │   │ Name        [                              ]   │    │
│              │   │ Age [  ]  Sex [ ▾ ]  BHT [        ]  Ward [ ] │    │
│ ▸ A.B.Perera │   │ Telephone   [                    ]            │    │
│   10202 · 45 │   │ Admitted [        ] Surgery [      ]          │    │
│   21 Jan     │   │ Discharged [      ] Blood group [      ]      │    │
│              │   └────────────────────────────────────────────────┘    │
│ ▸ K.M.Silva  │                                                          │
│   10166 · 45 │   ▼ PROCEDURE                        [Template ▾]       │
│   19 Jan     │   ┌────────────────────────────────────────────────┐    │
│              │   │ Title    [COMPLETE THYROIDECTOMY UNDER GA   ]  │    │
│              │   │ Team     [                                  ]  │    │
│              │   │ Indication [                                ]  │    │
│              │   │ Steps    [                                  ]  │    │
│              │   │          [                                  ]  │    │
│              │   └────────────────────────────────────────────────┘    │
│              │                                                          │
│              │   ▶ CLINICAL HISTORY                    2 of 6 filled   │
│              │                                                          │
│              │   ▼ INVESTIGATIONS & MANAGEMENT                         │
│              │   ┌────────────────────────────────────────────────┐    │
│              │   │ FBS [86 ] SCr [40 ] AST [20 ] Na [138]        │    │
│              │   │ K   [4  ] SCa [   ] Hb  [11.7]  [+ Other]     │    │
│              │   │ Management [                                ]  │    │
│              │   │ Histology  [                                ]  │    │
│              │   └────────────────────────────────────────────────┘    │
│              │                                                          │
│              │   ▶ ATTACHMENTS                              0 files    │
│  280px       │                                                          │
└──────────────┴─────────────────────────────────────────────────────────┘
```

### 3.1 Header (56 px)

- Left: unit name, static.
- Right: doctor dropdown, then 🗑 Recently Deleted, then ⚙ Settings. Doctor value persists across sessions and prints on the card as the issuing officer.
- **Recently Deleted** — lists every soft-deleted summary (no purge job exists yet, so this is everything ever deleted, not just the last 30 days — `docs/decisions.md`), each with a Restore button. A standalone maintenance action, not tied to whichever record is open, same as Settings.
- No login, no avatar, no admin badge.

### 3.2 Patient list pane (280 px, fixed)

- **New Card** — full-width primary button, top. Creates a blank record and focuses the Name field.
- **Advanced Search** — full-width secondary button, below New Card. Opens the Advanced Search modal (§3.2a) — this pane has no search box of its own anymore.
- **Refresh** — full-width secondary button, below Advanced Search. Re-runs the default list query without switching the open record — the list otherwise only updates after this app's own saves/creates, not changes made elsewhere (e.g. this session's own load-test scripts).
- **Cards** — name (bold, 15 px), then `BHT · Ward` and discharge date (13 px, grey). Discharge date matters because re-admissions produce duplicate names.
- Sorted by discharge date descending — always the default browsing list, unfiltered. Unsaved new cards pin to the top with a dot marker.
- Selected card: 3 px left accent bar, tinted background.
- Scrolls independently of the editor.

### 3.2a Advanced Search (modal, 1200×700)

Replaces the old inline search box entirely — this is the only way to filter or search summaries now (docs/decisions.md).

- **Filters**, grouped by kind (all optional, combine with AND), three rows: (1) Patient Name/BHT, Doctor (*All doctors* + every doctor including deactivated ones), and the **Search**/**Clear filters** buttons — together on this top row since it's the widest, rather than stranded on their own line; (2) Keyword, full width (matches clinical text — procedure, indication, steps, presenting complaint, past medical/surgical history, allergies, examination, management, histology; **not** name/BHT, which have their own field); (3) Created date range and Modified date range together, compact, left-aligned.
- **Patient Name/BHT and Doctor filter live** — Name debounces 150ms (same as the old inline search's own debounce), Doctor re-queries immediately on selection (already a discrete, deliberate action). **Keyword and the date ranges only apply when Search is clicked** — a full clinical-text scan or an unindexed date-range scan isn't something to fire on every keystroke (`docs/decisions.md`).
- **Results table**: Patient Name / BHT / Ward / Doctor / Discharge Date / Created / Modified / Actions. Click a column header to sort. Every fixed column's width is computed from real font metrics against its actual content (`_compute_column_widths`, docs/decisions.md) rather than a hand-tuned pixel guess — Doctor is the one exception, a fixed judgment-call width since names are unbounded.
- **Clicking a row** shows its full record in the quick-view panel directly — no separate View button; a click is enough for something non-destructive and reversible.
- **Actions** column, per row: **Full View** (opens a bigger, dedicated detail popup — see below), **Print** (opens the same Print Preview modal as the editor's Print button), **Edit** (loads the record into the main editor and closes this dialog) — Print/Edit stay explicit buttons since both are real, consequential operations, unlike just looking.
- **Quick-view panel** — alongside the results table, updates on row click. A compact, flat read-out: identity line (name, age/sex, BHT, ward) and doctor attribution, then Admission / Procedure / Clinical History / Investigations & Management / Attachments, grouped the same way as the editor's sections. Blank fields are omitted entirely rather than shown as "—" — same "omit if nothing to show" rule the printed card already follows (`docs/print-layout.md`). Investigation values are shown inline (`FBS 86 · SCr 40 · ...`). Attachments list filename, size, and an Open button (hands off to the OS's default viewer — `docs/decisions.md`). Not a PDF — instant, no render cost per click (docs/decisions.md).
- **Full View popup** (`app/ui/dialogs/summary_full_view.py`, ~760×820) — a dedicated, visually organized detail screen, not just a bigger quick-view panel: a tinted "hero" header with the patient's name and identity line; a red allergy alert box (`⚠ Allergies: ...`) shown prominently whenever allergies are recorded — the one thing on a discharge summary that's genuinely safety-critical to flag; then Admission / Procedure / Clinical History / Investigations & Management as bordered card sections (mirroring the editor's own section styling), with Admission's short fields (Telephone, Blood Group, the three dates) laid out side by side rather than one per line. Same blank-field-omission rule as the quick-view panel; a section with nothing in it shows a muted "No … recorded" line, or (Clinical History only) is omitted entirely when nothing in that group is filled. An Attachments card (filename + size + Open button per file) is appended last, but only when the record actually has files — unlike every other card, it's omitted entirely rather than showing a muted "none" line, since most records won't have any.
- **Loading state** — Search disables itself and shows "Searching…" while the query runs (synchronous, no threading — CLAUDE.md rules out async generally). Barely visible on a fast dev machine; matters more on the target HDD.

### 3.3 Editor pane

Scrollable region (`Canvas` + `Scrollbar`) since content exceeds 768 px.

**Action bar (64 px, sticky at top of pane):**
- Patient name and BHT as a live-updating breadcrumb, so the user always knows which record is open.
- **Print** — primary, leftmost. Most-used action.
- **Save** — secondary. Autosave makes it mostly redundant, but its presence reassures.
- **⋮ overflow** — Duplicate, Delete. **Duplicate** copies patient identity, dates, and all clinical narrative text into a brand-new record (fresh id, timestamps, and doctor attribution — stamped with whoever's currently selected in the header, not copied from the source); investigation values and attachments are deliberately NOT copied — reused text is fine as a starting point, but carrying over another patient's lab results or files onto a new record is a real safety risk, not a convenience (`docs/decisions.md`). **Delete** is a single Yes/No confirm (no typing required) — Recently Deleted (below) is the real safety net now, not a heavier confirmation step.
- Save state indicator: `✓ Saved 14:32` / `Saving…` / `⚠ Not saved`.

**Sections** are collapsible panels with a chevron. State persists per-user.

| Section | Default | Contents |
|---|---|---|
| Patient & Admission | Open | Name, Age, Sex, BHT, Ward, Telephone, Date of Admission, Date of Surgery, Date of Discharge, Blood group |
| Procedure | Open | Procedure title, Surgical team, Indication, Procedure steps, template picker |
| Clinical History | **Collapsed** | Presenting Complaint, Past Medical History, Past Surgical History, Allergies, Examination, Findings |
| Investigations & Management | Open | Investigation grid, Management, Histology Report |
| Attachments | Collapsed | File list + drop zone — multi-select file picker or drag-and-drop, both feeding one shared import path. Each row shows filename, size, an Open button (hands off to the OS's default viewer — `docs/decisions.md`), and a remove button. Files over 5 MB are rejected with an inline message (`docs/decisions.md`); images are resized to a 1600 px max dimension on import. Disabled (picker and drag-drop both) until a summary is open. Header counter reads `"N files"`, live. |

Collapsed headers show a fill count (`2 of 6 filled`) so nothing is invisible. All fields exist and print regardless of section state.

---

## 4. Field-level decisions

### 4.1 Investigations as a grid, not free text

The paper form has one free-text box. In practice it always holds the same seven analytes.

| Field | Unit | Type |
|---|---|---|
| FBS | mg/dL | numeric |
| SCr | µmol/L | numeric |
| AST | U/L | numeric |
| Na | mmol/L | numeric |
| K | mmol/L | numeric |
| S Ca | mmol/L | numeric |
| Hb | g/dL | numeric |

Plus **+ Other** to add ad-hoc `label: value` rows.

Gains: faster entry, no transcription typos, and the data becomes queryable later if the unit wants trends. Prints as a clean list identical in shape to the current card.

**Abnormal value flagging.** A value outside the general adult reference range for its analyte (`app/util/lab_ranges.py`) gets a red border/tint on blur and on reopening a saved record. A prompt to double-check, not a diagnosis — never blocks saving, and non-numeric results ("<0.5", "Not done") are never flagged since there's nothing numeric to compare (docs/decisions.md).

### 4.2 Dates

`DD/MM/YYYY` display order (Sri Lankan convention), stored ISO-8601. A single typed field (format-as-you-type, not an input mask — Qt mask blanks render as visible `_` characters on screen, inconsistent with every other empty field) is the primary interaction: typing is faster than clicking for staff entering a date they already know. A small calendar button sits alongside it as a convenience fallback for the rarer case of not knowing the exact date offhand — additive, not a replacement of the typing-first design. Date of Discharge defaults to today (summaries are filled in around discharge time); Admission and Surgery stay blank, since they're almost always past dates by the time the form is filled in. Validate: Admission ≤ Surgery ≤ Discharge (`app/util/validators.py`); an out-of-order pair shows an inline warning below the dates row, checked on every edit and on reopening a saved record — warns, never blocks (docs/decisions.md).

### 4.3 Procedure templates

Dropdown inserts canned text into the Steps box. Seeded from the unit's common operations. **Insert, don't link** — once inserted, the text is freely editable and the record keeps its own copy. Editing a template later must never alter an existing summary.

### 4.4 Blood group

Handwritten on the sample card, meaning it was needed and the form lacked it. Add as a proper field.

### 4.5 Text areas

Procedure Steps, Management, and Histology Report are multi-line, auto-growing to a 6-line cap then scrolling. Monospace is wrong here — use the body face. Histology reports are routinely multi-paragraph pathology text (docs/schema.md: "often filled in after discharge") — a single-line box forces internal horizontal scrolling to review, the same problem fixed for Clinical History.

---

## 5. Print preview

Modal, opens on Print. Renders the actual PDF at true A4 proportions, scaled to fit.

- Left: page thumbnail. Right: printer picker, copies, and a **Print** button.
- **Esc** closes. **Ctrl+P** from the editor opens preview directly.
- Preview is the real generated PDF, not an HTML approximation — what is on screen is what leaves the printer.

Currently the unit has no preview at all, so misprints waste a form. This is the highest-value addition beyond storage.

---

## 6. Visual system

### Colour

| Token | Value | Use |
|---|---|---|
| `bg` | `#F7F8FA` | Window background |
| `surface` | `#FFFFFF` | Panels, inputs |
| `border` | `#D8DCE3` | Input outlines, dividers |
| `text` | `#1A1D23` | Body |
| `text-muted` | `#6B7280` | Labels, metadata |
| `primary` | `#1D6FD0` | Buttons, focus ring, selection |
| `primary-tint` | `#E8F1FC` | Selected list row |
| `danger` | `#C0392B` | Delete only |
| `success` | `#2E7D4F` | Save confirmation |

Single accent. No gradients, no shadows beyond a 1 px border — they cost render time on integrated graphics and add nothing.

### Type

Segoe UI (present on every Windows 10 install; no font shipping needed).

| Role | Size | Weight |
|---|---|---|
| Section header | 13 px | Semibold, uppercase, letter-spaced |
| Field label | 13 px | Regular, muted |
| Input text | 14 px | Regular |
| Patient name (list) | 15 px | Semibold |
| Metadata | 13 px | Regular, muted |
| Procedure title input | 18 px | Semibold |

### Spacing

4 px base unit. Section padding 20 px. Field vertical gap 16 px. Input height 34 px, horizontal padding 12 px, corner radius 4 px.

### Focus

2 px `primary` ring, 1 px offset. Must be visible on every focusable element — keyboard navigation is a primary path, not a fallback.

---

## 7. Interaction rules

| Trigger | Behaviour |
|---|---|
| Field blur | Autosave. Indicator shows `Saving…` then `✓ Saved HH:MM`. |
| `Ctrl+S` | Force save. |
| `Ctrl+N` | New card. |
| `Ctrl+F` | Open Advanced Search. |
| `Ctrl+P` | Print preview. |
| `Esc` | Close modal (native Qt `QDialog` behaviour). |
| `Tab` | Next field in paper-form order, skipping collapsed sections. |
| Switch patient with unsaved edits | Save silently. No dialog — autosave means there is nothing to ask about. |
| Delete | Confirm with a single Yes/No click. Soft-delete: flag the row, purge after 30 days, restorable from Recently Deleted in the meantime. |
| Advanced Search returns nothing | Empty results table — filters are visible above it, inviting adjustment rather than a dead end. |
| Empty database | Centred message with a single New Card call to action. |

---

## 8. Accessibility and error handling

- Every input has a visible persistent label. No placeholder-only labelling — placeholders vanish on focus and the user forgets which box is which.
- Validation is inline, below the field, in `danger`. Never a modal dialog.
- Required to save: Name, BHT. Everything else may be blank, exactly as on paper.
- Duplicate BHT on save: warn but permit. Same patient can have multiple admissions.
- Colour is never the only signal — errors carry an icon and text.

---

## 9. PySide6 implementation notes

Stack is PySide6 (Qt6), not Tkinter/ttk — see `docs/decisions.md` for why. Notes below reflect that.

- Style the whole app with one **QSS** stylesheet (`app/theme.py`), applied once via `app.setStyleSheet(...)` at startup — one source of truth for the tokens in §6, not scattered per-widget `.setStyleSheet()` calls.
- **Do not** use `QTabWidget` for the sections. Tabs hide content; these panels must be simultaneously visible and scannable.
- Collapsible section = a `QWidget` with a clickable header row and a body `QWidget` toggled via `setVisible()`, chevron as a `QLabel` with a bound click handler — not `QToolBox` (its animated single-open-at-a-time behaviour fights "simultaneously visible").
- Editor pane is a `QScrollArea` with a plain `QWidget` body set via `setWidget()`. Qt scrolls this natively — no manual wheel-event binding needed, unlike Tkinter's Canvas approach.
- QSS gives real `border-radius`, hover/pressed states, and focus rings — this is the reason PySide6 was chosen over ttk. Use these deliberately, matching the tokens above; don't add effects the spec doesn't call for.
- Debounce search with a restartable `QTimer` (`start()` again cancels the pending fire), not a thread.
- 40 px input height: `setMinimumHeight(40)` directly on the input widget, not a layout-level hack.
- Trim unused Qt6 modules (`QtNetwork`, `QtSql`, `QtQml`, `WebEngine`) from `build.spec` — PyInstaller can pull them in speculatively otherwise, and this app touches none of them.

---

## 10. Deliberately excluded

| Excluded | Reason |
|---|---|
| Login screen | Shared ward PC. Passwords will be written on a sticky note or forgotten. Dropdown gives attribution at zero cost. |
| Dark theme | Wrong for fluorescent ward lighting and mismatched to printed output. |
| Dashboard / statistics | No stated need. Adds startup cost on a slow disk. |
| Rich text editing | The printed card is plain text. Formatting would only break print fidelity. |
| Multi-user sync | Single machine. Network reliability is not assumed. |
| Patient photos | Clinical data sensitivity for no stated benefit. |

---

## 11. Open questions

1. Does the printed card need the exact green-form layout, or is a redesigned but complete layout acceptable? *(Affects the print module, not this screen.)*
2. Is `S Ca` reported in mmol/L or mg/dL at this lab?
3. Should the doctor list be editable in-app, or fixed at build time?
4. Backup target — mapped network drive, or USB?
