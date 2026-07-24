"""Tests for the calibration store."""

from pathlib import Path

from picowatt.calibration import CalibrationStore, ChannelCal


def test_defaults(tmp_path: Path):
    store = CalibrationStore(tmp_path / "cal.json")
    cal = store.get("aabb", 0)
    assert cal.shunt_cal == 1573
    assert cal.offset_for(0) == 0.0


def test_roundtrip_persistence(tmp_path: Path):
    path = tmp_path / "cal.json"
    store = CalibrationStore(path)
    store.set("board1", 0, ChannelCal(shunt_cal=1600, zero_offset_a={0: 12e-6}))
    store.set_zero_offset("board1", 1, 1, -5e-6)
    store.set_shunt_cal("board1", 1, 1590)

    reloaded = CalibrationStore(path)
    assert reloaded.get("board1", 0).shunt_cal == 1600
    assert reloaded.get("board1", 0).offset_for(0) == 12e-6
    assert reloaded.get("board1", 0).offset_for(1) == 0.0  # per-range isolation
    assert reloaded.get("board1", 1).shunt_cal == 1590
    assert reloaded.get("board1", 1).offset_for(1) == -5e-6
    assert reloaded.get("other", 0).shunt_cal == 1573  # unknown board -> defaults


def test_corrupt_file_is_ignored(tmp_path: Path):
    path = tmp_path / "cal.json"
    path.write_text("{not json")
    store = CalibrationStore(path)
    assert store.get("x", 0).shunt_cal == 1573
