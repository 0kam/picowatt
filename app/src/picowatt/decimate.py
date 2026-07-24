"""Min/max binning decimation for display (PPK2-style, spikes never vanish)."""

from __future__ import annotations

import numpy as np


def minmax_decimate(
    t: np.ndarray, y: np.ndarray, max_points: int
) -> tuple[np.ndarray, np.ndarray]:
    """Reduce (t, y) to <= 2*max_points points keeping per-bin min and max.

    Index-based binning (samples are near-uniform in time). Output stays
    time-ordered; each bin contributes its (min, max) pair in encounter order.
    """
    n = len(t)
    if n <= 2 * max_points or max_points < 1:
        return t, y
    per_bin = n // max_points
    m = per_bin * max_points
    yb = y[:m].reshape(max_points, per_bin)
    tb = t[:m].reshape(max_points, per_bin)

    arg_min = np.argmin(yb, axis=1)
    arg_max = np.argmax(yb, axis=1)
    rows = np.arange(max_points)

    # Keep min/max in temporal order within each bin.
    first = np.minimum(arg_min, arg_max)
    second = np.maximum(arg_min, arg_max)
    out_t = np.empty(2 * max_points, dtype=t.dtype)
    out_y = np.empty(2 * max_points, dtype=y.dtype)
    out_t[0::2] = tb[rows, first]
    out_t[1::2] = tb[rows, second]
    out_y[0::2] = yb[rows, first]
    out_y[1::2] = yb[rows, second]
    return out_t, out_y
