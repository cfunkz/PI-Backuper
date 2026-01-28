# PI-Backuper

Raspberry Pi SD card backup & restore tool for **Windows**.

---

## Features

- Backup & restore full SD cards (raw disk imaging)
- Detects **removable USB devices only**
- Optional gzip compression
- SHA256 or MD5 hashing
- Stable high-speed pipeline (reader + writer threads)
- Progress bar with speed & ETA
- Safe rollback on error
- One-click portable `.exe` (no Python required)

---

## Screenshots

<img width="819" height="476" alt="image" src="https://github.com/user-attachments/assets/4c8f506e-fc36-493a-8011-555b7442eb55" />

---

## Requirements

- Windows 10 / 11
- **Administrator privileges**
- USB SD card reader

---

## What It Can Back Up

PI-Backuper performs **raw, full-device imaging**.  
It reads the entire removable device **sector-by-sector**, not files.

This means it can back up **any removable USB media**, including:

- Raspberry Pi SD cards (Raspberry Pi OS, Ubuntu, LibreELEC, custom images)
- Other SBC / embedded Linux SD cards
- USB flash drives (FAT32, exFAT, NTFS, unknown filesystems)
- External USB HDDs / SSDs (full disk, all partitions)
- Bootable installers and recovery media
- Encrypted or unsupported filesystems (data is copied as-is)

PI-Backuper does **not** depend on the filesystem or OS on the device.  
If Windows can see it as a **removable USB disk**, it can be backed up.

⚠ Internal system drives are intentionally **not supported** for safety.

---

## Usage

1. Download the latest release from **Releases**
2. Run `PI-Backuper.exe` (UAC prompt required)
3. Select removable device
4. Backup or restore

⚠ **Restore will erase the entire device.**

---

## Build (from source)

```powershell
pip install -r requirements.txt

pyinstaller --onefile --noconsole --uac-admin --name PI-Backuper ^
  --icon favicon.ico ^
  --add-data "favicon.ico;." ^
  --hidden-import=win32file ^
  --hidden-import=win32con ^
  --hidden-import=pythoncom ^
  --hidden-import=wmi ^
  main.py
```
