// Command dispatch (core0).
// Copyright (C) 2026  Ryotaro Okamoto
// SPDX-License-Identifier: GPL-3.0-or-later

#ifndef PICOWATT_COMMANDS_H
#define PICOWATT_COMMANDS_H

#include <stddef.h>
#include <stdint.h>

// Handle one decoded PC->FW frame; sends the response over CDC.
void commands_handle(uint8_t type, const uint8_t *payload, size_t len);

// Encode and queue a frame on the CDC TX FIFO (drops if no room).
void commands_send_frame(uint8_t type, const uint8_t *payload, size_t len);

#endif // PICOWATT_COMMANDS_H
