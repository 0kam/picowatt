// core1 acquisition loop: owns I2C0 exclusively (INA228 x2 + OLED).
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include "sampler.h"

#include "pico/multicore.h"
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "config.h"
#include "ina228.h"
#include "ring.h"
#include "ssd1306_ui.h"

pw_state_t g_state = {
    .mode = 0,
    .streaming = false,
    .ch = {
        {.adcrange = 0, .vbusct = 3, .vshct = 3, .avg = 0, .shunt_cal = PW_SHUNT_CAL_DEFAULT},
        {.adcrange = 0, .vbusct = 3, .vshct = 3, .avg = 0, .shunt_cal = PW_SHUNT_CAL_DEFAULT},
    },
    .config_seq = 0,
};

static ina228_t dev[2];
static volatile uint8_t ch_present_mask = 0;
static volatile bool ready = false;

static const uint8_t ch_addr[2] = {INA228_ADDR_IN, INA228_ADDR_OUT};

// OLED shows the mean over each ~300 ms render period, not instantaneous
// samples (readable at any preset). Sums accumulate between renders.
static float sum_v[2], sum_i[2];
static uint32_t sum_n[2];
static float disp_v[2], disp_i[2];
static bool disp_valid[2];

static void apply_config(void) {
    for (int c = 0; c < 2; c++) {
        if (!(ch_present_mask & (1u << c))) continue;
        ch_config_t cfg = g_state.ch[c];  // struct copy; core0 only edits before seq bump
        ina228_set_adc(&dev[c], cfg.adcrange != 0, (ina228_ct_t)cfg.vbusct,
                       (ina228_ct_t)cfg.vshct, (ina228_avg_t)cfg.avg);
        ina228_write_shunt_cal(&dev[c], cfg.shunt_cal);
    }
}

static float current_lsb(int c) {
    return g_state.ch[c].adcrange ? 2e-6f : 8e-6f;
}

static void oled_render(void) {
    for (int c = 0; c < 2; c++) {
        if (sum_n[c] > 0) {
            disp_v[c] = sum_v[c] / (float)sum_n[c];
            disp_i[c] = sum_i[c] / (float)sum_n[c];
            disp_valid[c] = true;
        }
        sum_v[c] = sum_i[c] = 0;
        sum_n[c] = 0;
    }
    if (g_state.mode == 1) {
        float p_in = disp_valid[0] ? disp_v[0] * disp_i[0] : 0;
        float p_out = disp_valid[1] ? disp_v[1] * disp_i[1] : 0;
        float eff = (p_in > 1e-6f) ? 100.0f * p_out / p_in : 0;
        ui_render_dual(p_in, p_out, eff);
    } else if (disp_valid[0]) {
        ui_render_single(disp_v[0], disp_i[0], disp_v[0] * disp_i[0]);
    }
}

static void core1_main(void) {
    i2c_init(PW_I2C, PW_I2C_BAUD_HZ);
    gpio_set_function(PW_I2C_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(PW_I2C_SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(PW_I2C_SDA_PIN);
    gpio_pull_up(PW_I2C_SCL_PIN);

    uint8_t mask = 0;
    for (int c = 0; c < 2; c++) {
        if (ina228_init(&dev[c], PW_I2C, ch_addr[c])) mask |= (1u << c);
    }
    ch_present_mask = mask;

    ui_init(PW_I2C);
    ui_message("picowatt", (mask & 1) ? "ch0 ready" : "no INA228!");

    uint32_t applied_seq = g_state.config_seq - 1;  // force initial apply
    uint32_t last_render_us = 0;

    while (true) {
        uint32_t seq = g_state.config_seq;
        if (seq != applied_seq) {
            applied_seq = seq;
            apply_config();
        }

        int nch = (g_state.mode == 1) ? 2 : 1;
        for (int c = 0; c < nch; c++) {
            if (!(ch_present_mask & (1u << c))) continue;
            if (!ina228_conversion_ready(&dev[c])) continue;

            sample_t s = {.ch = (uint8_t)c, .t_us = time_us_32()};
            s.vbus_raw = ina228_read_vbus_raw(&dev[c]);
            s.curr_raw = ina228_read_current_raw(&dev[c]);
            if (s.vbus_raw == INT32_MIN || s.curr_raw == INT32_MIN) continue;

            sum_v[c] += (float)s.vbus_raw * INA228_VBUS_LSB_V;
            sum_i[c] += (float)s.curr_raw * current_lsb(c);
            sum_n[c]++;

            if (g_state.streaming) ring_push(&s);
        }

        uint32_t now = time_us_32();
        if (now - last_render_us > 300000) {  // ~3.3 Hz
            last_render_us = now;
            oled_render();
        }
        ui_flush_one_page();  // <=1.3 ms, only when dirty
    }
}

void sampler_start(void) {
    multicore_launch_core1(core1_main);
    ready = true;
}

bool sampler_ready(void) {
    return ready;
}

uint8_t sampler_ch_present(void) {
    return ch_present_mask;
}
