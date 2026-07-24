"""Device discovery, handshake, and command API over pyserial."""

from __future__ import annotations

import time
from typing import Self

import serial
from serial.tools import list_ports

from . import protocol as proto

PICO_VID = 0x2E8A
PRODUCT_NAME = "picowatt"


class DeviceError(RuntimeError):
    pass


def find_ports() -> list[str]:
    """Ports that look like a picowatt device (product string match first)."""
    named, fallback = [], []
    for p in list_ports.comports():
        if p.vid != PICO_VID:
            continue
        if p.product and PRODUCT_NAME in p.product.lower():
            named.append(p.device)
        else:
            fallback.append(p.device)
    return named + fallback


class Device:
    """Synchronous picowatt session: handshake, commands, sample reads."""

    def __init__(self, port: str | None = None, timeout: float = 0.5) -> None:
        if port is None:
            ports = find_ports()
            if not ports:
                raise DeviceError("no picowatt device found (VID 0x2E8A)")
            port = ports[0]
        self.ser = serial.Serial(port, 115200, timeout=timeout)
        self.decoder = proto.Decoder()
        self.hello: proto.HelloAck | None = None
        self.config: proto.Config | None = None
        self._pending: list[tuple[int, bytes]] = []

    def close(self) -> None:
        self.ser.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- frame plumbing ----------------------------------------------------

    def _read_frames(self) -> list[tuple[int, bytes]]:
        data = self.ser.read(4096)
        return self.decoder.feed(data) if data else []

    def _wait_for(self, ftype: int, deadline_s: float = 0.5) -> bytes:
        """Return payload of the next frame of ftype; buffer DATA frames seen."""
        t0 = time.monotonic()
        while time.monotonic() - t0 < deadline_s:
            for ft, payload in self._read_frames():
                if ft == ftype:
                    return payload
                if ft == proto.FRAME_NACK and len(payload) == 2:
                    err = proto.NACK_ERRORS.get(payload[1], str(payload[1]))
                    raise DeviceError(f"NACK for cmd 0x{payload[0]:02X}: {err}")
                if ft == proto.FRAME_DATA:
                    self._pending.append((ft, payload))
        raise DeviceError(f"timeout waiting for frame 0x{ftype:02X}")

    def _command(self, frame: bytes, cmd_type: int) -> None:
        self.ser.write(frame)
        payload = self._wait_for(proto.FRAME_ACK)
        if payload and payload[0] != cmd_type:
            raise DeviceError(
                f"ACK for 0x{payload[0]:02X}, expected 0x{cmd_type:02X}"
            )

    # -- session -----------------------------------------------------------

    def connect(self) -> proto.HelloAck:
        self.ser.reset_input_buffer()
        self.decoder = proto.Decoder()
        self.ser.write(proto.cmd_hello())
        self.hello = proto.HelloAck.parse(self._wait_for(proto.FRAME_HELLO_ACK))
        self.get_config()
        return self.hello

    def get_config(self) -> proto.Config:
        self.ser.write(proto.cmd_get_config())
        self.config = proto.Config.parse(self._wait_for(proto.FRAME_CONFIG))
        return self.config

    def start(self) -> None:
        self._command(proto.cmd_start(), proto.FRAME_START)

    def stop(self) -> None:
        self._command(proto.cmd_stop(), proto.FRAME_STOP)
        # drain in-flight DATA so the next session starts clean
        time.sleep(0.05)
        self.ser.reset_input_buffer()
        self._pending.clear()

    def set_mode(self, mode: int) -> None:
        self._command(proto.cmd_set_mode(mode), proto.FRAME_SET_MODE)
        self.get_config()

    def set_adc(self, ch: int, adcrange: int, vbusct: int, vshct: int, avg: int) -> None:
        self._command(
            proto.cmd_set_adc(ch, adcrange, vbusct, vshct, avg), proto.FRAME_SET_ADC
        )
        self.get_config()

    def set_preset(self, name: str, adcrange: int = 0) -> None:
        ct, avg = proto.PRESETS[name]
        self.set_adc(0xFF, adcrange, ct, ct, avg)

    def set_shunt_cal(self, ch: int, val: int) -> None:
        self._command(proto.cmd_set_shunt_cal(ch, val), proto.FRAME_SET_SHUNT_CAL)
        self.get_config()

    def reboot_bootsel(self) -> None:
        self.ser.write(proto.cmd_reboot_bootsel())
        self.ser.flush()

    def read_data_frames(self):
        """Yield (frame_seq, records) for all complete DATA frames available now."""
        pending, self._pending = self._pending, []
        for _, payload in pending:
            yield proto.parse_data_frame(payload)
        for ft, payload in self._read_frames():
            if ft == proto.FRAME_DATA:
                yield proto.parse_data_frame(payload)
