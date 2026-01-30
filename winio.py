# =========================
# file: pibackuper/winio.py
# =========================
from __future__ import annotations

import threading
from typing import Iterable
from constants import (
    ERROR_IO_PENDING,
    FSCTL_DISMOUNT_VOLUME,
    FSCTL_LOCK_VOLUME,
)
from win_deps import win_modules


def open_disk(path: str, write: bool = False):
    """Open a raw drive."""
    w = win_modules()
    access = w.win32con.GENERIC_READ | (w.win32con.GENERIC_WRITE if write else 0)
    share = w.win32con.FILE_SHARE_READ | w.win32con.FILE_SHARE_WRITE
    flags = w.win32con.FILE_FLAG_SEQUENTIAL_SCAN | (w.win32con.FILE_FLAG_OVERLAPPED if write else 0)
    return w.win32file.CreateFile(path, access, share, None, w.win32con.OPEN_EXISTING, flags, None)


def open_volume(letter: str):
    """Open a logical volume handle (e.g. 'E:')."""
    w = win_modules()
    return w.win32file.CreateFile(
        rf"\\.\{letter}",
        w.win32con.GENERIC_READ | w.win32con.GENERIC_WRITE,
        w.win32con.FILE_SHARE_READ | w.win32con.FILE_SHARE_WRITE,
        None,
        w.win32con.OPEN_EXISTING,
        0,
        None,
    )


def lock_dismount(letters: Iterable[str]):
    """
    Lock + dismount all vol. letters.
    Returns list of handles closed later.
    """
    w = win_modules()
    hs = []
    for l in sorted({x for x in letters if x and x.endswith(":")}):
        h = None
        try:
            h = open_volume(l)
            w.win32file.DeviceIoControl(int(h), FSCTL_LOCK_VOLUME, None, 0)
            w.win32file.DeviceIoControl(int(h), FSCTL_DISMOUNT_VOLUME, None, 0)
            hs.append(h)
        except w.pywintypes.error:
            if h:
                try:
                    w.win32file.CloseHandle(int(h))
                except Exception:
                    pass
            for hh in hs:
                try:
                    w.win32file.CloseHandle(int(hh))
                except Exception:
                    pass
            raise RuntimeError(
                f"Could not lock/dismount {l}. Close Explorer/anything using it and retry."
            )
    return hs


def close_handles(hs) -> None:
    """Close list of win32 handles (best-effort)."""
    w = win_modules()
    for h in hs:
        try:
            w.win32file.CloseHandle(int(h))
        except Exception:
            pass


def write_at_cancel(h, cancel_evt: threading.Event, off: int, data: bytes) -> None:
    """
    Overlapped write with cooperative cancel. Raises InterruptedError if cancelled.
    """
    w = win_modules()
    CancelIoEx = getattr(w.win32file, "CancelIoEx", None)

    ov = w.pywintypes.OVERLAPPED()
    ov.hEvent = w.win32event.CreateEvent(None, True, False, None)
    ov.Offset = off & 0xFFFFFFFF
    ov.OffsetHigh = (off >> 32) & 0xFFFFFFFF

    try:
        try:
            w.win32file.WriteFile(int(h), data, ov)
        except w.pywintypes.error as e:
            if e.winerror != ERROR_IO_PENDING:
                raise

        while True:
            if cancel_evt.is_set():
                if CancelIoEx:
                    try:
                        CancelIoEx(int(h), ov)
                    except Exception:
                        pass
                raise InterruptedError("Cancelled")
            if w.win32event.WaitForSingleObject(ov.hEvent, 200) == w.win32con.WAIT_OBJECT_0:
                break

        w.win32file.GetOverlappedResult(int(h), ov, True)
    finally:
        try:
            w.win32file.CloseHandle(int(ov.hEvent))
        except Exception:
            pass
