// The hub's color light: on the ESP32-C6 SuperMini, a WS2812 on GPIO8 (it takes a 24-bit color as timed pulses, sent
// here with the RMT pulse hardware). The board also has a power LED (always on, not ours) and a one-color LED on
// GPIO15, kept dark. What the light shows: statusTask in hub.cpp. `/api/light` (owner) sets them by hand for a minute,
// to tell which light is which on a new board.
#pragma once
#include <cstdint>
#include <driver/gpio.h>
#include <driver/rmt_tx.h>
#include <freertos/FreeRTOS.h>

static rmt_channel_handle_t rgbChan = nullptr;
static rmt_encoder_handle_t rgbEnc = nullptr;
static volatile uint32_t lightTestUntil = 0;     // millis: /api/light sets the lights until then (statusTask waits)

static void rgbBegin() {
  if (rgbChan) return;
  rmt_tx_channel_config_t c = {};
  c.gpio_num = GPIO_NUM_8;
  c.clk_src = RMT_CLK_SRC_DEFAULT;
  c.resolution_hz = 10000000;                    // 0.1 us ticks
  c.mem_block_symbols = 48;
  c.trans_queue_depth = 2;
  if (rmt_new_tx_channel(&c, &rgbChan) != ESP_OK) { rgbChan = nullptr; return; }
  rmt_bytes_encoder_config_t e = {};
  e.bit0 = {3, 1, 9, 0};                         // 0: 0.3 us high, 0.9 us low
  e.bit1 = {9, 1, 3, 0};                         // 1: 0.9 us high, 0.3 us low
  e.flags.msb_first = 1;
  if (rmt_new_bytes_encoder(&e, &rgbEnc) != ESP_OK) { rgbEnc = nullptr; return; }
  rmt_enable(rgbChan);
}
// The color LED: red, green, blue, 0-255 each (sent green first, as the WS2812 wants it).
static void rgbSet(uint8_t r, uint8_t g, uint8_t b) {
  rgbBegin();
  if (!rgbChan || !rgbEnc) return;
  static uint8_t grb[3];                         // static: the pulse hardware reads it after rmt_transmit returns
  grb[0] = g; grb[1] = r; grb[2] = b;
  rmt_transmit_config_t t = {};
  rmt_transmit(rgbChan, rgbEnc, grb, sizeof grb, &t);
  rmt_tx_wait_all_done(rgbChan, 50);
}
