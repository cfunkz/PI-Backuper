# =========================
# file: pibackuper/constants.py
# =========================
from __future__ import annotations

__title__ = "PI-Backuper"
__version__ = "1.0.3"
__author__ = "cFunkz"
__license__ = "MIT"
__url__ = "https://github.com/cfunkz/PI-Backuper"
__description__ = "Win11 raw USB/SD backup/restore/clone."

CHUNK = 8 * 1024 * 1024
QUEUE_MAX = 16
ICON_FILE = "favicon.ico"

FSCTL_LOCK_VOLUME = 0x00090018
FSCTL_DISMOUNT_VOLUME = 0x00090020

ERROR_IO_PENDING = 997