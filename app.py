# =========================
# file: pibackuper/app.py
# =========================
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

from constants import __title__, __version__
from ui import App, set_app_icon
from utils import is_admin
from win_deps import MissingWindowsDependency, win_modules


def install_exception_box() -> None:
    def _hook(exctype, value, tb):
        import traceback
        msg = "".join(traceback.format_exception(exctype, value, tb))
        try:
            messagebox.showerror("Fatal error", msg)
        except Exception:
            pass
        raise SystemExit(1)

    sys.excepthook = _hook


def run() -> None:
    root = tk.Tk()
    install_exception_box()
    set_app_icon(root)

    root.title(f"{__title__} v{__version__}")
    root.geometry("860x500")
    root.minsize(780, 460)

    if not is_admin():
        messagebox.showerror("Admin required", "Run as Administrator.")
        root.destroy()
        return

    try:
        win_modules()
    except MissingWindowsDependency as e:
        messagebox.showerror("Missing dependency", str(e))
        root.destroy()
        return

    App(root)
    root.mainloop()

if __name__ == "__main__":
    run()
