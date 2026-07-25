"""Dataclasses mirroring app/db/schema tables. Grown one field-set at a time,
per chunk, rather than speculatively — see docs/schema.md for the full tables.
"""

from dataclasses import dataclass


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
