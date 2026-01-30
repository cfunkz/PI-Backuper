# =========================
# file: pibackuper/disks.py
# =========================
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from win_deps import win_modules


@dataclass(frozen=True)
class DiskInfo:
    idx: int
    phys: str
    size: int
    model: str
    letters: list[str]


def list_usb_disks() -> List[DiskInfo]:
    """List USB disks via WMI with drive letters."""
    w = win_modules()
    c = w.wmi.WMI()
    out: list[DiskInfo] = []
    for d in c.Win32_DiskDrive():
        if (d.InterfaceType or "").upper() != "USB":
            continue
        letters: list[str] = []
        try:
            for p in d.associators("Win32_DiskDriveToDiskPartition"):
                for l in p.associators("Win32_LogicalDiskToPartition"):
                    if l.DeviceID:
                        letters.append(str(l.DeviceID))
        except Exception:
            pass

        out.append(
            DiskInfo(
                idx=int(d.Index),
                phys=rf"\\.\PhysicalDrive{d.Index}",
                size=int(d.Size),
                model=(d.Model or "USB device").strip(),
                letters=letters,
            )
        )
    out.sort(key=lambda x: x.idx)
    return out
