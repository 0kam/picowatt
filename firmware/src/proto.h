// Wire protocol: COBS framing + CRC16-CCITT (docs/protocol.md).
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#ifndef PICOWATT_PROTO_H
#define PICOWATT_PROTO_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PROTO_VERSION 1

// Frame types FW -> PC
#define FRAME_DATA          0x01
#define FRAME_ACK           0x80
#define FRAME_NACK          0x81
#define FRAME_HELLO_ACK     0x90
#define FRAME_CONFIG        0x96

// Frame types PC -> FW
#define FRAME_HELLO         0x10
#define FRAME_START         0x11
#define FRAME_STOP          0x12
#define FRAME_SET_MODE      0x13
#define FRAME_SET_ADC       0x14
#define FRAME_SET_SHUNT_CAL 0x15
#define FRAME_GET_CONFIG    0x16
#define FRAME_REBOOT_BOOTSEL 0x1F

// NACK error codes
#define NACK_BAD_PARAM   1
#define NACK_CH_ABSENT   2
#define NACK_UNKNOWN_CMD 3
#define NACK_BAD_LENGTH  4

#define PROTO_MAX_FRAME 300  // unencoded: type + payload + crc

uint16_t crc16_ccitt(const uint8_t *data, size_t len);

// Encode type+payload into `out` as COBS(type|payload|crc16le) + 0x00.
// Returns bytes written, or 0 if it would exceed out_cap.
size_t proto_encode(uint8_t type, const uint8_t *payload, size_t payload_len,
                    uint8_t *out, size_t out_cap);

// Incremental decoder: feed bytes one at a time; returns true when a complete,
// CRC-valid frame is available in dec->type / dec->payload / dec->payload_len.
// Invalid frames (bad COBS or CRC) are discarded silently.
typedef struct {
    uint8_t raw[PROTO_MAX_FRAME + 8];  // COBS-encoded accumulation
    size_t raw_len;
    bool overflow;
    uint8_t type;
    uint8_t payload[PROTO_MAX_FRAME];
    size_t payload_len;
} proto_decoder_t;

void proto_decoder_init(proto_decoder_t *dec);
bool proto_decoder_feed(proto_decoder_t *dec, uint8_t byte);

#endif // PICOWATT_PROTO_H
