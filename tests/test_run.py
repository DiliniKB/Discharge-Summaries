"""run.py — top-level exception handler + logging setup."""

import logging
import sys

from PySide6.QtWidgets import QMessageBox

from app import config
from app.util.logging import setup_logging


def test_setup_logging_writes_to_the_configured_log_path(isolated_data_dir):
    log_path = setup_logging()
    assert log_path == config.get_log_path()
    logging.getLogger("test").info("a real test log line")
    for h in logging.getLogger().handlers:
        h.flush()
    assert log_path.exists()
    assert "a real test log line" in log_path.read_text()


def test_build_main_window_succeeds(isolated_data_dir, qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: None)

    import run as run_module

    win = run_module._build_main_window(qapp)
    assert win is not None
    assert hasattr(win, "editor") and hasattr(win, "patient_list")
    win.close()


def test_build_main_window_returns_none_and_logs_critical_on_startup_failure(isolated_data_dir, qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: None)

    import app.ui.main_window as main_window_module
    import run as run_module

    class _BrokenMainWindow:
        def __init__(self):
            raise RuntimeError("simulated startup failure")

    monkeypatch.setattr(main_window_module, "MainWindow", _BrokenMainWindow)

    logged_critical = {"count": 0}
    original_critical = run_module.logger.critical

    def counting_critical(*args, **kwargs):
        logged_critical["count"] += 1
        return original_critical(*args, **kwargs)

    monkeypatch.setattr(run_module.logger, "critical", counting_critical)

    result = run_module._build_main_window(qapp)
    assert result is None, "returns None instead of propagating the crash"
    assert logged_critical["count"] == 1


def test_excepthook_logs_and_shows_dialog_for_real_exceptions(isolated_data_dir, qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: None)

    import run as run_module

    run_module._install_excepthook()
    assert sys.excepthook is not sys.__excepthook__

    dialog_shown = {"count": 0}
    monkeypatch.setattr(
        run_module, "_show_error_dialog", lambda exc_value: dialog_shown.__setitem__("count", dialog_shown["count"] + 1)
    )

    logged_critical = {"count": 0}
    monkeypatch.setattr(
        run_module.logger, "critical", lambda *a, **k: logged_critical.__setitem__("count", logged_critical["count"] + 1)
    )

    try:
        raise ValueError("simulated bug inside a Qt slot")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    assert logged_critical["count"] == 1
    assert dialog_shown["count"] == 1


def test_excepthook_ignores_keyboard_interrupt(isolated_data_dir, qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: None)

    import run as run_module

    run_module._install_excepthook()

    dialog_shown = {"count": 0}
    monkeypatch.setattr(
        run_module, "_show_error_dialog", lambda exc_value: dialog_shown.__setitem__("count", dialog_shown["count"] + 1)
    )
    logged_critical = {"count": 0}
    monkeypatch.setattr(
        run_module.logger, "critical", lambda *a, **k: logged_critical.__setitem__("count", logged_critical["count"] + 1)
    )

    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        exc_info = sys.exc_info()
        # Suppress the default handler's stderr spam for this simulated interrupt.
        monkeypatch.setattr(sys, "__excepthook__", lambda *a: None)
        sys.excepthook(*exc_info)

    assert logged_critical["count"] == 0, "KeyboardInterrupt doesn't trigger the critical-log path"
    assert dialog_shown["count"] == 0, "KeyboardInterrupt doesn't trigger the error dialog"
