// picowatt firmware — core0: USB CDC binary protocol; core1: sampling (sampler.c).
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include <string.h>
#include "pico/bootrom.h"
#include "pico/stdlib.h"
#include "tusb.h"
#include "config.h"
#include "commands.h"
#include "proto.h"
#include "ring.h"
#include "sampler.h"

#define RECORDS_PER_FRAME 20
#define RECORD_BYTES 13
#define FLUSH_INTERVAL_US 10000

// Serialized DATA frame payload: frame_seq u16 | count u8 | records
static uint8_t data_payload[3 + RECORDS_PER_FRAME * RECORD_BYTES];
static uint16_t frame_seq = 0;
static uint8_t pending = 0;
static uint32_t last_flush_us = 0;

static void put_record(const sample_t *s) {
    uint8_t *b = data_payload + 3 + (size_t)pending * RECORD_BYTES;
    b[0] = s->ch;
    memcpy(b + 1, &s->t_us, 4);
    memcpy(b + 5, &s->vbus_raw, 4);
    memcpy(b + 9, &s->curr_raw, 4);
    pending++;
}

static void flush_data_frame(void) {
    if (pending == 0) return;
    data_payload[0] = (uint8_t)(frame_seq & 0xFF);
    data_payload[1] = (uint8_t)(frame_seq >> 8);
    data_payload[2] = pending;
    commands_send_frame(FRAME_DATA, data_payload, 3 + (size_t)pending * RECORD_BYTES);
    frame_seq++;
    pending = 0;
    last_flush_us = time_us_32();
}

static void tx_pump(void) {
    // Only pull from the ring when the CDC FIFO can take a full frame,
    // so backpressure stays in the (deep) ring, not in a half-built frame.
    while (tud_cdc_write_available() > 3 * RECORDS_PER_FRAME * RECORD_BYTES / 2 + 16) {
        sample_t s;
        if (!ring_pop(&s)) break;
        put_record(&s);
        if (pending == RECORDS_PER_FRAME) flush_data_frame();
    }
    if (pending > 0 && time_us_32() - last_flush_us > FLUSH_INTERVAL_US) {
        flush_data_frame();
    }
}

static void rx_pump(proto_decoder_t *dec) {
    uint8_t buf[64];
    while (tud_cdc_available()) {
        uint32_t n = tud_cdc_read(buf, sizeof buf);
        for (uint32_t i = 0; i < n; i++) {
            if (proto_decoder_feed(dec, buf[i])) {
                commands_handle(dec->type, dec->payload, dec->payload_len);
            }
        }
    }
}

// Arduino-style touch reset: 1200 baud -> reboot into BOOTSEL for flashing.
void tud_cdc_line_coding_cb(uint8_t itf, const cdc_line_coding_t *coding) {
    (void)itf;
    if (coding->bit_rate == 1200) reset_usb_boot(0, 0);
}

int main(void) {
    gpio_init(PICO_DEFAULT_LED_PIN);
    gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);

    ring_init();
    sampler_start();
    tusb_init();

    proto_decoder_t dec;
    proto_decoder_init(&dec);

    uint32_t last_led_us = 0;
    bool led_on = false;

    while (true) {
        tud_task();
        rx_pump(&dec);
        tx_pump();

        // LED: 1 Hz idle, 5 Hz streaming
        uint32_t period = g_state.streaming ? 100000 : 500000;
        uint32_t now = time_us_32();
        if (now - last_led_us > period) {
            last_led_us = now;
            led_on = !led_on;
            gpio_put(PICO_DEFAULT_LED_PIN, led_on);
        }
    }
}
