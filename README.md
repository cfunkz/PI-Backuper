<p align="center">
  <img src="favicon.ico" width="96" height="96" alt="PI-Backuper logo">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/GUI-Tkinter-blue?style=flat-square" alt="Tkinter">
  <img src="https://img.shields.io/badge/Built%20With-PyInstaller-3C873A?style=flat-square" alt="PyInstaller">
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=flat-square&logo=windows&logoColor=white" alt="Windows">
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/cfunkz/PI-Backuper?style=flat-square" alt="Stars">
  <img src="https://img.shields.io/github/issues/cfunkz/PI-Backuper?style=flat-square" alt="Open Issues">
  <img src="https://img.shields.io/github/release/cfunkz/PI-Backuper?style=flat-square" alt="Latest Release">
  <img src="https://img.shields.io/github/downloads/cfunkz/PI-Backuper/total?style=flat-square" alt="Downloads">
</p>

<p align="center">
  <a href="https://ko-fi.com/cfunkz81112">
    <strong>Buy me a coffee</strong>
  </a>
</p>

# PI-Backuper

Removable media backup & restore tool for **Windows**.

---

## Features

- Backup & restore full SD cards (raw disk imaging)
- Detects **removable USB devices only**
- Optional gzip compression
- SHA256 or MD5 hashing
- Stable high-speed pipeline (reader + writer threads)
- Progress bar with speed & ETA
- Clone to another device
- One-click portable `.exe` (no Python required)

---

## Screenshots

<img width="850" height="528" alt="image" src="https://github.com/user-attachments/assets/7f8e7f03-c2aa-4733-8d75-8ac1b64c2840" />

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

- SD cards (Raspberry Pi OS, Ubuntu, LibreELEC, custom images)
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
  --hidden-import=pythoncom ^
  --hidden-import=win32file ^
  --hidden-import=win32con ^
  --hidden-import=win32event ^
  --hidden-import=win32api ^
  --hidden-import=wmi ^
  main.py
```

## Trademark Notice

Raspberry Pi is a trademark of the Raspberry Pi Foundation.  
PI-Backuper is an independent, community-developed project and is **not affiliated with or endorsed by** the Raspberry Pi Foundation.
