import os, time, gzip, queue, threading, hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
from pathlib import Path

import win32file, win32con
import wmi

# ---------------- App metadata ----------------
__title__ = "PI-Backuper"
__version__ = "1.0.0"
__author__ = "cFunkz"
__license__ = "MIT"
__url__ = "https://github.com/cfunkz/PI-Backuper"
__description__ = "Fast Raspberry Pi SD card backup/restore (Windows, USB removable)."

CHUNK = 8 * 1024 * 1024   # 8MB
QUEUE_MAX = 16            # 16 * 8MB = 128MB buffer

ICON_FILE = "favicon.ico"


# ---------- helpers ----------
def is_admin():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative  # type: ignore[attr-defined]
    return Path(relative)


def fmt_bytes(n: float) -> str:
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.2f} {u}"
        n /= 1024
    return f"{n:.2f} PB"


def fmt_eta(sec):
    if sec is None:
        return "ETA calculating…"
    if sec <= 0:
        return "ETA —"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"ETA {h}h {m:02d}m"
    if m:
        return f"ETA {m}m {s:02d}s"
    return f"ETA {s}s"


def open_disk(path: str, write: bool = False):
    return win32file.CreateFile(
        path,
        win32con.GENERIC_WRITE if write else win32con.GENERIC_READ,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
        None,
        win32con.OPEN_EXISTING,
        win32con.FILE_FLAG_SEQUENTIAL_SCAN if not write else 0,
        None,
    )


def safe_remove(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ---------- removable disk detection ----------
def list_removable_disks():
    c = wmi.WMI()
    disks = []
    for d in c.Win32_DiskDrive():
        if (d.InterfaceType or "").upper() != "USB":
            continue

        phys = rf"\\.\PhysicalDrive{d.Index}"
        size = int(d.Size)
        model = (d.Model or "USB device").strip()

        letter = "?"
        for p in d.associators("Win32_DiskDriveToDiskPartition"):
            for l in p.associators("Win32_LogicalDiskToPartition"):
                letter = l.DeviceID
                break

        disks.append({"letter": letter, "phys": phys, "size": size, "model": model})
    return disks


# ---------- UI ----------
class App(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.root = root
        self.pack(fill="both", expand=True, padx=12, pady=12)

        self.q = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False

        self.disk_var = tk.StringVar()
        self.hash_var = tk.StringVar(value="sha256")
        self.compress_var = tk.BooleanVar(value=True)

        self.progress = tk.DoubleVar(value=0)
        self.status = tk.StringVar(value="Ready")
        self.speed = tk.StringVar(value="")
        self.eta = tk.StringVar(value="ETA —")  # FIX: not blank

        self._build_ui()
        self.refresh_disks()
        self.after(100, self._poll)

    def _build_ui(self):
        menubar = tk.Menu(self.root)
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self._about)
        menubar.add_cascade(label="Help", menu=helpmenu)
        self.root.config(menu=menubar)

        dev = ttk.LabelFrame(self, text="Removable device (USB)")
        dev.pack(fill="x")

        self.disk_box = ttk.Combobox(dev, textvariable=self.disk_var, state="readonly")
        self.disk_box.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ttk.Button(dev, text="Refresh", command=self.refresh_disks).pack(side="right", padx=6, pady=6)

        main = ttk.Frame(self)
        main.pack(fill="x", pady=10)

        b = ttk.LabelFrame(main, text="Backup")
        b.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.backup_path = tk.StringVar()
        ttk.Entry(b, textvariable=self.backup_path).pack(fill="x", padx=6, pady=4)
        rowb = ttk.Frame(b)
        rowb.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(rowb, text="Choose output", command=self.pick_backup).pack(side="left")
        ttk.Button(rowb, text="Start backup", command=self.start_backup).pack(side="right")

        r = ttk.LabelFrame(main, text="Restore")
        r.pack(side="left", fill="both", expand=True, padx=(5, 0))

        self.restore_path = tk.StringVar()
        ttk.Entry(r, textvariable=self.restore_path).pack(fill="x", padx=6, pady=4)
        rowr = ttk.Frame(r)
        rowr.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(rowr, text="Choose image", command=self.pick_restore).pack(side="left")
        ttk.Button(rowr, text="Start restore (erases)", command=self.start_restore).pack(side="right")

        opt = ttk.LabelFrame(self, text="Options")
        opt.pack(fill="x")

        for txt, val in [("SHA256", "sha256"), ("MD5", "md5"), ("None", "none")]:
            ttk.Radiobutton(opt, text=txt, variable=self.hash_var, value=val).pack(side="left", padx=6)

        ttk.Checkbutton(opt, text="Gzip compress", variable=self.compress_var).pack(side="right", padx=6)

        prog = ttk.LabelFrame(self, text="Progress")
        prog.pack(fill="x", pady=10)

        ttk.Progressbar(prog, variable=self.progress, maximum=100).pack(fill="x", padx=6, pady=4)

        lines = ttk.Frame(prog)
        lines.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Label(lines, textvariable=self.status).pack(anchor="w")
        ttk.Label(lines, textvariable=self.speed).pack(anchor="w")
        ttk.Label(lines, textvariable=self.eta).pack(anchor="w")

        btns = ttk.Frame(prog)
        btns.pack(fill="x", padx=6, pady=(0, 6))
        self.cancel_btn = ttk.Button(btns, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="right")

    def _about(self):
        messagebox.showinfo(
            "About",
            f"{__title__} v{__version__}\n"
            f"{__description__}\n\n"
            f"Author: {__author__}\n"
            f"License: {__license__}\n"
            f"{__url__}",
        )

    def refresh_disks(self):
        try:
            self.disks = list_removable_disks()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list disks:\n\n{e}")
            self.disks = []

        values = [f"{d['letter']} | {fmt_bytes(d['size'])} | {d['model']}" for d in self.disks]
        self.disk_box["values"] = values
        if values:
            self.disk_var.set(values[0])

    def selected_disk(self):
        if not self.disks or self.disk_box.current() < 0:
            raise RuntimeError("No removable disk selected.")
        return self.disks[self.disk_box.current()]

    def pick_backup(self):
        ext = ".img.gz" if self.compress_var.get() else ".img"
        p = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[("Image", "*.img *.img.gz"), ("All", "*.*")])
        if p:
            self.backup_path.set(p)

    def pick_restore(self):
        p = filedialog.askopenfilename(filetypes=[("Image", "*.img *.img.gz"), ("All", "*.*")])
        if p:
            self.restore_path.set(p)

    def _set_busy(self, busy: bool):
        self.busy = busy
        self.cancel_btn.config(state="normal" if busy else "disabled")

    def _cancel(self):
        self.cancel.set()
        self.status.set("Cancelling…")

    def start_backup(self):
        if self.busy:
            messagebox.showwarning("Busy", "An operation is already running.")
            return
        out = self.backup_path.get().strip()
        if not out:
            messagebox.showerror("Error", "No output file")
            return

        self.eta.set("ETA calculating…")  # FIX: show immediately
        self.cancel.clear()
        self._set_busy(True)
        threading.Thread(target=self._backup_worker, daemon=True).start()

    def start_restore(self):
        if self.busy:
            messagebox.showwarning("Busy", "An operation is already running.")
            return
        img = self.restore_path.get().strip()
        if not img:
            messagebox.showerror("Error", "No image selected")
            return
        if not messagebox.askyesno("WARNING", "THIS ERASES THE DEVICE. CONTINUE?"):
            return

        self.eta.set("ETA calculating…")  # FIX: show immediately
        self.cancel.clear()
        self._set_busy(True)
        threading.Thread(target=self._restore_worker, daemon=True).start()

    def _backup_worker(self):
        try:
            d = self.selected_disk()
            out = self.backup_path.get()
            tmp = out + ".partial"
            safe_remove(tmp)

            hasher = None
            hv = self.hash_var.get()
            if hv == "sha256":
                hasher = hashlib.sha256()
            elif hv == "md5":
                hasher = hashlib.md5()

            qdata = queue.Queue(maxsize=QUEUE_MAX)

            reader = open_disk(d["phys"])
            raw = open(tmp, "wb", buffering=16 * 1024 * 1024)
            writer = gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=1) if self.compress_var.get() else raw

            total = d["size"]
            done = 0
            start = time.time()
            last_ui = start

            def reader_thread():
                remaining = total
                try:
                    while remaining > 0 and not self.cancel.is_set():
                        to_read = min(CHUNK, remaining)
                        _, data = win32file.ReadFile(reader, to_read)
                        if not data:
                            break
                        qdata.put(data)
                        remaining -= len(data)
                finally:
                    qdata.put(None)

            def writer_thread():
                nonlocal done, last_ui
                while True:
                    data = qdata.get()
                    if data is None:
                        break
                    if self.cancel.is_set():
                        break
                    writer.write(data)
                    if hasher:
                        hasher.update(memoryview(data))
                    done += len(data)

                    now = time.time()
                    if now - last_ui > 0.2:
                        elapsed = now - start
                        spd = done / elapsed if elapsed else 0.0
                        eta = (total - done) / spd if spd > 0 else None  # FIX: only None when spd is 0
                        self.q.put(("p", done, total, spd, eta))
                        last_ui = now

            t1 = threading.Thread(target=reader_thread, daemon=True)
            t2 = threading.Thread(target=writer_thread, daemon=True)
            t1.start(); t2.start()
            t1.join(); t2.join()

            try:
                writer.close()
            except Exception:
                pass
            try:
                raw.flush()
                os.fsync(raw.fileno())
            except Exception:
                pass
            try:
                raw.close()
            except Exception:
                pass
            try:
                win32file.CloseHandle(reader)
            except Exception:
                pass

            if self.cancel.is_set():
                safe_remove(tmp)
                self.q.put(("done", "Backup cancelled"))
                return

            os.replace(tmp, out)

            if hasher:
                with open(out + ".hash.txt", "w", encoding="utf-8") as f:
                    f.write(hasher.hexdigest())

            self.q.put(("done", "Backup complete"))

        except Exception as e:
            try:
                safe_remove(self.backup_path.get() + ".partial")
            except Exception:
                pass
            self.q.put(("err", str(e)))

    def _restore_worker(self):
        try:
            d = self.selected_disk()
            img = self.restore_path.get()

            w = open_disk(d["phys"], write=True)
            opener = gzip.open if img.lower().endswith(".gz") else open

            total = d["size"]
            done = 0
            start = time.time()
            last_ui = start

            with opener(img, "rb") as src:
                while not self.cancel.is_set():
                    data = src.read(CHUNK)
                    if not data:
                        break
                    win32file.WriteFile(w, data)
                    done += len(data)

                    now = time.time()
                    if now - last_ui > 0.2:
                        elapsed = now - start
                        spd = done / elapsed if elapsed else 0.0
                        eta = (total - done) / spd if spd > 0 else None  # FIX
                        self.q.put(("p", done, total, spd, eta))
                        last_ui = now

            try:
                win32file.FlushFileBuffers(w)
            except Exception:
                pass
            try:
                win32file.CloseHandle(w)
            except Exception:
                pass

            if self.cancel.is_set():
                self.q.put(("done", "Restore cancelled (device may be partially written)"))
            else:
                self.q.put(("done", "Restore complete"))

        except Exception as e:
            self.q.put(("err", str(e)))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "p":
                    _, done, total, spd, eta = msg
                    self.progress.set(min(done / total * 100, 100))
                    self.status.set(f"{fmt_bytes(done)} / {fmt_bytes(total)}")
                    self.speed.set(f"{fmt_bytes(spd)}/s" if spd else "")
                    self.eta.set(fmt_eta(eta))  # will show calculating… then real ETA
                elif msg[0] == "done":
                    self._set_busy(False)
                    self.status.set(msg[1])
                elif msg[0] == "err":
                    self._set_busy(False)
                    self.status.set("Error")
                    messagebox.showerror("Error", msg[1])
        except queue.Empty:
            pass
        self.after(100, self._poll)


def install_exception_box():
    def _hook(exctype, value, tb):
        import traceback
        msg = "".join(traceback.format_exception(exctype, value, tb))
        try:
            messagebox.showerror("Fatal error", msg)
        except Exception:
            pass
        raise SystemExit(1)
    sys.excepthook = _hook


def main():
    root = tk.Tk()
    install_exception_box()

    try:
        root.iconbitmap(resource_path(ICON_FILE))
    except Exception:
        pass

    root.title(f"{__title__} v{__version__}")
    root.geometry("820x430")
    root.minsize(760, 420)

    if not is_admin():
        messagebox.showerror("Admin required", "Please run as Administrator.")
        root.destroy()
        return

    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
