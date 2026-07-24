// picowatt firmware — M1 skeleton: LED blink + USB CDC echo.
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include <stdio.h>
#include "pico/stdlib.h"
#include "config.h"

int main(void) {
    stdio_init_all();

    gpio_init(PICO_DEFAULT_LED_PIN);
    gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);

    absolute_time_t next_toggle = make_timeout_time_ms(500);
    bool led_on = false;

    while (true) {
        // Echo any received character back to the host.
        int c = getchar_timeout_us(0);
        if (c != PICO_ERROR_TIMEOUT) {
            putchar_raw(c);
        }

        if (absolute_time_diff_us(get_absolute_time(), next_toggle) <= 0) {
            led_on = !led_on;
            gpio_put(PICO_DEFAULT_LED_PIN, led_on);
            next_toggle = make_timeout_time_ms(500);
        }
    }
}
