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


@dataclass
class VbusHealth:
    """Plausibility check of a bus-voltage record (see :func:`check_vbus`)."""

    mean: float
    sd: float
    vmin: float
    vmax: float
    problem: str | None  # None when the bus looks like a real DC supply

    @property
    def ok(self) -> bool:
        return self.problem is None


def check_vbus(v: np.ndarray) -> VbusHealth:
    """Flag a bus voltage that cannot be a real DC supply.

    Two symptoms are caught, both produced by a floating measurement node
    (the supply "-" not tied to the GND terminal, or the VBus jumper left
    open) picking up mains hum:

    * the bus goes clearly negative -- impossible in the high-side hookup;
    * the bus swings by more than a few percent of its magnitude.

    The check is deliberately sign-agnostic: a 0 V ... -53 V, 50 Hz swing
    averages to roughly -26 V, so a test on the mean alone would miss it.
    """
    v = np.asarray(v, dtype=np.float64)
    if v.size == 0:
        return VbusHealth(np.nan, np.nan, np.nan, np.nan, None)
    mean, sd = float(v.mean()), float(v.std())
    vmin, vmax = float(v.min()), float(v.max())
    problem = None
    if vmin < -1.0:
        problem = f"bus voltage goes negative (min {vmin:.1f} V)"
    elif abs(mean) > 0.5 and sd > max(0.05, 0.02 * abs(mean)):
        problem = f"bus voltage is unstable (sd {sd:.2f} V, {100 * sd / abs(mean):.0f}% of mean)"
    return VbusHealth(mean, sd, vmin, vmax, problem)
