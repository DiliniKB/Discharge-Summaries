# Discharge Summaries

Offline desktop app for the Surgical Oncology Unit, Teaching Hospital Kurunegala. Creates, stores, and prints patient discharge summaries, replacing a handwritten A4 form.

Runs on a single ward laptop. No server, no network, no installation.

---

## Requirements

- Python 3.11+
- Windows for building (the target is Windows 10; `os.startfile` printing is Windows-only)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run in development

```bash
python run.py
```

First launch creates the database at `%APPDATA%\DischargeSummaries\data.db` and seeds the doctor list. To use a throwaway DB instead:

```bash
set DS_DATA_DIR=.\data
python run.py
```

## Build for the ward laptop

```bash
pyinstaller build.spec
```

Produces `dist/DischargeSummaries/`. Zip that whole folder — it is not a single exe.

**Do not switch to `--onefile`.** It unpacks the runtime to `%TEMP%` on every launch, which costs 5–10 seconds of cold start on the target machine's spinning disk. See `docs/decisions.md`.

Full transfer and first-run steps, including the SmartScreen warning staff will hit: `docs/deployment.md`.

## Tests

```bash
pytest
```

Database and printing tests use fictional patient data. Never commit real records.

## Where things live

| Path | Contents |
|---|---|
| `run.py` | Entry point, exception handler, logging |
| `app/db/` | SQLite access. One connection, WAL mode. |
| `app/ui/` | Tkinter screens. `sections/` maps 1:1 to the editor sections in the UI spec. |
| `app/printing/` | ReportLab A4 layout and print dispatch |
| `docs/` | Spec, schema, decisions, deployment, user guide |
| `data/` | Dev database. Gitignored. |

## Target machine

Acer Aspire A515-53 · i3-8145U · 4 GB RAM · 932 GB HDD · Windows 10 1809 · 1366×768.

The spinning disk is the binding constraint, not the RAM. Startup time and disk I/O are the things to protect. `CLAUDE.md` has the full rule set.

## Docs

- `docs/ui-spec.md` — screen layout, fields, visual tokens, interaction rules
- `docs/schema.md` — tables and columns
- `docs/print-layout.md` — the A4 card, mapped against the paper form
- `docs/deployment.md` — build, transfer, install, update
- `docs/decisions.md` — why the non-obvious calls were made
- `docs/user-guide.md` — for ward staff

## Data handling

The database holds real patient records.

- `data/` and all `.db` files are gitignored. Never commit real records.
- The app makes no network calls. No telemetry, no crash reporting.
- Backup on exit copies the database to a configured path. Configure it — a single file on one unmirrored drive is the main data-loss risk.
