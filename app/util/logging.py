"""Logging setup — rotating file handler. See docs/deployment.md "Where
data lives" (app.log) and CLAUDE.md hard rule #8: top-level exception
handler logs to file, shows a dialog, never dies silently.
"""

import logging
import logging.handlers

from app import config


def setup_logging():
    """Call once, at startup. Returns the log file path."""
    log_path = config.get_log_path()
    handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return log_path
