"""File handling for attachments — resize, cap, copy to disk. See
docs/decisions.md "Attachments on disk, paths in the database" and
CLAUDE.md hard rule #9 ("Cap attachment imports at 5 MB and resize images
on import").

Uses QImage (already a real, declared, PyInstaller-bundled dependency via
PySide6), not Pillow — Pillow is at most a transitive dependency here
(pulled in by ReportLab), and build.spec explicitly curates what actually
ships, so relying on an undeclared transitive import would be fragile.
QImage(path) also doubles as the "is this actually a readable image"
check: if it loads, resize it; if not, treat the file as a non-image and
copy it through unchanged (PDF, DOCX, etc.).
"""

import shutil
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from app.config import MAX_ATTACHMENT_BYTES, get_attachments_dir

MAX_IMAGE_DIMENSION = 1600


class AttachmentTooLargeError(Exception):
    """Raised when a file, after any resizing, still exceeds
    MAX_ATTACHMENT_BYTES. Caller (the UI) catches this and shows a status
    message — same pattern as PrintUnsupportedError."""


def save_attachment_file(source_path, summary_id):
    """Copies (and resizes, if an image) source_path into the attachments
    dir under a generated name. Returns (stored_relative_path, size_bytes).
    Raises AttachmentTooLargeError if the final file is still over the cap."""
    source_path = Path(source_path)
    dest_dir = get_attachments_dir() / str(summary_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{source_path.suffix.lower()}"
    dest_path = dest_dir / stored_name

    image = QImage(str(source_path))
    if not image.isNull() and (image.width() > MAX_IMAGE_DIMENSION or image.height() > MAX_IMAGE_DIMENSION):
        scaled = image.scaled(
            MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        scaled.save(str(dest_path))
    else:
        shutil.copy2(source_path, dest_path)

    size_bytes = dest_path.stat().st_size
    if size_bytes > MAX_ATTACHMENT_BYTES:
        dest_path.unlink(missing_ok=True)
        raise AttachmentTooLargeError(
            f"{source_path.name} is {size_bytes // 1024} KB, over the {MAX_ATTACHMENT_BYTES // 1024 // 1024} MB limit."
        )

    stored_relative_path = f"{summary_id}/{stored_name}"
    return stored_relative_path, size_bytes


def delete_attachment_file(stored_relative_path):
    """Best-effort disk delete — an already-missing file must never block
    the DB-level remove that always accompanies this call."""
    path = get_attachments_dir() / stored_relative_path
    path.unlink(missing_ok=True)


def format_size(size_bytes):
    """size_bytes -> '245 KB' / '1.2 MB', for display."""
    if size_bytes is None:
        return ""
    if size_bytes < 1024 * 1024:
        return f"{max(1, size_bytes // 1024)} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
