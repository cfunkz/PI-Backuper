# =========================
# file: pibackuper/utils.py
# =========================
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


def is_admin() -> bool:
    """Return True if running with admin rights (Windows)."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def resource_path(rel: str) -> Path:
    """Resolve resource path for dev or PyInstaller bundle."""
    base = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(".")  # type: ignore[attr-defined]
    return (base / rel).resolve()


def fmt_bytes(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {u}"
        n /= 1024
    return f"{n:.2f} PB"


def fmt_eta(sec: float | None) -> str:
    if sec is None:
        return "ETA …"
    if sec <= 0:
        return "ETA —"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"ETA {h}h {m:02d}m"
    if m:
        return f"ETA {m}m {s:02d}s"
    return f"ETA {s}s"


def disk_rescan() -> None:
    """Trigger DiskPart rescan (best-effort)."""
    try:
        subprocess.run(
            ["diskpart"],
            input="rescan\nexit\n",
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        pass


def make_hasher(name: str | None):
    name = (name or "").lower()
    if name == "sha256":
        return hashlib.sha256()
    if name == "md5":
        return hashlib.md5()
    return None


def sidecar(img: str) -> str:
    return img + ".hash.txt"


def write_sidecar(path: str, algo: str, nbytes: int, hexd: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{algo.lower()} {int(nbytes)} {hexd.lower()}\n")
    except Exception:
        pass


def read_sidecar(path: str) -> Optional[Tuple[str, int, str]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            parts = f.readline().strip().split()
        if len(parts) == 3:
            algo, nbytes, hexd = parts
            return algo.lower(), int(nbytes), hexd.lower()
    except Exception:
        pass
    return None


def atomic_replace(src: str, dst: str) -> None:
    os.replace(src, dst)

