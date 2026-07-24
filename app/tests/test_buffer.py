"""Tests for the ring buffer, time unwrap, and decimation."""

import numpy as np

from picowatt.buffer import ChannelBuffer, unwrap_t_us
from picowatt.decimate import minmax_decimate


def test_unwrap_monotonic():
    t = np.array([100, 200, 300], dtype=np.uint32)
    out, last, off = unwrap_t_us(t, None, 0)
    assert np.allclose(out, [100e-6, 200e-6, 300e-6])
    assert last == 300 and off == 0


def test_unwrap_across_wrap():
    t = np.array([2**32 - 100, 50, 200], dtype=np.uint32)
    out, _last, off = unwrap_t_us(t, None, 0)
    assert np.allclose(out, [(2**32 - 100) * 1e-6, (2**32 + 50) * 1e-6, (2**32 + 200) * 1e-6])
    assert off == 2**32


def test_unwrap_stateful_between_batches():
    out1, last, off = unwrap_t_us(np.array([2**32 - 10], dtype=np.uint32), None, 0)
    out2, last, off = unwrap_t_us(np.array([5], dtype=np.uint32), last, off)
    assert out2[0] > out1[0]


def test_channel_buffer_wraps():
    buf = ChannelBuffer(100)
    for k in range(3):
        t = np.arange(k * 60, (k + 1) * 60, dtype=np.float64)
        buf.append(t, t.astype(np.float32), t.astype(np.float32))
    t, _v, _i = buf.view()
    assert len(t) == 100
    assert t[0] == 80.0 and t[-1] == 179.0  # newest 100 of 180
    assert np.all(np.diff(t) > 0)


def test_channel_buffer_window():
    buf = ChannelBuffer(1000)
    t = np.arange(100, dtype=np.float64)
    buf.append(t, t.astype(np.float32), t.astype(np.float32))
    tw, _vw, _iw = buf.window(10.0, 20.0)
    assert tw[0] == 10.0 and tw[-1] == 20.0 and len(tw) == 11


def test_channel_buffer_oversize_append():
    buf = ChannelBuffer(50)
    t = np.arange(200, dtype=np.float64)
    buf.append(t, t.astype(np.float32), t.astype(np.float32))
    tv, _, _ = buf.view()
    assert len(tv) == 50 and tv[-1] == 199.0 and tv[0] == 150.0


def test_minmax_decimate_preserves_spike():
    t = np.arange(100_000, dtype=np.float64)
    y = np.zeros(100_000)
    y[54_321] = 42.0  # single-sample spike must survive
    td, yd = minmax_decimate(t, y, 500)
    assert len(td) == 1000
    assert yd.max() == 42.0
    assert np.all(np.diff(td) >= 0)


def test_minmax_decimate_passthrough_when_small():
    t = np.arange(100, dtype=np.float64)
    y = t * 2
    td, yd = minmax_decimate(t, y, 500)
    assert np.array_equal(td, t) and np.array_equal(yd, y)
