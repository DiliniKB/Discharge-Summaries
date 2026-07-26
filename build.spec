# PyInstaller spec — --onedir, never --onefile. See docs/decisions.md.
#
# Run on Windows (this cannot cross-compile from macOS/Linux):
#   pyinstaller build.spec
#
# Output: dist/DischargeSummaries/DischargeSummaries.exe

import os

block_cipher = None

# Migration .sql files aren't imported Python code, so PyInstaller won't
# find them on its own — sqlite3 needs them on disk at runtime to build a
# fresh database or migrate an existing one. Bundle every numbered
# migration file, not just the current one — app/db/connection.py replays
# whichever ones a given install hasn't applied yet.
datas = []
migrations_dir = os.path.join("app", "db", "migrations")
if os.path.isdir(migrations_dir):
    for filename in os.listdir(migrations_dir):
        if filename.endswith(".sql"):
            datas.append((os.path.join(migrations_dir, filename), migrations_dir))

# app/config.py's get_app_icon_path() loads this at runtime (window/
# taskbar icon) — bundled at the same relative path so that resolution,
# unchanged, still finds it inside the --onedir folder.
if os.path.isfile(os.path.join("assets", "app_icon.ico")):
    datas.append((os.path.join("assets", "app_icon.ico"), "assets"))

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # PySide6 (QtCore/QtGui/QtWidgets) + ReportLab only (CLAUDE.md).
        # Trim anything PyInstaller pulls in speculatively that this app
        # never imports — this app touches no network, no SQL bindings
        # beyond stdlib sqlite3, no QML, no embedded browser.
        "matplotlib",
        "numpy",
        "pandas",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "test",
        "unittest",
        "PySide6.QtNetwork",
        "PySide6.QtSql",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtBluetooth",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DischargeSummaries",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX compression costs startup time unpacking; not worth it here.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # The .exe's own icon — what shows on the desktop shortcut, taskbar
    # (before any window is open), and Explorer. app/config.py's
    # get_app_icon_path() sets the same file as the window icon once a
    # window exists; this is what's visible before that.
    icon=os.path.join("assets", "app_icon.ico") if os.path.isfile(os.path.join("assets", "app_icon.ico")) else None,
)

# --onedir: a folder, not a single exe. See docs/decisions.md.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DischargeSummaries",
)
