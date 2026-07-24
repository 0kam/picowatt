// INA228 register-level driver.
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include "ina228.h"

#include "pico/time.h"

#define I2C_TIMEOUT_US 2000

static bool reg_write16(ina228_t *dev, uint8_t reg, uint16_t val) {
    uint8_t buf[3] = {reg, (uint8_t)(val >> 8), (uint8_t)val};
    return i2c_write_timeout_us(dev->i2c, dev->addr, buf, 3, false, I2C_TIMEOUT_US) == 3;
}

static bool reg_read(ina228_t *dev, uint8_t reg, uint8_t *buf, size_t len) {
    if (i2c_write_timeout_us(dev->i2c, dev->addr, &reg, 1, true, I2C_TIMEOUT_US) != 1) {
        return false;
    }
    return i2c_read_timeout_us(dev->i2c, dev->addr, buf, len, false, I2C_TIMEOUT_US) == (int)len;
}

static bool reg_read16(ina228_t *dev, uint8_t reg, uint16_t *val) {
    uint8_t buf[2];
    if (!reg_read(dev, reg, buf, 2)) return false;
    *val = (uint16_t)((buf[0] << 8) | buf[1]);
    return true;
}

// 24-bit register holding a left-justified 20-bit two's-complement value.
static int32_t reg_read20(ina228_t *dev, uint8_t reg) {
    uint8_t buf[3];
    if (!reg_read(dev, reg, buf, 3)) return INT32_MIN;
    uint32_t v = ((uint32_t)buf[0] << 16) | ((uint32_t)buf[1] << 8) | buf[2];
    // Shift into the top of an i32, then arithmetic-shift back: sign-extends bit 19.
    return (int32_t)(v << 8) >> 12;
}

bool ina228_init(ina228_t *dev, i2c_inst_t *i2c, uint8_t addr) {
    dev->i2c = i2c;
    dev->addr = addr;
    dev->adcrange1 = false;

    uint16_t manuf, devid;
    if (!reg_read16(dev, INA228_REG_MANUF_ID, &manuf)) return false;
    if (!reg_read16(dev, INA228_REG_DEVICE_ID, &devid)) return false;
    if (manuf != INA228_MANUF_ID_TI || (devid >> 4) != INA228_DEVICE_ID_VAL) return false;

    if (!reg_write16(dev, INA228_REG_CONFIG, INA228_CONFIG_RST)) return false;
    sleep_us(300);  // datasheet: reset completes well under this
    return true;
}

bool ina228_set_adc(ina228_t *dev, bool adcrange1, ina228_ct_t vbusct,
                    ina228_ct_t vshct, ina228_avg_t avg) {
    uint16_t config = adcrange1 ? INA228_CONFIG_ADCRANGE : 0;
    if (!reg_write16(dev, INA228_REG_CONFIG, config)) return false;
    dev->adcrange1 = adcrange1;

    uint16_t adc = (uint16_t)((INA228_MODE_CONT_SB << 12) |
                              ((vbusct & 7) << 9) |
                              ((vshct & 7) << 6) |
                              ((vshct & 7) << 3) |  // VTCT: don't care (temp disabled)
                              (avg & 7));
    return reg_write16(dev, INA228_REG_ADC_CONFIG, adc);
}

bool ina228_write_shunt_cal(ina228_t *dev, uint16_t val) {
    return reg_write16(dev, INA228_REG_SHUNT_CAL, val & 0x7FFF);
}

bool ina228_conversion_ready(ina228_t *dev) {
    uint16_t diag;
    if (!reg_read16(dev, INA228_REG_DIAG_ALRT, &diag)) return false;
    return (diag & INA228_DIAG_CNVRF) != 0;
}

int32_t ina228_read_vbus_raw(ina228_t *dev) {
    return reg_read20(dev, INA228_REG_VBUS);
}

int32_t ina228_read_current_raw(ina228_t *dev) {
    return reg_read20(dev, INA228_REG_CURRENT);
}

int32_t ina228_read_vshunt_raw(ina228_t *dev) {
    return reg_read20(dev, INA228_REG_VSHUNT);
}
