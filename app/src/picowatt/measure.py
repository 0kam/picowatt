"""Region measurements: energy/charge integration over a time span."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .buffer import ChannelBuffer


@dataclass
class RegionResult:
    n: int
    dt_s: float
    avg_v: float
    avg_i: float
    avg_w: float
    wh: float
    ah: float


def integrate_region(buf: ChannelBuffer, t0: float, t1: float) -> RegionResult | None:
    """Trapezoidal integral of power/current over [t0, t1], full resolution."""
    t, v, i = buf.window(t0, t1)
    if len(t) < 2:
        return None
    p = v.astype(np.float64) * i.astype(np.float64)
    i64 = i.astype(np.float64)
    dt = float(t[-1] - t[0])
    if dt <= 0:
        return None
    joules = float(np.trapezoid(p, t))
    coulombs = float(np.trapezoid(i64, t))
    return RegionResult(
        n=len(t),
        dt_s=dt,
        avg_v=float(np.mean(v)),
        avg_i=coulombs / dt,
        avg_w=joules / dt,
        wh=joules / 3600.0,
        ah=coulombs / 3600.0,
    )
