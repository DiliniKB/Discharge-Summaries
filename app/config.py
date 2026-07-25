"""Paths and constants. See docs/deployment.md "Where data lives".

Production default is %APPDATA%\\DischargeSummaries on Windows — the only
platform this ships on (CLAUDE.md). The non-Windows fallback exists purely
for development on this machine; DS_DATA_DIR overrides both, matching
README.md's documented throwaway-DB dev instructions.
"""

import os
from pathlib import Path

APP_NAME = "DischargeSummaries"

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # CLAUDE.md: cap attachment imports at 5 MB


def get_data_dir() -> Path:
    override = os.environ.get("DS_DATA_DIR")
    if override:
        path = Path(override)
    elif os.name == "nt":
        path = Path(os.environ["APPDATA"]) / APP_NAME
    else:
        path = Path.home() / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    return get_data_dir() / "data.db"


def get_attachments_dir() -> Path:
    path = get_data_dir() / "attachments"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_path() -> Path:
    return get_data_dir() / "app.log"
