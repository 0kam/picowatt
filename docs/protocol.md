# picowatt serial protocol v1

Binary protocol over USB CDC. This document is the single source of truth;
`firmware/src/proto.*` and `app/src/picowatt/protocol.py` implement it.

## Framing

Every frame is COBS-encoded and terminated with a single `0x00` byte.
COBS guarantees no `0x00` inside the encoded frame, so a receiver can always
resynchronize at the next zero byte.

Unencoded frame layout (before COBS):

```
type:u8 | payload:u8[] | crc16:u16le
```

- `crc16` = CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection,
  no final xor) computed over `type + payload`.
- All multi-byte integers are **little-endian**.
- Maximum unencoded frame size: 300 bytes.

## Frame types

### FW → PC

| Type | Name | Payload |
|---|---|---|
| 0x01 | DATA | `frame_seq:u16` `count:u8` then `count` × record (13 B, below) |
| 0x80 | ACK | `cmd:u8` (the command type being acknowledged) |
| 0x81 | NACK | `cmd:u8` `err:u8` (1=bad param, 2=channel absent, 3=unknown cmd, 4=bad length) |
| 0x90 | HELLO_ACK | `proto_ver:u8` `fw_major:u8` `fw_minor:u8` `fw_patch:u8` `board_id:u8[8]` `ch_present:u8` (bitmask: bit0=ch0, bit1=ch1) |
| 0x96 | CONFIG | `mode:u8` `streaming:u8` `drops:u32` then 2 × per-channel block (7 B, below) |

DATA record (13 bytes):

```
ch:u8        0 = input side (0x40), 1 = output side (0x41)
t_us:u32     device microsecond timer at CNVRF detection; wraps every ~71.6 min
vbus_raw:i32 VBUS register, 20-bit sign-extended counts. LSB = 195.3125 µV
curr_raw:i32 CURRENT register, 20-bit sign-extended counts.
             LSB = 8 µA (ADCRANGE=0) or 2 µA (ADCRANGE=1)
```

`frame_seq` increments by 1 per DATA frame (wraps at 65535). A gap means
dropped frames. Records within a frame are in acquisition order but may
interleave channels.

CONFIG per-channel block (7 bytes):

```
present:u8  adcrange:u8  vbusct:u8  vshct:u8  avg:u8  shunt_cal:u16
```

`vbusct`/`vshct`/`avg` are raw INA228 field codes (datasheet tables 7-x):
CT: 0=50µs 1=84µs 2=150µs 3=280µs 4=540µs 5=1052µs 6=2074µs 7=4120µs;
AVG: 0=1 1=4 2=16 3=64 4=128 5=256 6=512 7=1024.

### PC → FW

| Type | Name | Payload | Response |
|---|---|---|---|
| 0x10 | HELLO | `proto_ver:u8` | HELLO_ACK (NACK if version mismatch) |
| 0x11 | START | — | ACK; DATA frames begin |
| 0x12 | STOP | — | ACK; DATA frames cease |
| 0x13 | SET_MODE | `mode:u8` (0=single, 1=dual) | ACK / NACK(2) if ch1 absent |
| 0x14 | SET_ADC | `ch:u8` (0/1/0xFF=both) `adcrange:u8` `vbusct:u8` `vshct:u8` `avg:u8` | ACK |
| 0x15 | SET_SHUNT_CAL | `ch:u8` `val:u16` | ACK |
| 0x16 | GET_CONFIG | — | CONFIG |
| 0x1F | REBOOT_BOOTSEL | — | (no response; device reboots into BOOTSEL for flashing) |

Setting `bit_rate` to 1200 baud on the CDC line coding also reboots into
BOOTSEL (Arduino-style touch reset).

## Session flow

```
PC opens port
PC → HELLO(proto_ver=1)         ← must ACK within 500 ms with matching version
PC → GET_CONFIG                 ← learn mode / ranges / shunt_cal
PC → SET_SHUNT_CAL, SET_ADC ... ← push stored calibration & settings
PC → START                      ← DATA frames stream until STOP
```

The device is stateless across power cycles (no flash writes); the PC re-pushes
configuration on every connect. `GET_CONFIG` is the source of truth for
converting `curr_raw` (CURRENT_LSB depends on ADCRANGE).

## Rate presets (PC-side convenience, both channels)

| Preset | CT code | AVG code | Rate/ch approx. |
|---|---|---|---|
| fast (single only) | 2 (150 µs) | 0 | ~3.3 kHz |
| fast-dual (default) | 3 (280 µs) | 0 | ~1.8 kHz |
| normal | 4 (540 µs) | 0 | ~925 Hz |
| quiet | 5 (1052 µs) | 1 (4×) | ~119 Hz |
| very-quiet | 7 (4120 µs) | 2 (16×) | ~7.6 Hz |
