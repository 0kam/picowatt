"""Wire protocol codec, mirroring docs/protocol.md.

Pure functions / classes, no I/O — unit-testable without hardware.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from cobs import cobs

PROTO_VERSION = 1

# FW -> PC
FRAME_DATA = 0x01
FRAME_ACK = 0x80
FRAME_NACK = 0x81
FRAME_HELLO_ACK = 0x90
FRAME_CONFIG = 0x96

# PC -> FW
FRAME_HELLO = 0x10
FRAME_START = 0x11
FRAME_STOP = 0x12
FRAME_SET_MODE = 0x13
FRAME_SET_ADC = 0x14
FRAME_SET_SHUNT_CAL = 0x15
FRAME_GET_CONFIG = 0x16
FRAME_REBOOT_BOOTSEL = 0x1F

NACK_ERRORS = {1: "bad param", 2: "channel absent", 3: "unknown cmd", 4: "bad length"}

VBUS_LSB_V = 195.3125e-6
CURRENT_LSB_A = {0: 8e-6, 1: 2e-6}  # by adcrange

# CT code -> microseconds, AVG code -> count (INA228 datasheet)
CT_US = [50, 84, 150, 280, 540, 1052, 2074, 4120]
AVG_COUNT = [1, 4, 16, 64, 128, 256, 512, 1024]

# name -> (ct_code, avg_code)
PRESETS = {
    "fast": (2, 0),        # ~3.3 kHz, single-channel only
    "fast-dual": (3, 0),   # ~1.8 kHz
    "normal": (4, 0),      # ~925 Hz
    "quiet": (5, 1),       # ~119 Hz
    "very-quiet": (7, 2),  # ~7.6 Hz
}

RECORD_DTYPE = np.dtype(
    [("ch", "u1"), ("t_us", "<u4"), ("vbus_raw", "<i4"), ("curr_raw", "<i4")]
)


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode_frame(ftype: int, payload: bytes = b"") -> bytes:
    raw = bytes([ftype]) + payload
    raw += crc16_ccitt(raw).to_bytes(2, "little")
    return cobs.encode(raw) + b"\x00"


class Decoder:
    """Incremental frame decoder. Feed bytes, get (type, payload) tuples."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[tuple[int, bytes]]:
        frames: list[tuple[int, bytes]] = []
        self._buf.extend(data)
        while True:
            idx = self._buf.find(0)
            if idx < 0:
                break
            chunk = bytes(self._buf[:idx])
            del self._buf[: idx + 1]
            if not chunk:
                continue
            try:
                raw = cobs.decode(chunk)
            except cobs.DecodeError:
                continue
            if len(raw) < 3:
                continue
            if crc16_ccitt(raw[:-2]) != int.from_bytes(raw[-2:], "little"):
                continue
            frames.append((raw[0], raw[1:-2]))
        return frames


@dataclass
class HelloAck:
    proto_ver: int
    fw_version: tuple[int, int, int]
    board_id: str  # hex
    ch_present: int

    @classmethod
    def parse(cls, payload: bytes) -> HelloAck:
        if len(payload) != 13:
            raise ValueError(f"HELLO_ACK length {len(payload)} != 13")
        return cls(
            proto_ver=payload[0],
            fw_version=(payload[1], payload[2], payload[3]),
            board_id=payload[4:12].hex(),
            ch_present=payload[12],
        )


@dataclass
class ChannelConfig:
    present: bool
    adcrange: int
    vbusct: int
    vshct: int
    avg: int
    shunt_cal: int

    @property
    def current_lsb(self) -> float:
        return CURRENT_LSB_A[self.adcrange]

    @property
    def sample_period_s(self) -> float:
        return (CT_US[self.vbusct] + CT_US[self.vshct]) * AVG_COUNT[self.avg] * 1e-6


@dataclass
class Config:
    mode: int  # 0 single, 1 dual
    streaming: bool
    drops: int
    ch: tuple[ChannelConfig, ChannelConfig]

    @classmethod
    def parse(cls, payload: bytes) -> Config:
        if len(payload) != 20:
            raise ValueError(f"CONFIG length {len(payload)} != 20")
        chans = []
        for c in range(2):
            b = payload[6 + c * 7 : 6 + (c + 1) * 7]
            chans.append(
                ChannelConfig(
                    present=bool(b[0]),
                    adcrange=b[1],
                    vbusct=b[2],
                    vshct=b[3],
                    avg=b[4],
                    shunt_cal=int.from_bytes(b[5:7], "little"),
                )
            )
        return cls(
            mode=payload[0],
            streaming=bool(payload[1]),
            drops=int.from_bytes(payload[2:6], "little"),
            ch=(chans[0], chans[1]),
        )


def parse_data_frame(payload: bytes) -> tuple[int, np.ndarray]:
    """Return (frame_seq, records) from a DATA frame payload."""
    if len(payload) < 3:
        raise ValueError("DATA frame too short")
    frame_seq = int.from_bytes(payload[0:2], "little")
    count = payload[2]
    body = payload[3:]
    if len(body) != count * RECORD_DTYPE.itemsize:
        raise ValueError(f"DATA frame: {count} records but {len(body)} bytes")
    records = np.frombuffer(body, dtype=RECORD_DTYPE)
    return frame_seq, records


# Command payload builders

def cmd_hello() -> bytes:
    return encode_frame(FRAME_HELLO, bytes([PROTO_VERSION]))


def cmd_start() -> bytes:
    return encode_frame(FRAME_START)


def cmd_stop() -> bytes:
    return encode_frame(FRAME_STOP)


def cmd_set_mode(mode: int) -> bytes:
    return encode_frame(FRAME_SET_MODE, bytes([mode]))


def cmd_set_adc(ch: int, adcrange: int, vbusct: int, vshct: int, avg: int) -> bytes:
    return encode_frame(FRAME_SET_ADC, bytes([ch, adcrange, vbusct, vshct, avg]))


def cmd_set_shunt_cal(ch: int, val: int) -> bytes:
    return encode_frame(FRAME_SET_SHUNT_CAL, bytes([ch]) + val.to_bytes(2, "little"))


def cmd_get_config() -> bytes:
    return encode_frame(FRAME_GET_CONFIG)


def cmd_reboot_bootsel() -> bytes:
    return encode_frame(FRAME_REBOOT_BOOTSEL)
