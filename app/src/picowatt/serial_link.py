"""Serial worker thread: owns the Device, streams converted sample batches."""

from __future__ import annotations

import queue
import time
from collections.abc import Callable

import numpy as np
from PySide6.QtCore import QThread, Signal

from . import protocol as proto
from .buffer import unwrap_t_us
from .calibration import CalibrationStore
from .device import Device, DeviceError


class SerialWorker(QThread):
    """Runs the serial session; all Device access happens on this thread.

    GUI code calls submit() to run commands on the worker thread; results
    surface through the signals below.
    """

    connected = Signal(object)       # HelloAck
    config_updated = Signal(object)  # Config
    samples = Signal(int, object, object, object)  # ch, t_s f8, v f4, i f4
    stats = Signal(int, int)         # frame gaps total, device ring drops
    error = Signal(str)
    finished_session = Signal()

    def __init__(self, port: str | None = None,
                 cal_store: CalibrationStore | None = None) -> None:
        super().__init__()
        self._port = port
        self._cal_store = cal_store
        self._cmds: queue.Queue[Callable[[Device], None]] = queue.Queue()
        self._quit = False
        self._offsets = [0.0, 0.0]  # amps, subtracted from converted current
        self.board_id: str | None = None

    def _refresh_offsets(self, cfg: proto.Config) -> None:
        if self._cal_store is None or self.board_id is None:
            return
        self._offsets = [
            self._cal_store.get(self.board_id, c).offset_for(cfg.ch[c].adcrange)
            for c in (0, 1)
        ]

    def submit(self, fn: Callable[[Device], None]) -> None:
        """Run fn(device) on the worker thread; config is re-read after."""
        self._cmds.put(fn)

    def shutdown(self) -> None:
        self._quit = True

    def run(self) -> None:
        try:
            dev = Device(self._port)
        except (DeviceError, OSError) as e:
            self.error.emit(str(e))
            self.finished_session.emit()
            return

        try:
            hello = dev.connect()
            self.board_id = hello.board_id
            # Push stored gain calibration (device is stateless across power cycles)
            if self._cal_store is not None:
                assert dev.config is not None
                for c in (0, 1):
                    if not (hello.ch_present & (1 << c)):
                        continue
                    cal = self._cal_store.get(hello.board_id, c)
                    if cal.shunt_cal != dev.config.ch[c].shunt_cal:
                        dev.set_shunt_cal(c, cal.shunt_cal)
            self.connected.emit(hello)
            assert dev.config is not None
            self._refresh_offsets(dev.config)
            self.config_updated.emit(dev.config)
        except (DeviceError, OSError) as e:
            self.error.emit(str(e))
            dev.close()
            self.finished_session.emit()
            return

        last_unwrap: int | None = None
        offset = 0
        t_zero: float | None = None  # session time zero (first sample)
        last_seq: int | None = None
        gaps = 0
        last_stats = time.monotonic()

        try:
            while not self._quit:
                # Pending commands (settings changes, start/stop, ...)
                ran_cmd = False
                while True:
                    try:
                        fn = self._cmds.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        fn(dev)
                        ran_cmd = True
                    except (DeviceError, OSError) as e:
                        self.error.emit(str(e))
                if ran_cmd:
                    cfg_new = dev.get_config()
                    self._refresh_offsets(cfg_new)
                    self.config_updated.emit(cfg_new)

                cfg = dev.config
                assert cfg is not None
                lsb = (cfg.ch[0].current_lsb, cfg.ch[1].current_lsb)

                # Drain available DATA frames, coalesce into one batch
                batches: list[np.ndarray] = []
                for seq, rec in dev.read_data_frames():
                    if last_seq is not None and seq != (last_seq + 1) & 0xFFFF:
                        gaps += (seq - last_seq - 1) & 0xFFFF
                    last_seq = seq
                    batches.append(rec)

                if not batches:
                    time.sleep(0.005)
                    continue

                rec = np.concatenate(batches) if len(batches) > 1 else batches[0]
                t_s, last_unwrap, offset = unwrap_t_us(rec["t_us"], last_unwrap, offset)
                if t_zero is None and len(t_s):
                    t_zero = float(t_s[0])
                t_s = t_s - (t_zero or 0.0)
                for c in (0, 1):
                    m = rec["ch"] == c
                    if not np.any(m):
                        continue
                    v = (rec["vbus_raw"][m] * proto.VBUS_LSB_V).astype(np.float32)
                    i = (rec["curr_raw"][m] * lsb[c] - self._offsets[c]).astype(np.float32)
                    self.samples.emit(c, t_s[m], v, i)

                now = time.monotonic()
                if now - last_stats > 1.0:
                    last_stats = now
                    self.stats.emit(gaps, 0)  # ring drops read on demand via config
        finally:
            try:
                dev.stop()
            except (DeviceError, OSError):
                pass
            dev.close()
            self.finished_session.emit()
