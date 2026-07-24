// Command dispatch (core0).
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include "commands.h"

#include <string.h>
#include "pico/bootrom.h"
#include "pico/unique_id.h"
#include "tusb.h"
#include "config.h"
#include "proto.h"
#include "ring.h"
#include "sampler.h"

void commands_send_frame(uint8_t type, const uint8_t *payload, size_t len) {
    uint8_t enc[PROTO_MAX_FRAME + PROTO_MAX_FRAME / 254 + 4];
    size_t n = proto_encode(type, payload, len, enc, sizeof enc);
    if (n == 0) return;
    if (tud_cdc_write_available() < n) return;  // drop rather than block
    tud_cdc_write(enc, n);
    tud_cdc_write_flush();
}

static void send_ack(uint8_t cmd) {
    commands_send_frame(FRAME_ACK, &cmd, 1);
}

static void send_nack(uint8_t cmd, uint8_t err) {
    uint8_t pl[2] = {cmd, err};
    commands_send_frame(FRAME_NACK, pl, 2);
}

static void handle_hello(const uint8_t *pl, size_t len) {
    if (len != 1) { send_nack(FRAME_HELLO, NACK_BAD_LENGTH); return; }
    if (pl[0] != PROTO_VERSION) { send_nack(FRAME_HELLO, NACK_BAD_PARAM); return; }

    uint8_t out[13];
    out[0] = PROTO_VERSION;
    out[1] = FW_VERSION_MAJOR;
    out[2] = FW_VERSION_MINOR;
    out[3] = FW_VERSION_PATCH;
    pico_unique_board_id_t id;
    pico_get_unique_board_id(&id);
    memcpy(out + 4, id.id, 8);
    out[12] = sampler_ch_present();
    commands_send_frame(FRAME_HELLO_ACK, out, sizeof out);
}

static void handle_set_mode(const uint8_t *pl, size_t len) {
    if (len != 1) { send_nack(FRAME_SET_MODE, NACK_BAD_LENGTH); return; }
    if (pl[0] > 1) { send_nack(FRAME_SET_MODE, NACK_BAD_PARAM); return; }
    if (pl[0] == 1 && !(sampler_ch_present() & 2)) {
        send_nack(FRAME_SET_MODE, NACK_CH_ABSENT);
        return;
    }
    g_state.mode = pl[0];
    g_state.config_seq++;
    send_ack(FRAME_SET_MODE);
}

static void handle_set_adc(const uint8_t *pl, size_t len) {
    if (len != 5) { send_nack(FRAME_SET_ADC, NACK_BAD_LENGTH); return; }
    uint8_t ch = pl[0];
    if ((ch > 1 && ch != 0xFF) || pl[1] > 1 || pl[2] > 7 || pl[3] > 7 || pl[4] > 7) {
        send_nack(FRAME_SET_ADC, NACK_BAD_PARAM);
        return;
    }
    for (int c = 0; c < 2; c++) {
        if (ch != 0xFF && ch != c) continue;
        g_state.ch[c].adcrange = pl[1];
        g_state.ch[c].vbusct = pl[2];
        g_state.ch[c].vshct = pl[3];
        g_state.ch[c].avg = pl[4];
    }
    g_state.config_seq++;
    send_ack(FRAME_SET_ADC);
}

static void handle_set_shunt_cal(const uint8_t *pl, size_t len) {
    if (len != 3) { send_nack(FRAME_SET_SHUNT_CAL, NACK_BAD_LENGTH); return; }
    uint8_t ch = pl[0];
    if (ch > 1 && ch != 0xFF) { send_nack(FRAME_SET_SHUNT_CAL, NACK_BAD_PARAM); return; }
    uint16_t val = (uint16_t)(pl[1] | (pl[2] << 8));
    for (int c = 0; c < 2; c++) {
        if (ch != 0xFF && ch != c) continue;
        g_state.ch[c].shunt_cal = val;
    }
    g_state.config_seq++;
    send_ack(FRAME_SET_SHUNT_CAL);
}

static void handle_get_config(void) {
    uint8_t out[2 + 4 + 2 * 7];
    out[0] = g_state.mode;
    out[1] = g_state.streaming ? 1 : 0;
    uint32_t drops = ring_drop_count();
    memcpy(out + 2, &drops, 4);  // little-endian target
    uint8_t present = sampler_ch_present();
    for (int c = 0; c < 2; c++) {
        uint8_t *b = out + 6 + c * 7;
        b[0] = (present >> c) & 1;
        b[1] = g_state.ch[c].adcrange;
        b[2] = g_state.ch[c].vbusct;
        b[3] = g_state.ch[c].vshct;
        b[4] = g_state.ch[c].avg;
        b[5] = (uint8_t)(g_state.ch[c].shunt_cal & 0xFF);
        b[6] = (uint8_t)(g_state.ch[c].shunt_cal >> 8);
    }
    commands_send_frame(FRAME_CONFIG, out, sizeof out);
}

void commands_handle(uint8_t type, const uint8_t *payload, size_t len) {
    switch (type) {
        case FRAME_HELLO:         handle_hello(payload, len); break;
        case FRAME_START:         g_state.streaming = true;  send_ack(FRAME_START); break;
        case FRAME_STOP:          g_state.streaming = false; send_ack(FRAME_STOP);  break;
        case FRAME_SET_MODE:      handle_set_mode(payload, len); break;
        case FRAME_SET_ADC:       handle_set_adc(payload, len); break;
        case FRAME_SET_SHUNT_CAL: handle_set_shunt_cal(payload, len); break;
        case FRAME_GET_CONFIG:    handle_get_config(); break;
        case FRAME_REBOOT_BOOTSEL: reset_usb_boot(0, 0); break;
        default:                  send_nack(type, NACK_UNKNOWN_CMD); break;
    }
}
