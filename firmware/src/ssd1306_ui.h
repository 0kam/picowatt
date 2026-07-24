// OLED status display (SSD1306 128x64).
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#ifndef PICOWATT_SSD1306_UI_H
#define PICOWATT_SSD1306_UI_H

#include <stdbool.h>
#include "hardware/i2c.h"

// Returns false if the OLED does not respond (system keeps running without it).
bool ui_init(i2c_inst_t *i2c);

// Two-line status message (e.g. errors, boot banner).
void ui_message(const char *line1, const char *line2);

// Single-channel screen: V / I / P with auto-ranged units.
void ui_single(float v, float i, float p);

// Dual-channel screen (M7): input/output power and efficiency.
void ui_dual(float p_in, float p_out, float eff_percent);

#endif // PICOWATT_SSD1306_UI_H
