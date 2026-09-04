#ifndef PICOWATT_CONFIG_H
#define PICOWATT_CONFIG_H

// ---- Firmware version ----
#define FW_VERSION_MAJOR 0
#define FW_VERSION_MINOR 1
#define FW_VERSION_PATCH 1

// ---- I2C bus ----
#define PW_I2C            i2c0
#define PW_I2C_SDA_PIN    4   // GP4, pin 6
#define PW_I2C_SCL_PIN    5   // GP5, pin 7
#define PW_I2C_BAUD_HZ    1000000  // 1 MHz; fall back to 400 kHz if unstable

// ---- Device addresses ----
#define INA228_ADDR_IN    0x40  // channel 0, input side (#1)
#define INA228_ADDR_OUT   0x41  // channel 1, output side (#2, A0 jumper closed)
#define SSD1306_ADDR      0x3C

// ---- Reserved for optional ALERT wiring (not used yet) ----
#define INA228_ALERT_IN_PIN   6   // GP6
#define INA228_ALERT_OUT_PIN  7   // GP7

// ---- Shunt / calibration defaults (see docs/calibration.md) ----
#define PW_SHUNT_OHMS         0.015f
#define PW_SHUNT_CAL_DEFAULT  1573  // ADCRANGE=0: LSB 8 uA; ADCRANGE=1: LSB 2 uA

#endif // PICOWATT_CONFIG_H
