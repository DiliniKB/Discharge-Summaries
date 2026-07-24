# Discharge Summary System — UI Design Specification

**Target:** Surgical Oncology Unit, Teaching Hospital Kurunegala
**Machine:** Acer Aspire A515-53 · i3-8145U · 4 GB RAM · 932 GB HDD · Windows 10 (1809) · 1366×768
**Stack:** Python 3 + Tkinter/ttk + sqlite3 + ReportLab
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
2. **Print preview** — modal, shows the A4 card at true proportions
3. **Template manager** — modal, edit canned procedure text
4. **Settings** — modal, printer default, backup path, doctor list

---

## 3. Main window

**Fixed minimum 1280×720.** Opens maximised.

```
┌────────────────────────────────────────────────────────────────────────┐
│  Discharge Summaries · Surgical Oncology Unit    Dr [S. Herath  ▾]     │ 56px
├──────────────┬─────────────────────────────────────────────────────────┤
│ [+ New Card] │  W.D. Kusuma Wijerathna          [Print] [Save] [ ⋮ ]   │ 64px
│              │  BHT 10178 · Ward 45                    ✓ Saved 14:32   │
│ [Search... ] ├─────────────────────────────────────────────────────────┤
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
- Right: doctor dropdown. Persists across sessions in settings. Value prints on the card as the issuing officer.
- No login, no avatar, no admin badge.

### 3.2 Patient list pane (280 px, fixed)

- **New Card** — full-width primary button, top. Creates a blank record and focuses the Name field.
- **Search** — filters as you type, matching BHT number *or* name substring, case-insensitive. Debounce 150 ms.
- **Cards** — name (bold, 15 px), then `BHT · Ward` and discharge date (13 px, grey). Discharge date matters because re-admissions produce duplicate names.
- Sorted by discharge date descending. Unsaved new cards pin to the top with a dot marker.
- Selected card: 3 px left accent bar, tinted background.
- Scrolls independently of the editor.

### 3.3 Editor pane

Scrollable region (`Canvas` + `Scrollbar`) since content exceeds 768 px.

**Action bar (64 px, sticky at top of pane):**
- Patient name and BHT as a live-updating breadcrumb, so the user always knows which record is open.
- **Print** — primary, leftmost. Most-used action.
- **Save** — secondary. Autosave makes it mostly redundant, but its presence reassures.
- **⋮ overflow** — Duplicate, Delete. Delete is buried and confirms with the patient name typed back.
- Save state indicator: `✓ Saved 14:32` / `Saving…` / `⚠ Not saved`.

**Sections** are collapsible panels with a chevron. State persists per-user.

| Section | Default | Contents |
|---|---|---|
| Patient & Admission | Open | Name, Age, Sex, BHT, Ward, Telephone, Date of Admission, Date of Surgery, Date of Discharge, Blood group |
| Procedure | Open | Procedure title, Surgical team, Indication, Procedure steps, template picker |
| Clinical History | **Collapsed** | Presenting Complaint, Past Medical History, Past Surgical History, Allergies, Examination, Findings |
| Investigations & Management | Open | Investigation grid, Management, Histology Report |
| Attachments | Collapsed | File list + drop zone |

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

### 4.2 Dates

`DD/MM/YYYY` display order (Sri Lankan convention), stored ISO-8601. Three separate entry boxes rather than a calendar picker — typing is faster than clicking for staff entering a date they already know. Validate: surgery date must fall between admission and discharge; warn inline, don't block.

### 4.3 Procedure templates

Dropdown inserts canned text into the Steps box. Seeded from the unit's common operations. **Insert, don't link** — once inserted, the text is freely editable and the record keeps its own copy. Editing a template later must never alter an existing summary.

### 4.4 Blood group

Handwritten on the sample card, meaning it was needed and the form lacked it. Add as a proper field.

### 4.5 Text areas

Procedure Steps and Management are multi-line, auto-growing to a 6-line cap then scrolling. Monospace is wrong here — use the body face.

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
| Input text | 16 px | Regular |
| Patient name (list) | 15 px | Semibold |
| Metadata | 13 px | Regular, muted |
| Procedure title input | 18 px | Semibold |

### Spacing

4 px base unit. Section padding 20 px. Field vertical gap 16 px. Input height 40 px, horizontal padding 12 px, corner radius 4 px.

### Focus

2 px `primary` ring, 1 px offset. Must be visible on every focusable element — keyboard navigation is a primary path, not a fallback.

---

## 7. Interaction rules

| Trigger | Behaviour |
|---|---|
| Field blur | Autosave. Indicator shows `Saving…` then `✓ Saved HH:MM`. |
| `Ctrl+S` | Force save. |
| `Ctrl+N` | New card. |
| `Ctrl+F` | Focus search. |
| `Ctrl+P` | Print preview. |
| `Esc` | Close modal; if none, clear search. |
| `Tab` | Next field in paper-form order, skipping collapsed sections. |
| Switch patient with unsaved edits | Save silently. No dialog — autosave means there is nothing to ask about. |
| Delete | Confirm by typing the patient name. Soft-delete: flag the row, purge after 30 days. |
| Search returns nothing | `No summaries match "xyz"` plus a **Create new card** button. |
| Empty database | Centred message with a single New Card call to action. |

---

## 8. Accessibility and error handling

- Every input has a visible persistent label. No placeholder-only labelling — placeholders vanish on focus and the user forgets which box is which.
- Validation is inline, below the field, in `danger`. Never a modal dialog.
- Required to save: Name, BHT. Everything else may be blank, exactly as on paper.
- Duplicate BHT on save: warn but permit. Same patient can have multiple admissions.
- Colour is never the only signal — errors carry an icon and text.

---

## 9. Tkinter implementation notes

- `ttk` with a custom theme, not raw `tk` widgets — raw Tk defaults look like 1995 and undercut trust in a clinical setting.
- **Do not** use `ttk.Notebook` for the sections. Tabs hide content; these panels must be simultaneously visible and scannable.
- Collapsible section = `ttk.Frame` toggled with `grid()` / `grid_remove()`, chevron as a `ttk.Label` with a bound click.
- Editor pane needs `Canvas` + `Scrollbar` + inner frame, with `<Configure>` bound to update the scroll region. Bind `<MouseWheel>` explicitly — Tkinter does not scroll canvases by default.
- `ttk.Style().configure()` for the tokens above. Set `fieldbackground` as well as `background` on Entry, or the theme will look half-applied.
- Corner radius is not available on ttk widgets. Either accept square corners or draw inputs on a Canvas. **Accept square corners** — the Canvas route costs far more than it returns.
- Debounce search with `after()` / `after_cancel()`, not a thread.
- 40 px input height comes from `ipady` on the grid call, not from a style property.

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
