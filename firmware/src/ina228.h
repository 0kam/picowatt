// INA228 register-level driver (TI datasheet SBOSA20).
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#ifndef PICOWATT_INA228_H
#define PICOWATT_INA228_H

#include <stdbool.h>
#include <stdint.h>
#include "hardware/i2c.h"

// Register addresses
#define INA228_REG_CONFIG      0x00
#define INA228_REG_ADC_CONFIG  0x01
#define INA228_REG_SHUNT_CAL   0x02
#define INA228_REG_VSHUNT      0x04
#define INA228_REG_VBUS        0x05
#define INA228_REG_CURRENT     0x07
#define INA228_REG_DIAG_ALRT   0x0B
#define INA228_REG_MANUF_ID    0x3E
#define INA228_REG_DEVICE_ID   0x3F

#define INA228_MANUF_ID_TI     0x5449  // "TI"
#define INA228_DEVICE_ID_VAL   0x228   // DIEID field, bits 15:4

// CONFIG bits
#define INA228_CONFIG_RST      (1u << 15)
#define INA228_CONFIG_ADCRANGE (1u << 4)

// ADC_CONFIG MODE: continuous shunt + bus (no temperature)
#define INA228_MODE_CONT_SB    0xB

// Conversion time codes (VBUSCT / VSHCT), datasheet table
typedef enum {
    INA228_CT_50US = 0,
    INA228_CT_84US,
    INA228_CT_150US,
    INA228_CT_280US,
    INA228_CT_540US,
    INA228_CT_1052US,
    INA228_CT_2074US,
    INA228_CT_4120US,
} ina228_ct_t;

// Averaging count codes
typedef enum {
    INA228_AVG_1 = 0,
    INA228_AVG_4,
    INA228_AVG_16,
    INA228_AVG_64,
    INA228_AVG_128,
    INA228_AVG_256,
    INA228_AVG_512,
    INA228_AVG_1024,
} ina228_avg_t;

// DIAG_ALRT bits
#define INA228_DIAG_CNVRF      (1u << 1)

// VBUS LSB is fixed regardless of range
#define INA228_VBUS_LSB_V      195.3125e-6f

typedef struct {
    i2c_inst_t *i2c;
    uint8_t addr;
    bool adcrange1;  // false: +/-163.84 mV, true: +/-40.96 mV
} ina228_t;

// Probe (MANUF/DEVICE ID), soft-reset, leave at power-on defaults.
// Returns false if the device does not respond or IDs mismatch.
bool ina228_init(ina228_t *dev, i2c_inst_t *i2c, uint8_t addr);

// Write CONFIG.ADCRANGE and ADC_CONFIG (continuous shunt+bus mode).
bool ina228_set_adc(ina228_t *dev, bool adcrange1, ina228_ct_t vbusct,
                    ina228_ct_t vshct, ina228_avg_t avg);

// Write SHUNT_CAL. Caller passes the final value (already x4 for ADCRANGE=1).
bool ina228_write_shunt_cal(ina228_t *dev, uint16_t val);

// Read DIAG_ALRT and report CNVRF (cleared by this read — treat as an edge).
bool ina228_conversion_ready(ina228_t *dev);

// 20-bit sign-extended raw counts. Return INT32_MIN on I2C error.
int32_t ina228_read_vbus_raw(ina228_t *dev);     // LSB 195.3125 uV
int32_t ina228_read_current_raw(ina228_t *dev);  // LSB = CURRENT_LSB
int32_t ina228_read_vshunt_raw(ina228_t *dev);   // LSB 312.5 nV (range0) / 78.125 nV (range1)

#endif // PICOWATT_INA228_H
