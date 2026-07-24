// core1 acquisition loop and shared device state.
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#ifndef PICOWATT_SAMPLER_H
#define PICOWATT_SAMPLER_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint8_t adcrange;  // 0 / 1
    uint8_t vbusct;    // INA228 CT code 0..7
    uint8_t vshct;     // INA228 CT code 0..7
    uint8_t avg;       // INA228 AVG code 0..7
    uint16_t shunt_cal;
} ch_config_t;

// Shared between cores. core0 edits fields then bumps config_seq; core1
// re-applies the full config when it sees a new seq (idempotent).
typedef struct {
    volatile uint8_t mode;       // 0 = single, 1 = dual
    volatile bool streaming;     // push samples into the ring
    ch_config_t ch[2];
    volatile uint32_t config_seq;
} pw_state_t;

extern pw_state_t g_state;

void sampler_start(void);          // launch core1 (probes devices, owns I2C0)
bool sampler_ready(void);          // probe finished
uint8_t sampler_ch_present(void);  // bitmask: bit0 = ch0 (0x40), bit1 = ch1 (0x41)

#endif // PICOWATT_SAMPLER_H
