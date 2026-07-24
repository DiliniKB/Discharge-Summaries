# Database schema

SQLite, single file at `%APPDATA%\DischargeSummaries\data.db`. Created and migrated on first launch from `app/db/schema.sql`.

## Connection settings

Applied once at startup in `app/db/connection.py`:

```sql
PRAGMA journal_mode = WAL;      -- saves don't block reads
PRAGMA synchronous  = NORMAL;   -- safe with WAL, far fewer fsyncs on a spinning disk
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 3000;
```

`synchronous = NORMAL` is the deliberate one. `FULL` fsyncs on every commit, which on this HDD makes autosave-on-blur feel like a stall. With WAL, `NORMAL` risks losing only the last transaction on an OS crash — acceptable given autosave writes constantly.

---

## Tables

### `summaries`

One row per discharge summary. The central table.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `patient_name` | TEXT NOT NULL | Required to save |
| `age` | INTEGER | |
| `sex` | TEXT | `Female` / `Male` / null |
| `bht_number` | TEXT NOT NULL | **Not unique** — see below |
| `ward` | TEXT | Defaults to `45` |
| `telephone` | TEXT | Text, not integer — leading zeros, spaces, `+94` |
| `blood_group` | TEXT | Added field, not on the printed paper form |
| `date_admission` | TEXT | ISO-8601 `YYYY-MM-DD` |
| `date_surgery` | TEXT | ISO-8601 |
| `date_discharge` | TEXT | ISO-8601 |
| `procedure_title` | TEXT | Prints as the card headline |
| `surgical_team` | TEXT | |
| `indication` | TEXT | |
| `procedure_steps` | TEXT | Multi-line |
| `presenting_complaint` | TEXT | Clinical history — often blank |
| `past_medical_history` | TEXT | |
| `past_surgical_history` | TEXT | |
| `allergies` | TEXT | |
| `examination` | TEXT | |
| `findings` | TEXT | |
| `management` | TEXT | Multi-line drug list |
| `histology_report` | TEXT | Often filled in after discharge |
| `created_by` | INTEGER FK → doctors | Signing officer at creation |
| `last_edited_by` | INTEGER FK → doctors | |
| `created_at` | TEXT | ISO-8601 timestamp |
| `updated_at` | TEXT | ISO-8601 timestamp |
| `deleted_at` | TEXT | Soft delete. Null = live. |

**Dates are stored ISO-8601 and displayed DD/MM/YYYY.** Conversion happens at the UI boundary only. ISO sorts correctly as text, which is why it's the storage format.

**`bht_number` is not unique.** The same patient can be admitted more than once and carry the same BHT. The UI warns on duplicate but does not block. Do not add a unique constraint.

**`created_by` / `last_edited_by` are the audit trail.** This is why the app needs no login — attribution is a field on the record, not an authentication system.

**Soft delete.** `deleted_at` is set rather than the row removed; a maintenance pass purges rows older than 30 days. Protects against a misclick destroying a record with no backup.

Indexes:

```sql
CREATE INDEX idx_summaries_bht      ON summaries(bht_number);
CREATE INDEX idx_summaries_name     ON summaries(patient_name);
CREATE INDEX idx_summaries_discharge ON summaries(date_discharge DESC);
```

The first two back the search box. The third backs the default list ordering. On a spinning disk these matter more than they would on an SSD.

---

### `investigations`

Lab values, one row per analyte per summary.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `summary_id` | INTEGER FK → summaries | `ON DELETE CASCADE` |
| `label` | TEXT NOT NULL | `FBS`, `SCr`, `AST`, `Na`, `K`, `S Ca`, `Hb`, or ad-hoc |
| `value` | TEXT | Text, not numeric — results like `<0.5` or `Not done` occur |
| `unit` | TEXT | |
| `sort_order` | INTEGER | Print order |

**Why a table and not seven columns on `summaries`.** The paper form has one free-text investigations box, but in practice it always holds the same seven analytes. A table gives structured entry (fewer transcription errors), allows ad-hoc extra rows, and makes the values queryable later if the unit ever wants trends. The seven standard rows are created with every new summary; blank ones are skipped at print time.

`value` is TEXT deliberately. Lab reports contain non-numeric results and forcing REAL would either reject them or silently lose them.

---

### `doctors`

Populates the header dropdown.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | TEXT NOT NULL | e.g. `Dr. S. Herath` |
| `designation` | TEXT | e.g. `SR Onco-surgery` |
| `active` | INTEGER DEFAULT 1 | |
| `sort_order` | INTEGER DEFAULT 0 | Consultant first, not alphabetical |

**Deactivate, never delete.** MOs rotate through the unit. Setting `active = 0` removes them from the dropdown while every summary they signed still prints their name. A delete would orphan the FK and break old records.

Seeded on first launch; editable via the "Manage doctors…" dialog reached from the header dropdown.

---

### `templates`

Canned procedure text.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | TEXT NOT NULL | e.g. `Thyroid lobectomy` |
| `body` | TEXT NOT NULL | Multi-line steps |
| `sort_order` | INTEGER | |
| `active` | INTEGER DEFAULT 1 | |

**Templates insert, they don't link.** Selecting a template copies its text into `summaries.procedure_steps`, after which the two are unrelated. Editing a template must never alter an existing summary — a discharge summary is a record of what happened, and retroactive edits would corrupt it.

---

### `attachments`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `summary_id` | INTEGER FK → summaries | `ON DELETE CASCADE` |
| `filename` | TEXT NOT NULL | Original name, for display |
| `stored_path` | TEXT NOT NULL | Relative to the attachments dir |
| `size_bytes` | INTEGER | |
| `added_at` | TEXT | ISO-8601 |

**Files on disk, paths in the DB — never blobs.** Blobs bloat the database file, which slows every query and makes the backup copy expensive. Files live in `%APPDATA%\DischargeSummaries\attachments\<summary_id>\`.

Imports are capped at 5 MB and images are resized on import. A nurse dropping in a 40 MB phone photo is a realistic way to exhaust memory on a 4 GB machine.

---

### `app_meta`

Key/value store for schema version and settings.

| Column | Type |
|---|---|
| `key` | TEXT PK |
| `value` | TEXT |

Holds `schema_version` (drives migrations), `backup_path`, `default_ward`, `last_doctor_id`.

---

## Query patterns

**List pane** — never loads full records:

```sql
SELECT id, patient_name, bht_number, ward, date_discharge
FROM summaries
WHERE deleted_at IS NULL
ORDER BY date_discharge DESC, id DESC
LIMIT 50 OFFSET ?;
```

**Search** — debounced 150ms in the UI, hits both indexes:

```sql
SELECT id, patient_name, bht_number, ward, date_discharge
FROM summaries
WHERE deleted_at IS NULL
  AND (patient_name LIKE ? OR bht_number LIKE ?)
ORDER BY date_discharge DESC
LIMIT 50;
```

**Full record** — only on selection, one summary at a time.

Loading every summary into memory would work today with a few hundred records and degrade badly by year three. The `LIMIT` is not premature optimisation on this hardware.

---

## Migrations

`app_meta.schema_version` gates forward-only migration steps in `app/db/schema.sql`. On launch, compare stored version to code version and apply the gap.

Back up the `.db` before migrating. On this machine there is no other copy.
