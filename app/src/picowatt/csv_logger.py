"""Streaming CSV logger: dedicated writer thread, no GUI-thread disk I/O."""

from __future__ import annotations

import queue
import threading
from datetime import datetime

import numpy as np


class CsvLogger:
    """Append (ch, t, v, i) batches to a CSV file from a background thread."""

    def __init__(self, path: str, meta: dict[str, str] | None = None) -> None:
        self.path = path
        self._q: queue.Queue[tuple[int, np.ndarray, np.ndarray, np.ndarray] | None] = (
            queue.Queue(maxsize=1000)
        )
        self._file = open(path, "w", newline="")  # noqa: SIM115 - lifetime managed by stop()
        for key, val in (meta or {}).items():
            self._file.write(f"# {key}: {val}\n")
        self._file.write(f"# started: {datetime.now().astimezone().isoformat()}\n")
        self._file.write("t_s,ch,vbus_V,current_A,power_W\n")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.rows_written = 0
        self.dropped_batches = 0

    def log(self, ch: int, t: np.ndarray, v: np.ndarray, i: np.ndarray) -> None:
        try:
            self._q.put_nowait((ch, t, v, i))
        except queue.Full:
            self.dropped_batches += 1

    def stop(self) -> None:
        self._q.put(None)
        self._thread.join(timeout=5)
        self._file.close()

    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                return
            ch, t, v, i = item
            p = v.astype(np.float64) * i.astype(np.float64)
            lines = [
                f"{t[k]:.6f},{ch},{v[k]:.6f},{i[k]:.7f},{p[k]:.7f}\n"
                for k in range(len(t))
            ]
            self._file.writelines(lines)
            self.rows_written += len(lines)
            if self._q.empty():
                self._file.flush()
