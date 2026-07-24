# Decisions

Non-obvious calls and the reasoning behind them. Read before re-litigating.

Most of these follow from one fact: the target machine has 4 GB of RAM and a **932 GB spinning hard disk running at 100% active time with 0 KB/s throughput**. The disk is the binding constraint, not the CPU or memory.

---

## Python + Tkinter over .NET WinForms

**Decision:** Python 3.11, Tkinter/ttk, PyInstaller.

.NET Framework 4.7.2 already ships with Windows 10 1809, so a .NET build would be a single exe with nothing to bundle — a better deployment story. Python was chosen for developer fluency and iteration speed on a small internal tool.

**What this costs:** a bundled runtime folder instead of one file, and slower cold start. Mitigated by `--onedir` (below). Verified acceptable on the target machine before committing.

**Revisit if:** startup exceeds ~4 seconds on the ward laptop, or deployment friction becomes a recurring support burden.

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

---

## Soft delete with a 30-day purge

**Decision:** `deleted_at` timestamp; rows purged by a maintenance pass after 30 days. Delete confirms by typing the patient name.

There is one database file on one unmirrored drive. A misclick should not be terminal.

---

## Paginated list queries

**Decision:** `LIMIT 50` on the list pane, full record loaded only on selection.

With a few hundred summaries, loading everything would work fine today and degrade badly by year three — on the machine least able to absorb it. Not premature optimisation on this hardware.

---

## Open items

| Item | Blocks |
|---|---|
| Sign-off on the redesigned A4 layout vs the green form | `printing/layout.py` |
| Confirm S Ca units at this lab (mmol/L assumed) | Investigations grid |
| Backup target — mapped network drive or USB | `util/backup.py` |
| Whether encryption at rest is required | Scoped change, ask before building |

---

## Raised with the machine's owner, outside this project's scope

These aren't code changes, but they affect whether the app feels usable:

1. **Second RAM stick.** One of two SODIMM slots is free. Cheap, immediate.
2. **Replace the HDD with a SATA SSD.** The single biggest cause of the machine feeling dead.
3. **Windows 10 1809 has been unsupported since May 2021.** An unpatched machine holding clinical records is a real risk and worth escalating to whoever owns hospital IT.
