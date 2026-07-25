"""Attachments section: collapsed by default, empty-state shell (no real
file handling yet — deliberately deferred, see the section's own docstring)."""

from app.ui.sections.attachments import AttachmentsSection


def test_starts_collapsed_with_zero_files():
    sec = AttachmentsSection()
    sec.show()

    assert sec._title.text() == "ATTACHMENTS"
    assert sec.expanded is False
    assert sec.body.isVisible() is False
    assert sec._counter.text() == "0 files"
    assert sec.add_file_button.text() == "+ Add File"


def test_add_file_is_a_safe_shell():
    sec = AttachmentsSection()
    sec.show()
    sec.add_file_button.click()  # no real file handling yet — must not raise
    assert sec._counter.text() == "0 files"


def test_clicking_the_header_expands_it():
    sec = AttachmentsSection()
    sec.show()
    sec._toggle()
    assert sec.expanded is True
    assert sec.body.isVisible() is True


def test_wired_into_the_real_editor_collapsed(isolated_data_dir):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    assert win.editor.attachments_section is not None
    assert win.editor.attachments_section.expanded is False
    win.close()
