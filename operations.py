# =========================
# file: pibackuper/operations.py
# =========================
from __future__ import annotations

import gzip
import os
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from constants import CHUNK
from disks import DiskInfo
from streaming import Progress, stream_copy
from utils import (
    atomic_replace,
    disk_rescan,
    make_hasher,
    read_sidecar,
    sidecar,
    write_sidecar,
)
from win_deps import win_modules
from winio import close_handles, lock_dismount, open_disk, write_at_cancel


ProgressCb = Callable[[Progress], None]


@dataclass(frozen=True)
class BackupOptions:
    compress: bool
    hash_algo: str  # "sha256" | "md5" | "none"


def backup_disk_to_image(
    *,
    disk: DiskInfo,
    out_path: str,
    opts: BackupOptions,
    cancel_evt: threading.Event,
    progress_cb: ProgressCb | None = None,
) -> None:
    """
    Backup raw disk to image. Writes to temp '.partial' then renames.
    """
    w = win_modules()
    rd = raw = gz = None
    tmp = out_path + ".partial"

    try:
        try:
            os.remove(tmp)
        except Exception:
            pass

        algo = (opts.hash_algo or "none").lower()
        hasher = make_hasher(algo)

        rd = open_disk(disk.phys, write=False)
        raw = open(tmp, "wb", buffering=16 * 1024 * 1024)
        gz = gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=1) if opts.compress else raw

        remaining = disk.size

        def read_fn() -> bytes:
            nonlocal remaining
            if remaining <= 0:
                return b""
            if cancel_evt.is_set():
                raise InterruptedError("Cancelled")
            to_read = min(CHUNK, remaining)
            _hr, data = w.win32file.ReadFile(int(rd), to_read)
            remaining -= len(data)
            return data

        def write_fn(b: bytes) -> None:
            gz.write(b)

        stream_copy(
            read_fn=read_fn,
            write_fn=write_fn,
            total=disk.size,
            cancel_evt=cancel_evt,
            hasher=hasher,
            progress_fn=progress_cb,
        )

        try:
            gz.close()
        except Exception:
            pass
        try:
            raw.flush()
            os.fsync(raw.fileno())
        except Exception:
            pass

        if cancel_evt.is_set():
            try:
                os.remove(tmp)
            except Exception:
                pass
            raise InterruptedError("Cancelled")

        atomic_replace(tmp, out_path)

        if hasher:
            write_sidecar(sidecar(out_path), algo, disk.size, hasher.hexdigest())

    finally:
        try:
            if gz and gz is not raw:
                gz.close()
        except Exception:
            pass
        try:
            if raw:
                raw.close()
        except Exception:
            pass
        try:
            if rd:
                w.win32file.CloseHandle(int(rd))
        except Exception:
            pass


def restore_image_to_disk(
    *,
    disk: DiskInfo,
    img_path: str,
    cancel_evt: threading.Event,
    progress_cb: ProgressCb | None = None,
) -> None:
    """
    Restore image (optionally .gz) to raw disk. Locks/dismounts volumes first.
    Validates against hash file if present.
    """
    w = win_modules()
    hs = []
    dst = src = None

    meta = read_sidecar(sidecar(img_path))
    hasher = make_hasher(meta[0]) if meta else None
    expect_bytes = meta[1] if meta else None
    expect_hex = meta[2] if meta else None

    try:
        hs = lock_dismount(disk.letters)
        dst = open_disk(disk.phys, write=True)
        src = gzip.open(img_path, "rb") if img_path.lower().endswith(".gz") else open(img_path, "rb")

        written = 0
        off = 0
        total_prog = int(expect_bytes) if expect_bytes else int(disk.size)

        def read_fn() -> bytes:
            if cancel_evt.is_set():
                raise InterruptedError("Cancelled")
            return src.read(CHUNK)

        def limit_fn(n: int) -> None:
            nonlocal written
            if written + n > disk.size:
                raise RuntimeError("Image larger than target device.")

        def write_fn(b: bytes) -> None:
            nonlocal written, off
            write_at_cancel(dst, cancel_evt, off, b)
            off += len(b)
            written += len(b)

        stream_copy(
            read_fn=read_fn,
            write_fn=write_fn,
            total=total_prog,
            cancel_evt=cancel_evt,
            hasher=hasher,
            limit_fn=limit_fn,
            progress_fn=progress_cb,
        )

        try:
            w.win32file.FlushFileBuffers(int(dst))
        except Exception:
            pass

        if cancel_evt.is_set():
            raise InterruptedError("Cancelled")

        if hasher and expect_hex:
            if expect_bytes is not None and written != expect_bytes:
                raise RuntimeError(f"Size mismatch (expected {expect_bytes}, got {written})")
            if hasher.hexdigest().lower() != expect_hex.lower():
                raise RuntimeError("Hash verify FAILED")

        disk_rescan()

    finally:
        try:
            if src:
                src.close()
        except Exception:
            pass
        try:
            if dst:
                w.win32file.CloseHandle(int(dst))
        except Exception:
            pass
        close_handles(hs)


def clone_disk_to_disk(
    *,
    src_disk: DiskInfo,
    dst_disk: DiskInfo,
    cancel_evt: threading.Event,
    progress_cb: ProgressCb | None = None,
) -> None:
    """
    Clone disk A to disk B (erases B). Locks/dismounts B volumes first.
    """
    w = win_modules()
    hs = []
    src = dst = None

    if dst_disk.size < src_disk.size:
        raise RuntimeError("Target device is smaller than source.")

    try:
        hs = lock_dismount(dst_disk.letters)
        src = open_disk(src_disk.phys, write=False)
        dst = open_disk(dst_disk.phys, write=True)

        remaining = src_disk.size
        off = 0

        def read_fn() -> bytes:
            nonlocal remaining
            if remaining <= 0:
                return b""
            if cancel_evt.is_set():
                raise InterruptedError("Cancelled")
            to_read = min(CHUNK, remaining)
            _hr, data = w.win32file.ReadFile(int(src), to_read)
            remaining -= len(data)
            return data

        def write_fn(buf: bytes) -> None:
            nonlocal off
            write_at_cancel(dst, cancel_evt, off, buf)
            off += len(buf)

        stream_copy(
            read_fn=read_fn,
            write_fn=write_fn,
            total=src_disk.size,
            cancel_evt=cancel_evt,
            progress_fn=progress_cb,
        )

        try:
            w.win32file.FlushFileBuffers(int(dst))
        except Exception:
            pass

        if cancel_evt.is_set():
            raise InterruptedError("Cancelled")

        disk_rescan()

    finally:
        try:
            if src:
                w.win32file.CloseHandle(int(src))
        except Exception:
            pass
        try:
            if dst:
                w.win32file.CloseHandle(int(dst))
        except Exception:
            pass
        close_handles(hs)

