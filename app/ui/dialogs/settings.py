"""Settings dialog — backup path. See docs/ui-spec.md screen inventory,
docs/deployment.md §8.

Printer default isn't here: docs/decisions.md already settled that
printing goes through os.startfile's default handler — printer selection
is OS-level, not something this app configures. Doctor list isn't
duplicated here either — docs/user-guide.md describes that as its own
"Manage doctors…" dialog, reached from the header dropdown, not Settings.
"""

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import config, theme
from app.db import app_meta
from app.ui.widgets.labeled import LabeledField
from app.util import backup as backup_util

BACKUP_PATH_KEY = "backup_path"


class SettingsDialog(QDialog):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("Settings")
        self.resize(480, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING, theme.SECTION_PADDING
        )
        layout.setSpacing(theme.FIELD_GAP)

        note = QLabel(
            "A single database file on one unmirrored drive is the main data-loss risk. "
            "Configure a backup path — a mapped network drive or a USB stick."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        path_container = QWidget()
        path_row = QHBoxLayout(path_container)
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(theme.FIELD_GAP)

        self.path_input = QLineEdit()
        self.path_input.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        self.path_input.setText(app_meta.get(self._conn, BACKUP_PATH_KEY, "") or "")
        path_row.addWidget(self.path_input, stretch=1)

        browse_button = QPushButton("Browse…")
        browse_button.setObjectName("Secondary")
        browse_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        browse_button.clicked.connect(self._on_browse)
        path_row.addWidget(browse_button)

        layout.addWidget(LabeledField("Backup Path", path_container))

        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        layout.addWidget(self.status_label)

        layout.addStretch()

        button_row = QHBoxLayout()
        button_row.setSpacing(theme.FIELD_GAP)

        backup_now_button = QPushButton("Back Up Now")
        backup_now_button.setObjectName("Secondary")
        backup_now_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        backup_now_button.clicked.connect(self._on_backup_now)
        button_row.addWidget(backup_now_button)
        button_row.addStretch()

        done_button = QPushButton("Done")
        done_button.setObjectName("Primary")
        done_button.setMinimumHeight(theme.INPUT_HEIGHT_PX)
        done_button.clicked.connect(self._on_done)
        button_row.addWidget(done_button)
        layout.addLayout(button_row)

    def _on_browse(self):
        directory = QFileDialog.getExistingDirectory(self, "Choose backup folder", self.path_input.text())
        if directory:
            self.path_input.setText(directory)

    def _on_backup_now(self):
        path = self.path_input.text().strip()
        if not path:
            self.status_label.setText("Set a backup path first.")
            return
        ok = backup_util.backup_now(config.get_db_path(), path)
        self.status_label.setText("Backed up." if ok else "Backup failed — check the path is writable.")

    def _on_done(self):
        app_meta.set(self._conn, BACKUP_PATH_KEY, self.path_input.text().strip())
        self.accept()
