# =========================
# file: pibackuper/ui.py
# =========================
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from constants import ICON_FILE
from disks import DiskInfo, list_usb_disks
from operations import (
    BackupOptions,
    backup_disk_to_image,
    clone_disk_to_disk,
    restore_image_to_disk,
)
from streaming import Progress
from utils import fmt_bytes, fmt_eta, resource_path


class App(ttk.Frame):
    """
    Tkinter UI. Owns:
      - disk refresh + selection
      - running on background threads
      - progress to UI thread via queue
    """

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.root = root
        self.pack(fill="both", expand=True, padx=12, pady=12)

        self._msgq: queue.Queue[tuple] = queue.Queue()
        self._cancel_evt = threading.Event()
        self._busy = False
        self._disks: list[DiskInfo] = []

        self.disk_var = tk.StringVar()
        self.src_var = tk.StringVar()
        self.dst_var = tk.StringVar()

        self.hash_var = tk.StringVar(value="sha256")
        self.compress_var = tk.BooleanVar(value=True)

        self.backup_path = tk.StringVar()
        self.restore_path = tk.StringVar()

        self.progress = tk.DoubleVar(value=0)
        self.status = tk.StringVar(value="Ready")
        self.speed = tk.StringVar(value="")
        self.eta = tk.StringVar(value="ETA —")

        self._build_ui()
        self.refresh()
        self.after(100, self._poll)

    def _build_ui(self) -> None:
        menubar = tk.Menu(self.root)
        h = tk.Menu(menubar, tearoff=0)
        h.add_command(label="About", command=self._about)
        menubar.add_cascade(label="Help", menu=h)
        self.root.config(menu=menubar)

        dev = ttk.LabelFrame(self, text="USB device (Backup/Restore)")
        dev.pack(fill="x", pady=(0, 6))
        self.disk_box = ttk.Combobox(dev, textvariable=self.disk_var, state="readonly")
        self.disk_box.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ttk.Button(dev, text="Refresh", command=self.refresh).pack(side="right", padx=6, pady=6)

        row = ttk.Frame(self)
        row.pack(fill="x", pady=(0, 6))

        b = ttk.LabelFrame(row, text="Backup")
        b.pack(side="left", fill="both", expand=True, padx=(0, 5))
        ttk.Entry(b, textvariable=self.backup_path).pack(fill="x", padx=6, pady=4)
        rb = ttk.Frame(b)
        rb.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(rb, text="Choose output", command=self.pick_backup).pack(side="left")
        ttk.Button(rb, text="Start backup", command=self.start_backup).pack(side="right")

        r = ttk.LabelFrame(row, text="Restore")
        r.pack(side="left", fill="both", expand=True, padx=(5, 0))
        ttk.Entry(r, textvariable=self.restore_path).pack(fill="x", padx=6, pady=4)
        rr = ttk.Frame(r)
        rr.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(rr, text="Choose image", command=self.pick_restore).pack(side="left")
        ttk.Button(rr, text="Start restore (erases)", command=self.start_restore).pack(side="right")

        c = ttk.LabelFrame(self, text="Clone (Live A → B, erases B)")
        c.pack(fill="x", pady=(0, 6))
        ttk.Label(c, text="A:").pack(side="left", padx=(6, 4), pady=6)
        self.src_box = ttk.Combobox(c, textvariable=self.src_var, state="readonly", width=34)
        self.src_box.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=6)
        ttk.Label(c, text="B:").pack(side="left", padx=(0, 4), pady=6)
        self.dst_box = ttk.Combobox(c, textvariable=self.dst_var, state="readonly", width=34)
        self.dst_box.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=6)
        ttk.Button(c, text="Start clone", command=self.start_clone).pack(side="right", padx=(0, 6), pady=6)

        opt = ttk.LabelFrame(self, text="Options")
        opt.pack(fill="x", pady=(0, 6))
        for txt, val in (("SHA256", "sha256"), ("MD5", "md5"), ("None", "none")):
            ttk.Radiobutton(opt, text=txt, variable=self.hash_var, value=val).pack(side="left", padx=6, pady=2)
        ttk.Checkbutton(opt, text="Gzip compress", variable=self.compress_var).pack(side="right", padx=6, pady=2)

        prog = ttk.LabelFrame(self, text="Progress")
        prog.pack(fill="x")
        ttk.Progressbar(prog, variable=self.progress, maximum=100).pack(fill="x", padx=6, pady=(4, 2))
        lines = ttk.Frame(prog)
        lines.pack(fill="x", padx=6, pady=(0, 4))
        ttk.Label(lines, textvariable=self.status).pack(anchor="w")
        ttk.Label(lines, textvariable=self.speed).pack(anchor="w")
        er = ttk.Frame(lines)
        er.pack(fill="x")
        ttk.Label(er, textvariable=self.eta).pack(side="left")
        self.cancel_btn = ttk.Button(er, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="right")

    def _about(self) -> None:
        from .constants import __author__, __description__, __license__, __title__, __url__, __version__
        messagebox.showinfo(
            "About",
            f"{__title__} v{__version__}\n{__description__}\n\nAuthor: {__author__}\nLicense: {__license__}\n{__url__}",
        )

    def refresh(self) -> None:
        try:
            self._disks = list_usb_disks()
        except Exception:
            self._disks = []

        vals = [self._fmt_disk(d) for d in self._disks]
        for box in (self.disk_box, self.src_box, self.dst_box):
            box["values"] = vals
            if vals and box.current() < 0:
                box.current(0)

        if vals:
            self.disk_var.set(vals[self.disk_box.current()])
            self.src_var.set(vals[self.src_box.current()])
            self.dst_var.set(vals[self.dst_box.current()])

    @staticmethod
    def _fmt_disk(d: DiskInfo) -> str:
        letters = ",".join(d.letters) if d.letters else "—"
        return f"{letters} | {fmt_bytes(d.size)} | Disk {d.idx} | {d.model}"

    def _selected_disk(self, box: ttk.Combobox) -> DiskInfo:
        if not self._disks or box.current() < 0:
            raise RuntimeError("No disk selected.")
        return self._disks[box.current()]

    def pick_backup(self) -> None:
        ext = ".img.gz" if self.compress_var.get() else ".img"
        p = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[("Image", "*.img *.img.gz"), ("All", "*.*")],
        )
        if p:
            self.backup_path.set(p)

    def pick_restore(self) -> None:
        p = filedialog.askopenfilename(
            filetypes=[("Image", "*.img *.img.gz"), ("All", "*.*")],
        )
        if p:
            self.restore_path.set(p)

    def _set_busy(self, on: bool) -> None:
        self._busy = on
        self.cancel_btn.config(state="normal" if on else "disabled")

    def _cancel(self) -> None:
        self._cancel_evt.set()
        self.status.set("Cancelling…")

    def _start_worker(self, worker_fn) -> None:
        self.progress.set(0)
        self.status.set("Starting…")
        self.speed.set("")
        self.eta.set("ETA …")
        self._cancel_evt.clear()
        self._set_busy(True)
        threading.Thread(target=worker_fn, daemon=True).start()

    def _progress_cb(self, p: Progress) -> None:
        self._msgq.put(("p", p))

    # ---------- buttons ----------
    def start_backup(self) -> None:
        if self._busy:
            messagebox.showwarning("Busy", "Operation running.")
            return
        out = self.backup_path.get().strip()
        if not out:
            messagebox.showerror("Error", "No output file.")
            return

        def worker() -> None:
            try:
                d = self._selected_disk(self.disk_box)
                opts = BackupOptions(
                    compress=bool(self.compress_var.get()),
                    hash_algo=str(self.hash_var.get()).lower(),
                )
                backup_disk_to_image(
                    disk=d,
                    out_path=out,
                    opts=opts,
                    cancel_evt=self._cancel_evt,
                    progress_cb=self._progress_cb,
                )
                self._msgq.put(("done", "Backup complete"))
            except InterruptedError:
                self._msgq.put(("done", "Backup cancelled"))
            except Exception as e:
                self._msgq.put(("err", str(e)))

        self._start_worker(worker)

    def start_restore(self) -> None:
        if self._busy:
            messagebox.showwarning("Busy", "Operation running.")
            return
        img = self.restore_path.get().strip()
        if not img:
            messagebox.showerror("Error", "No image selected.")
            return

        d = self._selected_disk(self.disk_box)
        if not messagebox.askyesno(
            "WARNING",
            f"THIS ERASES:\n\nDisk {d.idx} ({fmt_bytes(d.size)})\n\nContinue?",
        ):
            return

        def worker() -> None:
            try:
                d2 = self._selected_disk(self.disk_box)
                restore_image_to_disk(
                    disk=d2,
                    img_path=img,
                    cancel_evt=self._cancel_evt,
                    progress_cb=self._progress_cb,
                )
                self._msgq.put(("done", "Restore complete"))
            except InterruptedError:
                self._msgq.put(("done", "Restore cancelled"))
            except Exception as e:
                self._msgq.put(("err", str(e)))

        self._start_worker(worker)

    def start_clone(self) -> None:
        if self._busy:
            messagebox.showwarning("Busy", "Operation running.")
            return

        a = self._selected_disk(self.src_box)
        b = self._selected_disk(self.dst_box)
        if a.idx == b.idx:
            messagebox.showerror("Error", "A and B must be different.")
            return
        if b.size < a.size:
            messagebox.showerror("Error", f"Target smaller.\nA: {fmt_bytes(a.size)}\nB: {fmt_bytes(b.size)}")
            return

        if not messagebox.askyesno(
            "WARNING",
            "CLONE ERASES B.\n\n"
            f"A: Disk {a.idx} ({fmt_bytes(a.size)})\n"
            f"B: Disk {b.idx} ({fmt_bytes(b.size)})\n\nContinue?",
        ):
            return

        def worker() -> None:
            try:
                a2 = self._selected_disk(self.src_box)
                b2 = self._selected_disk(self.dst_box)
                clone_disk_to_disk(
                    src_disk=a2,
                    dst_disk=b2,
                    cancel_evt=self._cancel_evt,
                    progress_cb=self._progress_cb,
                )
                self._msgq.put(("done", "Clone complete"))
            except InterruptedError:
                self._msgq.put(("done", "Clone cancelled"))
            except Exception as e:
                self._msgq.put(("err", str(e)))

        self._start_worker(worker)

    # ---------- polling ----------
    def _poll(self) -> None:
        try:
            while True:
                msg = self._msgq.get_nowait()
                kind = msg[0]
                if kind == "p":
                    p: Progress = msg[1]
                    total = max(int(p.total), 1)
                    self.progress.set(min(p.done / total * 100, 100))
                    self.status.set(f"{fmt_bytes(p.done)} / {fmt_bytes(total)}")
                    self.speed.set(f"{fmt_bytes(p.speed_bps)}/s" if p.speed_bps else "")
                    self.eta.set(fmt_eta(p.eta_sec))
                elif kind == "done":
                    self._set_busy(False)
                    self.status.set(str(msg[1]))
                    self.speed.set("")
                    self.eta.set("ETA —")
                elif kind == "err":
                    self._set_busy(False)
                    self.status.set("Error")
                    self.speed.set("")
                    self.eta.set("ETA —")
                    messagebox.showerror("Error", str(msg[1]))
        except queue.Empty:
            pass
        self.after(100, self._poll)


def set_app_icon(root: tk.Tk) -> None:
    try:
        root.iconbitmap(resource_path(ICON_FILE))
    except Exception:
        pass
