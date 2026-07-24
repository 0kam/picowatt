"""Unit tests for the wire protocol codec (no hardware required)."""

import numpy as np
import pytest

from picowatt import protocol as proto


def test_crc16_known_vector():
    # CRC-16/CCITT-FALSE of "123456789" is 0x29B1
    assert proto.crc16_ccitt(b"123456789") == 0x29B1


def test_encode_decode_roundtrip():
    dec = proto.Decoder()
    frame = proto.encode_frame(proto.FRAME_HELLO, bytes([proto.PROTO_VERSION]))
    frames = dec.feed(frame)
    assert frames == [(proto.FRAME_HELLO, bytes([proto.PROTO_VERSION]))]


def test_roundtrip_with_zeros_in_payload():
    dec = proto.Decoder()
    payload = bytes([0, 1, 0, 0, 255, 0])
    frames = dec.feed(proto.encode_frame(0x42, payload))
    assert frames == [(0x42, payload)]


def test_decoder_resyncs_after_garbage():
    dec = proto.Decoder()
    good = proto.encode_frame(proto.FRAME_START)
    frames = dec.feed(b"\x13\x37\xde\xad" + b"\x00" + good)
    assert frames == [(proto.FRAME_START, b"")]


def test_decoder_rejects_corrupt_crc():
    frame = bytearray(proto.encode_frame(proto.FRAME_START))
    frame[1] ^= 0xFF
    assert proto.Decoder().feed(bytes(frame)) == []


def test_decoder_handles_split_delivery():
    dec = proto.Decoder()
    frame = proto.encode_frame(0x11, b"")
    assert dec.feed(frame[:2]) == []
    assert dec.feed(frame[2:]) == [(0x11, b"")]


def test_parse_data_frame():
    rec = np.zeros(2, dtype=proto.RECORD_DTYPE)
    rec["ch"] = [0, 1]
    rec["t_us"] = [1000, 2000]
    rec["vbus_raw"] = [25000, -12]
    rec["curr_raw"] = [-62000, 7]
    payload = (1234).to_bytes(2, "little") + bytes([2]) + rec.tobytes()
    seq, out = proto.parse_data_frame(payload)
    assert seq == 1234
    assert np.array_equal(out, rec)


def test_parse_data_frame_length_mismatch():
    with pytest.raises(ValueError):
        proto.parse_data_frame(b"\x00\x00\x05" + b"\x00" * 13)


def test_record_is_13_bytes():
    assert proto.RECORD_DTYPE.itemsize == 13


def test_hello_ack_parse():
    payload = bytes([1, 0, 1, 0]) + bytes(range(8)) + bytes([0b11])
    h = proto.HelloAck.parse(payload)
    assert h.proto_ver == 1
    assert h.fw_version == (0, 1, 0)
    assert h.board_id == "0001020304050607"
    assert h.ch_present == 0b11


def test_config_parse_roundtrip():
    per_ch = bytes([1, 0, 3, 3, 0]) + (1573).to_bytes(2, "little")
    payload = bytes([1, 1]) + (42).to_bytes(4, "little") + per_ch + per_ch
    cfg = proto.Config.parse(payload)
    assert cfg.mode == 1 and cfg.streaming and cfg.drops == 42
    assert cfg.ch[0].shunt_cal == 1573
    assert cfg.ch[0].current_lsb == 8e-6
    assert abs(cfg.ch[0].sample_period_s - 560e-6) < 1e-9


def test_cobs_max_block_boundary():
    # 254+ bytes of nonzero data exercises the 0xFF COBS block path
    payload = bytes(range(1, 255)) + bytes(range(1, 100))
    dec = proto.Decoder()
    assert dec.feed(proto.encode_frame(0x01, payload)) == [(0x01, payload)]
