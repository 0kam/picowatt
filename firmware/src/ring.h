// SPSC lock-free sample ring buffer (producer: core1, consumer: core0).
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#ifndef PICOWATT_RING_H
#define PICOWATT_RING_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint8_t ch;
    uint32_t t_us;
    int32_t vbus_raw;
    int32_t curr_raw;
} sample_t;

#define RING_SIZE 4096  // power of two; ~1 s headroom at max rate

void ring_init(void);
bool ring_push(const sample_t *s);   // core1 only; false + drop count on full
bool ring_pop(sample_t *s);          // core0 only
uint32_t ring_drop_count(void);

#endif // PICOWATT_RING_H
