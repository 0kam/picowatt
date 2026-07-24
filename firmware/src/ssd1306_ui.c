// OLED status display.
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include "ssd1306_ui.h"

#include <stdio.h>
#include <math.h>
#include "ssd1306.h"
#include "config.h"

static ssd1306_t oled;
static bool present = false;

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
}

// Format with auto-ranged unit into "%7.4f X" / "%6.2f mX" style, 10 chars max.
static void fmt_ranged(char *buf, size_t n, float val, const char *unit) {
    float a = fabsf(val);
    if (a < 1.0f) {
        snprintf(buf, n, "%7.2f m%s", (double)(val * 1e3f), unit);
    } else {
        snprintf(buf, n, "%8.4f %s", (double)val, unit);
    }
}

void ui_single(float v, float i, float p) {
    if (!present) return;
    char line[16];
    ssd1306_clear(&oled);
    // 5x8 font at scale 2 -> ~12 px/char, 3 rows
    snprintf(line, sizeof line, "%8.4f V", (double)v);
    ssd1306_draw_string(&oled, 0, 1, 2, line);
    fmt_ranged(line, sizeof line, i, "A");
    ssd1306_draw_string(&oled, 0, 23, 2, line);
    fmt_ranged(line, sizeof line, p, "W");
    ssd1306_draw_string(&oled, 0, 45, 2, line);
    ssd1306_show(&oled);
}

void ui_dual(float p_in, float p_out, float eff_percent) {
    if (!present) return;
    char line[16];
    ssd1306_clear(&oled);
    fmt_ranged(line, sizeof line, p_in, "W");
    ssd1306_draw_string(&oled, 0, 1, 2, line);
    fmt_ranged(line, sizeof line, p_out, "W");
    ssd1306_draw_string(&oled, 0, 23, 2, line);
    snprintf(line, sizeof line, "%7.2f %%", (double)eff_percent);
    ssd1306_draw_string(&oled, 0, 45, 2, line);
    ssd1306_show(&oled);
}
