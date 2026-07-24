"""Headless capture CLI.

Examples:
    picowatt-cli --seconds 10
    picowatt-cli --seconds 60 --preset normal --csv out.csv
    picowatt-cli --mode dual --preset fast-dual --csv sweep.csv
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import sys
import time

import numpy as np

from . import protocol as proto
from .device import Device, DeviceError, find_ports


class TimeUnwrapper:
    """Unwrap the device's u32 microsecond timer into monotonic seconds."""

    def __init__(self) -> None:
        self._last: int | None = None
        self._offset = 0  # accumulated wraps, in us

    def unwrap(self, t_us: np.ndarray) -> np.ndarray:
        out = np.empty(len(t_us), dtype=np.float64)
        last, offset = self._last, self._offset
        for i, t in enumerate(t_us):
            t = int(t)
            if last is not None and t < last - 2**31:
                offset += 2**32
            last = t
            out[i] = (t + offset) * 1e-6
        self._last, self._offset = last, offset
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description="picowatt headless capture")
    ap.add_argument("--port", help="serial port (default: auto-detect)")
    ap.add_argument("--seconds", type=float, default=10.0, help="capture duration")
    ap.add_argument("--csv", help="write samples to CSV file")
    ap.add_argument("--preset", choices=sorted(proto.PRESETS), default=None,
                    help="rate preset (see docs/protocol.md)")
    ap.add_argument("--adcrange", type=int, choices=[0, 1], default=0,
                    help="0: +/-163.84mV (8uA LSB), 1: +/-40.96mV (2uA LSB)")
    ap.add_argument("--mode", choices=["single", "dual"], default=None)
    ap.add_argument("--list", action="store_true", help="list candidate ports and exit")
    args = ap.parse_args()

    if args.list:
        for p in find_ports():
            print(p)
        return 0

    try:
        dev = Device(args.port)
    except DeviceError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    with dev, contextlib.ExitStack() as stack:
        hello = dev.connect()
        print(f"connected: fw {'.'.join(map(str, hello.fw_version))}  "
              f"board {hello.board_id}  channels 0x{hello.ch_present:02X}")

        if args.mode:
            dev.set_mode(0 if args.mode == "single" else 1)
        if args.preset:
            dev.set_preset(args.preset, adcrange=args.adcrange)

        cfg = dev.config
        assert cfg is not None
        nch = 2 if cfg.mode == 1 else 1
        print(f"mode={'dual' if cfg.mode else 'single'}  "
              f"expected rate/ch ~{1.0 / cfg.ch[0].sample_period_s:.1f} Hz")

        writer = None
        if args.csv:
            csv_file = stack.enter_context(open(args.csv, "w", newline=""))
            writer = csv.writer(csv_file)
            writer.writerow(["t_s", "ch", "vbus_V", "current_A", "power_W"])

        unwrap = TimeUnwrapper()
        lsb = [cfg.ch[c].current_lsb for c in range(2)]
        n_samples = np.zeros(2, dtype=int)
        gaps = 0
        last_seq: int | None = None
        t_first: float | None = None
        t_last: float | None = None

        dev.start()
        t_end = time.monotonic() + args.seconds
        try:
            while time.monotonic() < t_end:
                for seq, rec in dev.read_data_frames():
                    if last_seq is not None and seq != (last_seq + 1) & 0xFFFF:
                        gaps += (seq - last_seq - 1) & 0xFFFF
                    last_seq = seq
                    t_s = unwrap.unwrap(rec["t_us"])
                    if len(t_s):
                        if t_first is None:
                            t_first = t_s[0]
                        t_last = t_s[-1]
                    for c in range(2):
                        n_samples[c] += int(np.sum(rec["ch"] == c))
                    if writer is not None:
                        v = rec["vbus_raw"] * proto.VBUS_LSB_V
                        for k in range(len(rec)):
                            ch = int(rec["ch"][k])
                            i_a = float(rec["curr_raw"][k]) * lsb[ch]
                            writer.writerow([
                                f"{t_s[k]:.6f}", ch, f"{v[k]:.6f}",
                                f"{i_a:.7f}", f"{v[k] * i_a:.7f}",
                            ])
        finally:
            dev.stop()
            cfg_after = dev.get_config()

        span = (t_last - t_first) if (t_first is not None and t_last is not None) else 0.0
        total = int(n_samples.sum())
        print(f"captured {total} samples in {span:.3f} s device-time"
              + (f" ({total / span:.1f} Sa/s aggregate)" if span > 0 else ""))
        for c in range(nch):
            if span > 0:
                print(f"  ch{c}: {n_samples[c]} samples, {n_samples[c] / span:.1f} Hz")
        print(f"frame gaps: {gaps}  device ring drops: {cfg_after.drops}")
        if args.csv:
            print(f"wrote {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
