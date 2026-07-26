"""General adult reference ranges for the 7 standard investigations — a
prompt to double-check an unusual value, not a diagnosis. Same units
already used by STANDARD_ANALYTES (app/db/summaries.py). Hb in particular
is genuinely sex-dependent in real practice; one unisex range here is a
deliberate, disclosed simplification, not a claim of precision
(docs/decisions.md).

investigations.value is TEXT, not REAL, because real lab results include
non-numeric entries like "<0.5" or "Not done" (docs/decisions.md) — those
never get flagged here, since there's nothing numeric to compare.
"""

NORMAL_RANGES = {
    "FBS": (70, 100),     # mg/dL, fasting
    "SCr": (60, 110),     # µmol/L
    "AST": (10, 40),      # U/L
    "Na": (135, 145),     # mmol/L
    "K": (3.5, 5.1),      # mmol/L
    "S Ca": (2.1, 2.6),   # mmol/L, corrected calcium
    "Hb": (12, 17),       # g/dL — unisex approximation
}


def is_abnormal(label, value_text):
    """True if value_text is a plain number outside the normal range for
    label. False for an unknown label, a blank value, or text that
    doesn't parse as a plain float — never raises."""
    bounds = NORMAL_RANGES.get(label)
    if bounds is None or not value_text:
        return False
    try:
        value = float(value_text)
    except ValueError:
        return False
    low, high = bounds
    return value < low or value > high
