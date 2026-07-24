# CLAUDE.md

Offline desktop app for the Surgical Oncology Unit, Teaching Hospital Kurunegala.
Replaces a handwritten green A4 discharge summary form. Stores summaries and prints them.

## The machine this must run on

Acer Aspire A515-53 · i3-8145U · **4 GB RAM (3.86 usable, ~1.6 free)** · **932 GB HDD, not SSD** · Windows 10 Home 1809 (build 17763, unsupported since May 2021) · 1366×768 · single user, offline.

The disk is the bottleneck — Task Manager shows 100% active time at 0 KB/s throughput. Every decision below follows from that. **If a change would increase startup time or disk I/O, don't make it.**

## Stack

Python 3.11 · Tkinter/ttk · sqlite3 (stdlib) · ReportLab · PyInstaller `--onedir`

No web framework, no ORM, no Electron, no async. Stdlib unless there's a reason.

## Hard rules

These exist because of the machine or the setting. Don't relax them without asking.

1. **PyInstaller `--onedir`, never `--onefile`.** Onefile unpacks the runtime to `%TEMP%` on every launch — 5–10s cold start on this disk vs ~2s.
2. **One SQLite connection**, opened at startup, closed at exit. Never per-operation.
3. **WAL mode on** (`PRAGMA journal_mode=WAL`) so saves don't block reads.
4. **Never `SELECT *` the summaries table into memory.** List pane uses `LIMIT`/`OFFSET`. Full record loads only on selection.
5. **No `ttk.Notebook` for the editor sections.** Sections must be simultaneously visible and scannable. Use collapsible frames.
6. **No login screen.** Shared ward PC. Doctor is picked from a header dropdown for attribution. See `docs/decisions.md`.
7. **Autosave on field blur.** A crash must cost one field, not one card.
8. **Top-level exception handler** in `run.py` — log to file, show a dialog. Never die silently.
9. **Cap attachment imports at 5 MB** and resize images on import. A 40 MB phone photo is a realistic way to blow memory here.
10. **Generate PDFs to a temp file**, not in memory. Release after printing.

## Layout

```
run.py                  entry point, exception handler, logging setup
app/config.py           paths (%APPDATA%\DischargeSummaries), constants
app/theme.py            ttk style — all colour/type tokens live here
app/models.py           dataclasses: Summary, Doctor, Template
app/db/                 schema.sql, connection.py, summaries.py, doctors.py, templates.py
app/ui/main_window.py   header + split pane
app/ui/patient_list.py  left pane: search, pagination
app/ui/editor.py        right pane: assembles sections
app/ui/sections/        one file per editor section (patient, procedure, clinical,
                        investigations, attachments) — mirrors docs/ui-spec.md §3.3
app/ui/widgets/         collapsible.py, scrollframe.py, labeled.py, datefield.py
app/ui/dialogs/         print_preview.py, doctors.py, templates.py, settings.py
app/printing/layout.py  ReportLab A4 card — the deliverable that matters
app/printing/printer.py os.startfile(path, "print") dispatch
app/util/               logging.py, backup.py, validators.py
docs/                   see below
data/                   gitignored, dev DB only
```

Build `widgets/collapsible.py` and `widgets/scrollframe.py` first — everything else depends on them.

## Tkinter gotchas specific to this build

- Use `ttk`, not raw `tk`. Raw Tk defaults look like 1995 and undercut trust in a clinical setting.
- Editor pane needs `Canvas` + `Scrollbar` + inner frame with `<Configure>` bound to update scrollregion. Bind `<MouseWheel>` explicitly — Tkinter does not scroll canvases by default.
- On ttk Entry, set **both** `background` and `fieldbackground` or the theme looks half-applied.
- ttk widgets have no corner radius. Accept square corners. Don't draw inputs on a Canvas to fake it — costs far more than it returns.
- 40px input height comes from `ipady` on the `grid()` call, not from a style property.
- Collapsible section = `ttk.Frame` toggled with `grid()` / `grid_remove()`.
- Debounce search with `after()` / `after_cancel()`. No threads.

## Data conventions

- Dates: stored **ISO-8601** (`YYYY-MM-DD`), displayed **DD/MM/YYYY** (Sri Lankan convention). Conversion at the UI boundary only.
- Doctors are **deactivated, never deleted** — old summaries must keep printing the correct signing officer.
- Templates **insert** text; they don't link. Editing a template must never alter an existing summary.
- Deletes are soft (flag + purge after 30 days).
- BHT number is not unique — the same patient can have multiple admissions. Warn on duplicate, don't block.

## Patient data

This app holds real clinical records. Applies to code and to anything committed:

- **Never commit real patient data.** Test fixtures and sample data are fictional. `data/` is gitignored.
- The `.db` file has no encryption by default — if the hospital requires encryption at rest, that's a scoped change, ask first.
- Backup on exit copies the `.db` to a configured path. A single file on a single unmirrored HDD is the main data-loss risk.
- Don't add telemetry, crash reporting, or any network call. The app is offline by design.

## Docs

| File | What it's for |
|---|---|
| `docs/ui-spec.md` | Screen layout, fields, tokens, interaction rules. The design source of truth. |
| `docs/schema.md` | Tables, columns, why each field exists. |
| `docs/print-layout.md` | A4 card mapping against the original paper form. |
| `docs/deployment.md` | Build, zip, transfer, SmartScreen, first run. |
| `docs/decisions.md` | Why no login, why onedir, why the investigations grid. Read before re-litigating. |
| `docs/user-guide.md` | For ward staff. Plain language, printable. |

## Working style

- Small commits, one concern each.
- Update `docs/decisions.md` when you make a non-obvious call.
- Test on the target laptop before calling anything done. Startup time and print output are the two things that can't be verified on a dev machine.
