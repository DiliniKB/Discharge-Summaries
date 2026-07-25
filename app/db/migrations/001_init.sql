-- Initial schema. See docs/schema.md for the reasoning behind every
-- non-obvious column. Forward-only, never edited once shipped —
-- docs/decisions.md "Numbered migration files, not one evolving schema.sql".

CREATE TABLE summaries (
    id                      INTEGER PRIMARY KEY,
    patient_name            TEXT NOT NULL,
    age                     INTEGER,
    sex                     TEXT,
    bht_number              TEXT NOT NULL,          -- not unique: same patient can have multiple admissions
    ward                    TEXT,
    telephone               TEXT,                    -- text, not integer: leading zeros, spaces, +94
    blood_group             TEXT,
    date_admission          TEXT,                    -- ISO-8601 YYYY-MM-DD
    date_surgery            TEXT,
    date_discharge          TEXT,
    procedure_title         TEXT,
    surgical_team           TEXT,
    indication               TEXT,
    procedure_steps          TEXT,
    presenting_complaint     TEXT,
    past_medical_history     TEXT,
    past_surgical_history    TEXT,
    allergies                TEXT,
    examination               TEXT,
    findings                  TEXT,
    management                TEXT,
    histology_report          TEXT,
    created_by                INTEGER REFERENCES doctors(id),
    last_edited_by             INTEGER REFERENCES doctors(id),
    created_at                 TEXT NOT NULL,
    updated_at                 TEXT NOT NULL,
    deleted_at                 TEXT                    -- soft delete; NULL = live
);

CREATE TABLE investigations (
    id          INTEGER PRIMARY KEY,
    summary_id  INTEGER NOT NULL REFERENCES summaries(id) ON DELETE CASCADE,
    label       TEXT NOT NULL,   -- FBS, SCr, AST, Na, K, S Ca, Hb, or ad-hoc
    value       TEXT,            -- TEXT deliberately: lab reports contain "<0.5", "Not done"
    unit        TEXT,
    sort_order  INTEGER
);

CREATE TABLE doctors (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    designation  TEXT,
    active       INTEGER NOT NULL DEFAULT 1,
    sort_order   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE templates (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    body        TEXT NOT NULL,
    sort_order  INTEGER,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE attachments (
    id           INTEGER PRIMARY KEY,
    summary_id   INTEGER NOT NULL REFERENCES summaries(id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,   -- original name, for display
    stored_path  TEXT NOT NULL,   -- relative to the attachments dir
    size_bytes   INTEGER,
    added_at     TEXT NOT NULL
);

CREATE TABLE app_meta (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

CREATE INDEX idx_summaries_bht       ON summaries(bht_number);
CREATE INDEX idx_summaries_name      ON summaries(patient_name);
CREATE INDEX idx_summaries_discharge ON summaries(date_discharge DESC);
