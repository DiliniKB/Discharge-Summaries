"""File handling for attachments: resize, cap, copy. See CLAUDE.md hard
rule #9 and docs/decisions.md."""

import pytest
from PySide6.QtGui import QColor, QImage

from app import config
from app.util.attachments import (
    AttachmentMissingError,
    AttachmentOpenUnsupportedError,
    AttachmentTooLargeError,
    MAX_IMAGE_DIMENSION,
    format_size,
    open_attachment_file,
    save_attachment_file,
)


def _make_image(path, width, height):
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor("red"))
    image.save(str(path))


def test_oversized_image_is_resized(isolated_data_dir, tmp_path, qapp):
    source = tmp_path / "photo.png"
    _make_image(source, 3000, 2000)

    stored_relative_path, size_bytes = save_attachment_file(source, summary_id=1)

    dest = config.get_attachments_dir() / stored_relative_path
    assert dest.exists()
    assert size_bytes == dest.stat().st_size

    resized = QImage(str(dest))
    assert resized.width() <= MAX_IMAGE_DIMENSION
    assert resized.height() <= MAX_IMAGE_DIMENSION
    # Aspect ratio preserved: original was 3:2.
    assert resized.width() == MAX_IMAGE_DIMENSION
    assert resized.height() == MAX_IMAGE_DIMENSION * 2 // 3


def test_small_image_is_not_resized(isolated_data_dir, tmp_path, qapp):
    source = tmp_path / "thumb.png"
    _make_image(source, 200, 150)

    stored_relative_path, _size_bytes = save_attachment_file(source, summary_id=1)

    dest = config.get_attachments_dir() / stored_relative_path
    result = QImage(str(dest))
    assert result.width() == 200
    assert result.height() == 150


def test_non_image_file_copies_through_unchanged(isolated_data_dir, tmp_path, qapp):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4 not a real pdf but not an image either")

    stored_relative_path, size_bytes = save_attachment_file(source, summary_id=1)

    dest = config.get_attachments_dir() / stored_relative_path
    assert dest.read_bytes() == source.read_bytes()
    assert size_bytes == source.stat().st_size


def test_file_still_over_cap_raises_and_cleans_up(isolated_data_dir, tmp_path, qapp, monkeypatch):
    monkeypatch.setattr("app.util.attachments.MAX_ATTACHMENT_BYTES", 100)
    source = tmp_path / "big.pdf"
    source.write_bytes(b"x" * 500)

    with pytest.raises(AttachmentTooLargeError):
        save_attachment_file(source, summary_id=1)

    # No orphaned file left behind in the attachments dir.
    leftover = list((config.get_attachments_dir() / "1").glob("*")) if (config.get_attachments_dir() / "1").exists() else []
    assert leftover == []


def test_generated_stored_names_dont_collide(isolated_data_dir, tmp_path, qapp):
    source_a = tmp_path / "a" / "report.pdf"
    source_a.parent.mkdir()
    source_a.write_bytes(b"first report")

    source_b = tmp_path / "b" / "report.pdf"
    source_b.parent.mkdir()
    source_b.write_bytes(b"second report")

    path_a, _ = save_attachment_file(source_a, summary_id=1)
    path_b, _ = save_attachment_file(source_b, summary_id=1)

    assert path_a != path_b
    dest_a = config.get_attachments_dir() / path_a
    dest_b = config.get_attachments_dir() / path_b
    assert dest_a.read_bytes() == b"first report"
    assert dest_b.read_bytes() == b"second report"


def test_open_attachment_file_raises_clear_error_on_non_windows(isolated_data_dir, tmp_path, qapp):
    source = tmp_path / "photo.png"
    _make_image(source, 200, 150)
    stored_relative_path, _size_bytes = save_attachment_file(source, summary_id=1)

    with pytest.raises(AttachmentOpenUnsupportedError):
        open_attachment_file(stored_relative_path)


def test_open_attachment_file_raises_when_missing_from_disk(isolated_data_dir, qapp):
    with pytest.raises(AttachmentMissingError):
        open_attachment_file("1/does-not-exist.png")


def test_format_size():
    assert format_size(500) == "1 KB"
    assert format_size(2048) == "2 KB"
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(int(1.5 * 1024 * 1024)) == "1.5 MB"
    assert format_size(None) == ""
