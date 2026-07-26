"""Dialog sizing that respects the actual screen, not just a fixed pixel
guess. The target laptop is 1366×768 (CLAUDE.md); a dialog whose fixed
height exceeds the screen's *available* area (Windows' taskbar eats a
real chunk of that 768) gets its bottom row pushed off-screen —
unreachable without dragging the window up first. Confirmed on the
target OS, not just theoretical: Print Preview and the Full View dialog
both cut off their bottom button/Close row on Windows despite looking
fine on a taller dev-machine screen.
"""

from PySide6.QtWidgets import QApplication

# Taskbar + title bar + a little slack — not exact on every Windows
# theme/DPI setting, but comfortably enough to keep the bottom row
# reachable rather than exactly on the pixel.
_HEIGHT_MARGIN = 80
_WIDTH_MARGIN = 40


def clamped_dialog_size(dialog, width, height):
    """Returns (width, height) capped to the dialog's screen's available
    geometry. Call before the first show()/resize() so the dialog never
    opens taller than the screen has room for."""
    screen = dialog.screen() or QApplication.primaryScreen()
    available = screen.availableGeometry()
    return min(width, available.width() - _WIDTH_MARGIN), min(height, available.height() - _HEIGHT_MARGIN)
