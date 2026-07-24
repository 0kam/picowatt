"""Full-resolution sample store: preallocated per-channel ring buffers."""

from __future__ import annotations

import numpy as np


def unwrap_t_us(t_us: np.ndarray, last: int | None, offset: int) -> tuple[np.ndarray, int, int]:
    """Vectorized unwrap of the device's u32 microsecond timer.

    Returns (seconds_f64, new_last, new_offset). `offset` accumulates 2**32
    per wrap. Records arrive in acquisition order, so any large backwards jump
    is a wrap.
    """
    t = t_us.astype(np.int64)
    if len(t) == 0:
        return np.empty(0, dtype=np.float64), last, offset
    prev = np.empty(len(t), dtype=np.int64)
    prev[0] = t[0] if last is None else last
    prev[1:] = t[:-1]
    wraps = np.cumsum((t - prev) < -(2**31)) * (2**32)
    out = (t + offset + wraps) * 1e-6
    return out, int(t[-1]), int(offset + (wraps[-1] if len(wraps) else 0))


class ChannelBuffer:
    """Ring buffer of (t, v, i) columns for one channel."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.t = np.zeros(capacity, dtype=np.float64)
        self.v = np.zeros(capacity, dtype=np.float32)
        self.i = np.zeros(capacity, dtype=np.float32)
        self.write = 0  # next write index
        self.count = 0  # valid samples (<= capacity)

    def append(self, t: np.ndarray, v: np.ndarray, i: np.ndarray) -> None:
        n = len(t)
        if n == 0:
            return
        if n >= self.capacity:  # keep only the newest capacity samples
            t, v, i = t[-self.capacity:], v[-self.capacity:], i[-self.capacity:]
            n = self.capacity
        first = min(n, self.capacity - self.write)
        for dst, src in ((self.t, t), (self.v, v), (self.i, i)):
            dst[self.write : self.write + first] = src[:first]
            if n > first:
                dst[: n - first] = src[first:]
        self.write = (self.write + n) % self.capacity
        self.count = min(self.count + n, self.capacity)

    def view(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Time-ordered copies of the valid contents."""
        if self.count < self.capacity:
            sl = slice(0, self.write)
            return self.t[sl].copy(), self.v[sl].copy(), self.i[sl].copy()
        idx = np.r_[self.write : self.capacity, 0 : self.write]
        return self.t[idx], self.v[idx], self.i[idx]

    def window(self, t0: float, t1: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Samples with t0 <= t <= t1 (uses monotonicity of t)."""
        t, v, i = self.view()
        lo = np.searchsorted(t, t0, side="left")
        hi = np.searchsorted(t, t1, side="right")
        return t[lo:hi], v[lo:hi], i[lo:hi]

    def latest_t(self) -> float | None:
        if self.count == 0:
            return None
        return float(self.t[(self.write - 1) % self.capacity])
