# =========================
# file: pibackuper/streaming.py
# =========================
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from constants import QUEUE_MAX


@dataclass(frozen=True)
class Progress:
    done: int
    total: int
    speed_bps: float
    eta_sec: float | None


ReadFn = Callable[[], bytes]
WriteFn = Callable[[bytes], None]
LimitFn = Callable[[int], None]
ProgressFn = Callable[[Progress], None]


def stream_copy(
    *,
    read_fn: ReadFn,
    write_fn: WriteFn,
    total: int,
    cancel_evt: threading.Event,
    hasher=None,
    limit_fn: LimitFn | None = None,
    progress_fn: ProgressFn | None = None,
    tick_sec: float = 0.2,
) -> int:
    """
    Producer/consumer streamer:
      - producer reads chunks and enqueues
      - consumer writes chunks, updates optional hasher
      - posts progress periodically via callback
    """
    qd: queue.Queue[bytes | None] = queue.Queue(maxsize=QUEUE_MAX)
    done = 0
    start = time.time()
    last = start
    err: list[BaseException | None] = [None]

    def producer() -> None:
        try:
            while not cancel_evt.is_set():
                b = read_fn()
                if not b:
                    break
                qd.put(b)
        except BaseException as e:
            err[0] = e
        finally:
            qd.put(None)

    threading.Thread(target=producer, daemon=True).start()

    def emit(now: float) -> None:
        if not progress_fn:
            return
        dt = max(now - start, 1e-6)
        spd = done / dt
        eta = (total - done) / spd if spd > 0 else None
        progress_fn(Progress(done=done, total=total, speed_bps=spd, eta_sec=eta))

    while True:
        b = qd.get()
        if b is None:
            break
        if cancel_evt.is_set():
            break

        if limit_fn:
            limit_fn(len(b))
        if hasher:
            hasher.update(b)

        write_fn(b)
        done += len(b)

        now = time.time()
        if now - last >= tick_sec:
            emit(now)
            last = now

    if err[0] is not None:
        raise err[0]

    emit(time.time())
    return done