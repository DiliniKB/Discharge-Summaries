"""Entry point. Top-level exception handler: log to file, show a dialog,
never die silently. CLAUDE.md hard rule #8.

Two failure modes are handled, deliberately differently:
1. Startup failures (before the Qt event loop begins) — caught directly
   in _build_main_window(), since sys.excepthook doesn't fire for
   exceptions the interpreter never actually raises past a try/except.
2. Failures once the event loop is running — Qt swallows exceptions
   raised inside slots/callbacks by default (prints to stderr and
   carries on, or silently misbehaves) unless sys.excepthook is
   overridden; installed in _install_excepthook() before app.exec().

_build_main_window() is a separate function (not inlined in main())
specifically so it's callable directly in tests without blocking on the
real event loop via app.exec().
"""

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app import theme
from app.util.logging import setup_logging

logger = logging.getLogger(__name__)


def _show_error_dialog(exc_value):
    box = QMessageBox()
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle("Discharge Summaries — Unexpected Error")
    box.setText("Something went wrong and has been logged.")
    box.setInformativeText(str(exc_value))
    box.setStandardButtons(QMessageBox.Ok)
    box.exec()


def _install_excepthook():
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
        _show_error_dialog(exc_value)

    sys.excepthook = handle_exception


def _build_main_window(app):
    """Returns the constructed MainWindow, or None if startup failed (in
    which case the error is already logged and shown)."""
    try:
        theme.apply_theme(app)
        from app.ui.main_window import MainWindow  # deferred: any import-time failure here must be caught too

        return MainWindow()
    except Exception:
        logger.critical("Failed during startup", exc_info=True)
        _show_error_dialog(sys.exc_info()[1])
        return None


def main():
    log_path = setup_logging()
    logger.info("Starting Discharge Summaries")

    app = QApplication(sys.argv)
    _install_excepthook()

    win = _build_main_window(app)
    if win is None:
        sys.exit(1)

    win.showMaximized()
    exit_code = app.exec()
    logger.info("Exiting Discharge Summaries")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
