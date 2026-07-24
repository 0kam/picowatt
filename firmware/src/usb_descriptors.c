// USB descriptors: CDC device, product string "picowatt".
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#include <string.h>
#include "pico/unique_id.h"
#include "tusb.h"
#include "config.h"

#define USBD_VID 0x2E8A  // Raspberry Pi
#define USBD_PID 0x000A  // Pico SDK CDC

enum {
    ITF_NUM_CDC = 0,
    ITF_NUM_CDC_DATA,
    ITF_NUM_TOTAL,
};

#define EPNUM_CDC_NOTIF 0x81
#define EPNUM_CDC_OUT   0x02
#define EPNUM_CDC_IN    0x82

static const tusb_desc_device_t desc_device = {
    .bLength = sizeof(tusb_desc_device_t),
    .bDescriptorType = TUSB_DESC_DEVICE,
    .bcdUSB = 0x0200,
    .bDeviceClass = TUSB_CLASS_MISC,
    .bDeviceSubClass = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = USBD_VID,
    .idProduct = USBD_PID,
    .bcdDevice = (FW_VERSION_MAJOR << 8) | FW_VERSION_MINOR,
    .iManufacturer = 1,
    .iProduct = 2,
    .iSerialNumber = 3,
    .bNumConfigurations = 1,
};

#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN)

static const uint8_t desc_configuration[] = {
    TUD_CONFIG_DESCRIPTOR(1, ITF_NUM_TOTAL, 0, CONFIG_TOTAL_LEN, 0, 100),
    TUD_CDC_DESCRIPTOR(ITF_NUM_CDC, 4, EPNUM_CDC_NOTIF, 8, EPNUM_CDC_OUT,
                       EPNUM_CDC_IN, 64),
};

static const char *string_desc[] = {
    NULL,               // 0: language (handled below)
    "picowatt project", // 1: manufacturer
    "picowatt",         // 2: product
    NULL,               // 3: serial (board id, filled at runtime)
    "picowatt data",    // 4: CDC interface
};

const uint8_t *tud_descriptor_device_cb(void) {
    return (const uint8_t *)&desc_device;
}

const uint8_t *tud_descriptor_configuration_cb(uint8_t index) {
    (void)index;
    return desc_configuration;
}

const uint16_t *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
    (void)langid;
    static uint16_t desc[32];
    uint8_t len;

    if (index == 0) {
        desc[1] = 0x0409;  // English (US)
        len = 1;
    } else if (index == 3) {
        char serial[2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1];
        pico_get_unique_board_id_string(serial, sizeof serial);
        len = (uint8_t)strlen(serial);
        for (uint8_t i = 0; i < len; i++) desc[1 + i] = serial[i];
    } else if (index < TU_ARRAY_SIZE(string_desc) && string_desc[index]) {
        const char *s = string_desc[index];
        len = (uint8_t)strlen(s);
        if (len > 30) len = 30;
        for (uint8_t i = 0; i < len; i++) desc[1 + i] = s[i];
    } else {
        return NULL;
    }

    desc[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * len + 2));
    return desc;
}
