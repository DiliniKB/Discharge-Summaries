# Deployment

Building, transferring, and installing on the ward laptop. No installer, no admin rights, no Python on the target machine.

**Target:** Acer Aspire A515-53 · Windows 10 Home 1809 · 4 GB RAM · 932 GB HDD · offline.

---

## 1. Build

On a Windows machine with the project set up:

```bash
.venv\Scripts\activate
pyinstaller build.spec
```

Output: `dist/DischargeSummaries/` containing `DischargeSummaries.exe` plus the bundled Python runtime and DLLs.

**This is a folder, not a single exe.** That is deliberate — see `decisions.md`. Do not switch to `--onefile` to make the transfer tidier; it costs 5–10 seconds of cold start on every launch on the target's spinning disk.

Verify before shipping:

```bash
dist\DischargeSummaries\DischargeSummaries.exe
```

Check that it launches, creates the database, and prints a test card.

---

## 2. Package

```bash
cd dist
tar -a -c -f DischargeSummaries-v1.0.0.zip DischargeSummaries
```

Or right-click the folder → Send to → Compressed folder.

Name the zip with a version. When you send an update, staff need to tell which one they have.

---

## 3. Transfer

Google Drive, or a USB stick if the ward machine has no reliable connection.

**Zip it — don't upload a bare `.exe`.** Drive scans executables and sometimes blocks them outright. A zip goes through.

If Drive still refuses, a password-protected zip works, but then you're on the phone reading out a password. USB is usually faster.

---

## 4. First install on the ward laptop

1. Download the zip.
2. Extract to `C:\DischargeSummaries\` — **not** Program Files, which needs admin rights. Not the Desktop, where it gets dragged around.
3. Open the folder and run `DischargeSummaries.exe`.
4. Right-click the exe → Send to → Desktop (create shortcut).

### The SmartScreen warning

An unsigned executable downloaded from the internet triggers:

> **Windows protected your PC**
> Microsoft Defender SmartScreen prevented an unrecognised app from starting.

Click **More info**, then **Run anyway**.

**Tell whoever receives the file to expect this**, or they will assume the app is broken or infected and stop. This is not optional — it is the single most common reason a handover fails.

Chrome may also warn on download ("this file isn't commonly downloaded"). Keep it.

The warning appears on first run only. Code signing would remove it, but a certificate costs more than this project is worth.

---

## 5. First launch

On first run the app:

- Creates `%APPDATA%\DischargeSummaries\` (`C:\Users\<user>\AppData\Roaming\DischargeSummaries\`)
- Creates `data.db` and applies the schema
- Seeds the doctor list
- Seeds the procedure templates
- Writes `app.log`

Then, in the app:

1. **Manage doctors** — header dropdown → *Manage doctors…*. Correct names and designations.
2. **Set the backup path** — Settings. A mapped network drive or a USB stick. This is the only protection against the single unmirrored HDD.
3. **Print a test card** with fictional data and compare it against a real green form.

---

## 6. Where data lives

```
%APPDATA%\DischargeSummaries\
├── data.db              the database
├── data.db-wal          WAL journal
├── data.db-shm          shared memory
├── attachments\         scanned reports, by summary id
└── app.log              rotating log
```

**Deliberately separate from the application folder.** Updating means replacing `C:\DischargeSummaries\` — if the database lived there, an update would destroy every record.

---

## 7. Updating

1. Close the app.
2. **Copy `%APPDATA%\DischargeSummaries\data.db` somewhere safe.** Do this even though the app folder is separate. It costs ten seconds.
3. Delete `C:\DischargeSummaries\`.
4. Extract the new zip in its place.
5. Launch. Migrations apply automatically.

The desktop shortcut survives if the folder name is unchanged.

---

## 8. Backup

Configured in Settings. On exit, the app copies `data.db` to the backup path with a date stamp.

**A single database file on a single unmirrored HDD in a hospital is the main data-loss risk in this project.** Configure the backup on day one. Verify occasionally that files are actually appearing — a backup nobody checks is not a backup.

If the ward has no network share, a dedicated USB stick left in the machine works. Ugly, effective.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Windows protected your PC" | Unsigned exe, first run | More info → Run anyway |
| Won't start, no window | Missing DLL or corrupt extract | Check `app.log`. Re-extract the zip. |
| Very slow first launch | Cold disk cache | Normal on this machine. Second launch is faster. Confirm the build is `--onedir`. |
| "Database is locked" | A second instance is running | Check Task Manager for a stray `DischargeSummaries.exe` |
| Print does nothing | No default printer set | Windows Settings → Printers → set a default |
| Print preview blank | ReportLab failed | Check `app.log` |
| Records missing after update | App folder was used for data | Recover from backup. Confirm `%APPDATA%` path in `config.py`. |

`app.log` in `%APPDATA%\DischargeSummaries\` is the first place to look for anything not on this list.

---

## 10. Handover checklist

- [ ] App extracted to `C:\DischargeSummaries\`
- [ ] Desktop shortcut created
- [ ] SmartScreen warning cleared once
- [ ] Doctor list corrected
- [ ] Backup path set and verified writing
- [ ] Test card printed and checked against a paper form
- [ ] `user-guide.md` printed and left with the machine
- [ ] Named contact for problems, with the version number written down
