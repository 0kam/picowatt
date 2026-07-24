// picowatt firmware — M3: INA228 text output + OLED display.
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "config.h"
#include "ina228.h"
#include "ssd1306_ui.h"

// M2 defaults: ADCRANGE=0 (8 uA/LSB), 540 us conversions, 16x averaging
// -> new sample every (540+540)*16 = 17.3 ms (~58 Hz); printed at 10 Hz.
#define CURRENT_LSB_A 8e-6f

static void i2c_bus_init(void) {
    i2c_init(PW_I2C, PW_I2C_BAUD_HZ);
    gpio_set_function(PW_I2C_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(PW_I2C_SCL_PIN, GPIO_FUNC_I2C);
    // External 10k pullups on the INA228 board; internal ones don't hurt.
    gpio_pull_up(PW_I2C_SDA_PIN);
    gpio_pull_up(PW_I2C_SCL_PIN);
}

int main(void) {
    stdio_init_all();

    gpio_init(PICO_DEFAULT_LED_PIN);
    gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);

    i2c_bus_init();

    bool have_oled = ui_init(PW_I2C);
    if (have_oled) ui_message("picowatt", "starting...");

    ina228_t ina;
    bool ok = false;
    while (!ok) {
        ok = ina228_init(&ina, PW_I2C, INA228_ADDR_IN);
        if (ok) {
            ok = ina228_set_adc(&ina, false, INA228_CT_540US, INA228_CT_540US,
                                INA228_AVG_16) &&
                 ina228_write_shunt_cal(&ina, PW_SHUNT_CAL_DEFAULT);
        }
        if (!ok) {
            printf("ERROR: INA228 not found at 0x%02X (check wiring)\n", INA228_ADDR_IN);
            ui_message("ERROR", "INA228 not found");
            gpio_put(PICO_DEFAULT_LED_PIN, 1);  // solid LED = error
            sleep_ms(1000);
        }
    }

    absolute_time_t next_print = make_timeout_time_ms(100);
    bool led_on = false;
    int oled_div = 0;

    while (true) {
        sleep_until(next_print);
        next_print = delayed_by_ms(next_print, 100);

        int32_t vbus_raw = ina228_read_vbus_raw(&ina);
        int32_t curr_raw = ina228_read_current_raw(&ina);
        if (vbus_raw == INT32_MIN || curr_raw == INT32_MIN) {
            printf("ERROR: I2C read failed\n");
            continue;
        }

        float v = (float)vbus_raw * INA228_VBUS_LSB_V;
        float i = (float)curr_raw * CURRENT_LSB_A;
        float p = v * i;
        printf("V=%9.5f V  I=%9.6f A  P=%10.6f W  (vbus_raw=%ld curr_raw=%ld)\n",
               (double)v, (double)i, (double)p, (long)vbus_raw, (long)curr_raw);

        if (++oled_div >= 3) {  // ~3.3 Hz OLED refresh
            oled_div = 0;
            ui_single(v, i, p);
        }

        led_on = !led_on;  // 5 Hz blink while measuring
        gpio_put(PICO_DEFAULT_LED_PIN, led_on);
    }
}
