"""Dataclasses mirroring app/db/schema tables. Grown one field-set at a time,
per chunk, rather than speculatively — see docs/schema.md for the full tables.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Doctor:
    id: int
    name: str
    designation: str
    active: bool = True
    sort_order: int = 0

    @property
    def display_name(self) -> str:
        return f"{self.name} — {self.designation}" if self.designation else self.name


@dataclass
class Template:
    id: int
    name: str
    body: str
    sort_order: int = 0
    active: bool = True


@dataclass
class Attachment:
    id: int
    summary_id: int
    filename: str
    stored_path: str
    size_bytes: int
    added_at: str


@dataclass
class Summary:
    """Mirrors the summaries table exactly — see docs/schema.md. id=None
    means not yet saved (a blank "+ New Card" that hasn't hit the DB)."""

    id: Optional[int] = None
    patient_name: str = ""
    age: Optional[int] = None
    sex: str = ""
    bht_number: str = ""
    ward: str = ""
    telephone: str = ""
    blood_group: str = ""
    date_admission: str = ""
    date_surgery: str = ""
    date_discharge: str = ""
    procedure_title: str = ""
    surgical_team: str = ""
    indication: str = ""
    procedure_steps: str = ""
    presenting_complaint: str = ""
    past_medical_history: str = ""
    past_surgical_history: str = ""
    allergies: str = ""
    examination: str = ""
    findings: str = ""
    management: str = ""
    histology_report: str = ""
    created_by: Optional[int] = None
    last_edited_by: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    deleted_at: Optional[str] = None
