"""Dialog sizing clamped to the actual screen — the bug this exists to
prevent: a fixed height taller than the target 1366x768 Windows screen
pushes a dialog's bottom button row off-screen."""

from PySide6.QtWidgets import QDialog

from app.util.screen import clamped_dialog_size


def test_size_smaller_than_screen_is_unchanged(qapp):
    dialog = QDialog()
    available = dialog.screen().availableGeometry()

    width, height = clamped_dialog_size(dialog, 400, 300)

    assert (width, height) == (400, 300)
    assert width <= available.width()
    assert height <= available.height()


def test_size_taller_than_screen_is_clamped(qapp):
    dialog = QDialog()
    available = dialog.screen().availableGeometry()

    width, height = clamped_dialog_size(dialog, 700, available.height() + 500)

    assert height < available.height() + 500
    assert height <= available.height()
    assert width == 700


def test_size_wider_than_screen_is_clamped(qapp):
    dialog = QDialog()
    available = dialog.screen().availableGeometry()

    width, height = clamped_dialog_size(dialog, available.width() + 500, 400)

    assert width < available.width() + 500
    assert width <= available.width()
    assert height == 400
