# =========================
# file: pibackuper/win_deps.py
# =========================
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple


class MissingWindowsDependency(RuntimeError):
    """Raised when pywin32/wmi dependencies are not available."""


@dataclass(frozen=True)
class WinModules:
    """Container for Windows modules."""
    wmi: Any
    win32file: Any
    win32con: Any
    pywintypes: Any
    win32event: Any


_WIN_CACHE: WinModules | None = None


def win_modules() -> WinModules:
    """
    Requires:
        pip install pywin32 wmi
    """
    global _WIN_CACHE
    if _WIN_CACHE is not None:
        return _WIN_CACHE
    try:
        import wmi  # type: ignore
        import win32file  # type: ignore
        import win32con  # type: ignore
        import pywintypes  # type: ignore
        import win32event  # type: ignore

        _WIN_CACHE = WinModules(
            wmi=wmi,
            win32file=win32file,
            win32con=win32con,
            pywintypes=pywintypes,
            win32event=win32event,
        )
        return _WIN_CACHE
    except Exception as e:
        raise MissingWindowsDependency(
            "Required Windows modules not available. Install:\n"
            "  pip install pywin32 wmi\n"
            f"Error: {e}"
        ) from e
