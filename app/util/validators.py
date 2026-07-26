"""Cross-field validation — warns, never blocks (docs/decisions.md, same
"warn but permit" precedent as duplicate BHT). A discharge summary with
an unusual-but-correct date order must still be saveable immediately.
"""


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
