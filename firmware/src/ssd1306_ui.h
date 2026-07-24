// OLED status display (SSD1306 128x64), page-chunked writes.
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#ifndef PICOWATT_SSD1306_UI_H
#define PICOWATT_SSD1306_UI_H

#include <stdbool.h>
#include "hardware/i2c.h"

// Returns false if the OLED does not respond (system keeps running without it).
bool ui_init(i2c_inst_t *i2c);

// Immediate two-line status message (full-frame write; boot/error paths only).
void ui_message(const char *line1, const char *line2);

// Draw to the framebuffer and mark pages dirty; actual I2C writes happen in
// ui_flush_one_page(), one 128-byte page (<=1.3 ms at 1 MHz) per call, so the
// sampling loop is never stalled for a full frame.
void ui_render_single(float v, float i, float p);
void ui_render_dual(float p_in, float p_out, float eff_percent);

// Write at most one dirty page. Returns true if a page was written.
bool ui_flush_one_page(void);

#endif // PICOWATT_SSD1306_UI_H
