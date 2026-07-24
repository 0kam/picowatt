// TinyUSB configuration: single CDC device.
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#ifndef PICOWATT_TUSB_CONFIG_H
#define PICOWATT_TUSB_CONFIG_H

#include "tusb_option.h"

#define CFG_TUSB_RHPORT0_MODE (OPT_MODE_DEVICE | OPT_MODE_FULL_SPEED)
#define CFG_TUSB_OS           OPT_OS_PICO

#define CFG_TUD_ENABLED       1
#define CFG_TUD_ENDPOINT0_SIZE 64

#define CFG_TUD_CDC           1
#define CFG_TUD_CDC_RX_BUFSIZE 512
#define CFG_TUD_CDC_TX_BUFSIZE 4096
#define CFG_TUD_CDC_EP_BUFSIZE 64

#endif // PICOWATT_TUSB_CONFIG_H
