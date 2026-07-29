"""Field-level and cross-field validation.

Two different enforcement levels live here, deliberately: date-order
warns but never blocks (below) — an unusual-but-correct date order must
still be saveable immediately. Name/Telephone/BHT format (this section)
actually BLOCK the save for that one field — a real, requested departure
from this app's usual "warn, don't block" precedent (docs/decisions.md),
not an oversight. Blocking is per-field, not per-record: an invalid BHT
doesn't stop Name or any other field on the same summary from
autosaving independently, matching the app's existing per-field
autosave-on-blur architecture (CLAUDE.md hard rule #7).
"""

import re

# Sri Lankan local number: exactly 10 digits, starting with 0 — e.g.
# 0771234567.
_TELEPHONE_PATTERN = re.compile(r"^0\d{9}$")

# "number-year" per the ward's own convention — one or more digits, a
# literal hyphen, then a 4-digit year, e.g. 12345-2026.
_BHT_PATTERN = re.compile(r"^\d+-\d{4}$")


def validate_name(name):
    """Required — a blank (or whitespace-only) name is invalid."""
    return bool((name or "").strip())


def validate_telephone(telephone):
    """Required — must be a 10-digit number starting with 0."""
    return bool(_TELEPHONE_PATTERN.match((telephone or "").strip()))


def validate_bht(bht_number):
    """Required — must match number-year, e.g. 12345-2026."""
    return bool(_BHT_PATTERN.match((bht_number or "").strip()))


def validate_date_order(date_admission, date_surgery, date_discharge):
    """Returns human-readable warnings for any pair that's chronologically
    out of order. ISO YYYY-MM-DD strings compare correctly as plain text
    (docs/schema.md) — no date parsing needed. A pair is only checked
    when both sides are filled; a blank date is never itself a warning."""
    warnings = []
    if date_admission and date_surgery and date_surgery < date_admission:
        warnings.append("Surgery date is before Admission date.")
    if date_surgery and date_discharge and date_discharge < date_surgery:
        warnings.append("Discharge date is before Surgery date.")
    if date_admission and date_discharge and date_discharge < date_admission:
        warnings.append("Discharge date is before Admission date.")
    return warnings
