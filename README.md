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

![Main Window](images/main.png)

---

## Requirements

- Windows 10 / 11
- **Administrator privileges**
- USB SD card reader

---

## Usage

1. Download the latest release from **Releases**
2. Run `PI-Imager.exe` (UAC prompt required)
3. Select removable device
4. Backup or restore

⚠ **Restore will erase the entire device.**

---

## Build (from source)

```powershell
pip install -r requirements.txt
python -m pywin32_postinstall

pyinstaller --onefile --noconsole --uac-admin --name PI-Imager ^
  --icon favicon.ico ^
  --add-data "favicon.ico;." ^
  --hidden-import=win32file ^
  --hidden-import=win32con ^
  --hidden-import=pythoncom ^
  --hidden-import=wmi ^
  main.py
```