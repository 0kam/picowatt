// OLED status display, page-chunked writes.
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include "ssd1306_ui.h"

#include <stdio.h>
#include <math.h>
#include <string.h>
#include "ssd1306.h"
#include "config.h"

#define I2C_TIMEOUT_US 3000

static ssd1306_t oled;
static bool present = false;
static uint8_t dirty_mask = 0;  // bit per 8-row page (128x64 -> 8 pages)

bool ui_init(i2c_inst_t *i2c) {
    present = ssd1306_init(&oled, 128, 64, SSD1306_ADDR, i2c);
    if (present) {
        ssd1306_clear(&oled);
        ssd1306_show(&oled);
    }
    return present;
}

void ui_message(const char *line1, const char *line2) {
    if (!present) return;
    ssd1306_clear(&oled);
    ssd1306_draw_string(&oled, 0, 16, 1, line1);
    if (line2) ssd1306_draw_string(&oled, 0, 32, 1, line2);
    ssd1306_show(&oled);
    dirty_mask = 0;
}

// Format with auto-ranged unit, 10 chars max.
static void fmt_ranged(char *buf, size_t n, float val, const char *unit) {
    float a = fabsf(val);
    if (a < 1.0f) {
        snprintf(buf, n, "%7.2f m%s", (double)(val * 1e3f), unit);
    } else {
        snprintf(buf, n, "%8.4f %s", (double)val, unit);
    }
}

static void render_3lines(const char *l1, const char *l2, const char *l3) {
    if (!present) return;
    ssd1306_clear(&oled);
    ssd1306_draw_string(&oled, 0, 1, 2, l1);
    ssd1306_draw_string(&oled, 0, 23, 2, l2);
    ssd1306_draw_string(&oled, 0, 45, 2, l3);
    dirty_mask = 0xFF;
}

void ui_render_single(float v, float i, float p) {
    char l1[16], l2[16], l3[16];
    snprintf(l1, sizeof l1, "%8.4f V", (double)v);
    fmt_ranged(l2, sizeof l2, i, "A");
    fmt_ranged(l3, sizeof l3, p, "W");
    render_3lines(l1, l2, l3);
}

void ui_render_dual(float p_in, float p_out, float eff_percent) {
    char l1[16], l2[16], l3[16];
    fmt_ranged(l1, sizeof l1, p_in, "W");
    fmt_ranged(l2, sizeof l2, p_out, "W");
    snprintf(l3, sizeof l3, "%7.2f %%", (double)eff_percent);
    render_3lines(l1, l2, l3);
}

static bool oled_cmds(const uint8_t *cmds, size_t n) {
    // Each command byte is prefixed with control byte 0x00.
    for (size_t k = 0; k < n; k++) {
        uint8_t buf[2] = {0x00, cmds[k]};
        if (i2c_write_timeout_us(oled.i2c_i, oled.address, buf, 2, false,
                                 I2C_TIMEOUT_US) != 2) {
            return false;
        }
    }
    return true;
}

bool ui_flush_one_page(void) {
    if (!present || dirty_mask == 0) return false;

    int page = __builtin_ctz(dirty_mask);
    dirty_mask &= (uint8_t)~(1u << page);

    const uint8_t cmds[] = {
        SET_COL_ADDR, 0, (uint8_t)(oled.width - 1),
        SET_PAGE_ADDR, (uint8_t)page, (uint8_t)page,
    };
    if (!oled_cmds(cmds, sizeof cmds)) return false;

    uint8_t buf[129];
    buf[0] = 0x40;  // data control byte
    memcpy(buf + 1, oled.buffer + (size_t)page * oled.width, oled.width);
    i2c_write_timeout_us(oled.i2c_i, oled.address, buf, sizeof buf, false,
                         2 * I2C_TIMEOUT_US);
    return true;
}
