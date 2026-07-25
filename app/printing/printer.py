"""Print dispatch. See docs/print-layout.md "Printing".

os.startfile with the "print" verb hands the file to the shell, which
uses the default PDF handler and default printer. No printer driver
code, no dialog to maintain. Windows-only — fine, the target is one
Windows laptop (CLAUDE.md).
"""

import os


class PrintUnsupportedError(RuntimeError):
    """Raised when attempting to print on a non-Windows platform. The
    shipped app only ever runs on Windows (CLAUDE.md) — this exists so
    dev/test runs on other platforms fail with a clear message instead
    of a confusing AttributeError deep in os.startfile."""


def print_pdf(pdf_path):
    if not hasattr(os, "startfile"):
        raise PrintUnsupportedError(
            "Printing requires os.startfile, which only exists on Windows. "
            "This is expected when running on a dev machine — the shipped "
            "app is Windows-only."
        )
    os.startfile(str(pdf_path), "print")
