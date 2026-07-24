"""Per-device calibration profiles, stored as JSON keyed by board_id.

Gain lives in the device's SHUNT_CAL register (pushed on every connect);
zero offset is applied PC-side to converted current. Offsets are stored per
ADC range because the raw ADC offset scales differently in each range.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

DEFAULT_SHUNT_CAL = 1573


@dataclass
class ChannelCal:
    shunt_cal: int = DEFAULT_SHUNT_CAL
    # adcrange (as str key in JSON) -> offset in amps
    zero_offset_a: dict[int, float] = field(default_factory=dict)

    def offset_for(self, adcrange: int) -> float:
        return self.zero_offset_a.get(adcrange, 0.0)


class CalibrationStore:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            path = Path(platformdirs.user_config_dir("picowatt")) / "calibration.json"
        self.path = path
        self._data: dict[str, dict[str, ChannelCal]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        for board, chans in raw.items():
            self._data[board] = {
                ch: ChannelCal(
                    shunt_cal=int(c.get("shunt_cal", DEFAULT_SHUNT_CAL)),
                    zero_offset_a={int(k): float(v)
                                   for k, v in c.get("zero_offset_a", {}).items()},
                )
                for ch, c in chans.items()
            }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            board: {
                ch: {"shunt_cal": c.shunt_cal, "zero_offset_a": c.zero_offset_a}
                for ch, c in chans.items()
            }
            for board, chans in self._data.items()
        }
        self.path.write_text(json.dumps(raw, indent=2))

    def get(self, board_id: str, ch: int) -> ChannelCal:
        return self._data.get(board_id, {}).get(str(ch), ChannelCal())

    def set(self, board_id: str, ch: int, cal: ChannelCal) -> None:
        self._data.setdefault(board_id, {})[str(ch)] = cal
        self.save()

    def set_shunt_cal(self, board_id: str, ch: int, shunt_cal: int) -> None:
        cal = self.get(board_id, ch)
        cal.shunt_cal = shunt_cal
        self.set(board_id, ch, cal)

    def set_zero_offset(self, board_id: str, ch: int, adcrange: int, offset_a: float) -> None:
        cal = self.get(board_id, ch)
        cal.zero_offset_a[adcrange] = offset_a
        self.set(board_id, ch, cal)
