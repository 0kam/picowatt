// Wire protocol implementation.
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include "proto.h"

#include <string.h>

uint16_t crc16_ccitt(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; b++) {
            crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

// COBS encode src[0..len) into dst; returns encoded length (no trailing zero).
static size_t cobs_encode(const uint8_t *src, size_t len, uint8_t *dst) {
    size_t out = 0;
    size_t code_pos = out++;
    uint8_t code = 1;
    for (size_t i = 0; i < len; i++) {
        if (src[i] == 0) {
            dst[code_pos] = code;
            code_pos = out++;
            code = 1;
        } else {
            dst[out++] = src[i];
            if (++code == 0xFF) {
                dst[code_pos] = code;
                code_pos = out++;
                code = 1;
            }
        }
    }
    dst[code_pos] = code;
    return out;
}

// COBS decode src[0..len) (no trailing zero) into dst; returns decoded length
// or 0 on malformed input.
static size_t cobs_decode(const uint8_t *src, size_t len, uint8_t *dst) {
    size_t out = 0, i = 0;
    while (i < len) {
        uint8_t code = src[i++];
        if (code == 0 || i + code - 1 > len) return 0;
        for (uint8_t j = 1; j < code; j++) dst[out++] = src[i++];
        if (code != 0xFF && i < len) dst[out++] = 0;
    }
    return out;
}

size_t proto_encode(uint8_t type, const uint8_t *payload, size_t payload_len,
                    uint8_t *out, size_t out_cap) {
    uint8_t raw[PROTO_MAX_FRAME];
    if (payload_len + 3 > sizeof raw) return 0;
    raw[0] = type;
    memcpy(raw + 1, payload, payload_len);
    uint16_t crc = crc16_ccitt(raw, payload_len + 1);
    raw[payload_len + 1] = (uint8_t)(crc & 0xFF);
    raw[payload_len + 2] = (uint8_t)(crc >> 8);

    size_t raw_len = payload_len + 3;
    // COBS worst case: len + len/254 + 1, plus trailing zero
    if (raw_len + raw_len / 254 + 2 > out_cap) return 0;
    size_t enc = cobs_encode(raw, raw_len, out);
    out[enc++] = 0x00;
    return enc;
}

void proto_decoder_init(proto_decoder_t *dec) {
    dec->raw_len = 0;
    dec->overflow = false;
}

bool proto_decoder_feed(proto_decoder_t *dec, uint8_t byte) {
    if (byte != 0x00) {
        if (dec->raw_len < sizeof dec->raw) {
            dec->raw[dec->raw_len++] = byte;
        } else {
            dec->overflow = true;
        }
        return false;
    }

    // Delimiter: try to decode what we accumulated.
    size_t raw_len = dec->raw_len;
    bool overflow = dec->overflow;
    dec->raw_len = 0;
    dec->overflow = false;
    if (overflow || raw_len == 0) return false;

    uint8_t decoded[PROTO_MAX_FRAME + 8];
    size_t n = cobs_decode(dec->raw, raw_len, decoded);
    if (n < 3) return false;  // need at least type + crc16

    uint16_t crc = crc16_ccitt(decoded, n - 2);
    uint16_t rx_crc = (uint16_t)(decoded[n - 2] | (decoded[n - 1] << 8));
    if (crc != rx_crc) return false;

    dec->type = decoded[0];
    dec->payload_len = n - 3;
    memcpy(dec->payload, decoded + 1, dec->payload_len);
    return true;
}
