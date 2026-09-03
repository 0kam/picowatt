"""Tests for the bus-voltage plausibility check."""

import numpy as np

from picowatt.measure import check_vbus


def _mains(v_lo: float, v_hi: float, hz: float = 50.0, rate: float = 1000.0, seconds: float = 2.0):
    t = np.arange(int(rate * seconds)) / rate
    return (v_hi + v_lo) / 2 + (v_hi - v_lo) / 2 * np.sin(2 * np.pi * hz * t)


def test_clean_supply_is_ok():
    v = 5.0 + np.random.default_rng(0).normal(0, 1.4e-3, 5000)
    assert check_vbus(v).ok


def test_zero_volts_with_noise_is_ok():
    # Supply off: tiny noise around 0 V must not trip the relative test.
    v = np.random.default_rng(1).normal(0, 2e-3, 5000)
    assert check_vbus(v).ok


def test_floating_gnd_negative_swing_is_flagged():
    # The real-world case: GND link forgotten, 0 V ... -53 V at 50 Hz.
    # Mean is about -26 V, so a mean>0 gate alone would miss this.
    h = check_vbus(_mains(-53.0, 0.0))
    assert not h.ok
    assert "negative" in h.problem


def test_positive_hum_is_flagged():
    h = check_vbus(_mains(0.0, 40.0))
    assert not h.ok
    assert "unstable" in h.problem


def test_small_ripple_is_ok():
    # 1 % ripple on 12 V is a normal switching supply, not a wiring fault.
    assert check_vbus(_mains(11.94, 12.06)).ok


def test_empty_input():
    assert check_vbus(np.array([])).ok
