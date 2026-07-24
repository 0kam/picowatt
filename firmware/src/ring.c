// SPSC lock-free sample ring buffer.
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include "ring.h"

#include "pico.h"
#include "hardware/sync.h"

static sample_t buf[RING_SIZE];
static volatile uint32_t head;  // written by producer (core1)
static volatile uint32_t tail;  // written by consumer (core0)
static volatile uint32_t drops;

void ring_init(void) {
    head = tail = drops = 0;
}

bool ring_push(const sample_t *s) {
    uint32_t h = head;
    if (h - tail >= RING_SIZE) {
        drops++;
        return false;
    }
    buf[h & (RING_SIZE - 1)] = *s;
    __dmb();  // data visible before index advance
    head = h + 1;
    return true;
}

bool ring_pop(sample_t *s) {
    uint32_t t = tail;
    if (t == head) return false;
    *s = buf[t & (RING_SIZE - 1)];
    __dmb();
    tail = t + 1;
    return true;
}

uint32_t ring_drop_count(void) {
    return drops;
}
