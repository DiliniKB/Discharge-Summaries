"""Backup on exit — copies data.db to the configured path with a date
stamp. See docs/deployment.md §8: "A single database file on a single
unmirrored HDD in a hospital is the main data-loss risk in this project."
"""

import shutil
from datetime import datetime
from pathlib import Path


def backup_now(db_path, backup_dir):
    """Copies db_path into backup_dir as 'data-YYYY-MM-DD.db'. Returns
    False (never raises) if backup_dir doesn't exist or isn't writable —
    a failed backup must never block the app from closing."""
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    if not db_path.exists():
        return False
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d")
        dest = backup_dir / f"data-{stamp}.db"
        shutil.copy2(db_path, dest)
        return True
    except OSError:
        return False
