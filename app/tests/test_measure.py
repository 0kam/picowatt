"""Tests for region integration."""

import numpy as np

from picowatt.buffer import ChannelBuffer
from picowatt.measure import integrate_region


def _filled_buffer(rate_hz: float, seconds: float, v: float, i: float) -> ChannelBuffer:
    n = int(rate_hz * seconds)
    buf = ChannelBuffer(n + 10)
    t = np.arange(n, dtype=np.float64) / rate_hz
    buf.append(t, np.full(n, v, np.float32), np.full(n, i, np.float32))
    return buf


def test_constant_power_energy():
    # 5 V x 0.5 A = 2.5 W for 60 s -> 2.5 * 60/3600 Wh
    buf = _filled_buffer(1000.0, 60.0, 5.0, 0.5)
    r = integrate_region(buf, 0.0, 60.0)
    assert r is not None
    expected_wh = 2.5 * r.dt_s / 3600.0
    assert abs(r.wh - expected_wh) / expected_wh < 1e-6
    assert abs(r.avg_w - 2.5) < 1e-6
    assert abs(r.avg_i - 0.5) < 1e-6


def test_subrange_integration():
    buf = _filled_buffer(1000.0, 60.0, 5.0, 0.5)
    r = integrate_region(buf, 10.0, 20.0)
    assert r is not None
    assert abs(r.dt_s - 10.0) < 2e-3
    assert abs(r.wh - 2.5 * r.dt_s / 3600.0) < 1e-9


def test_region_with_no_data():
    buf = ChannelBuffer(10)
    assert integrate_region(buf, 0.0, 1.0) is None


def test_noise_averages_out():
    rng = np.random.default_rng(42)
    n = 100_000
    t = np.arange(n, dtype=np.float64) / 1000.0
    i = (0.5 + rng.normal(0, 0.01, n)).astype(np.float32)
    v = np.full(n, 5.0, np.float32)
    buf = ChannelBuffer(n + 1)
    buf.append(t, v, i)
    r = integrate_region(buf, 0.0, t[-1])
    assert r is not None
    assert abs(r.avg_i - 0.5) < 1e-3  # noise integrates away
