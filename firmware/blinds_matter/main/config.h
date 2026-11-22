// Blinds controller firmware, V1. Board: carrier PCB (hardware/pcb), ESP32-C6, Arduino-ESP32 core 3.x.
#pragma once
#include "ardu.h"
#include "logic.h"                               // the pure rules and math (tested on the Mac)
#include "tilter.h"                              // one blind's Move and its motion limits (tested on the Mac)

#define FW_BUILD __DATE__ " " __TIME__

// ---- pins (hardware/pcb/netlist.py): per port IN1, IN2, EN, angle
const int P_IN1[PORTS] = {14, 19, 16}, P_IN2[PORTS] = {18, 20, 17}, P_EN[PORTS] = {7, 5, 1}, P_ANG[PORTS] = {6, 4, 2};
const int PIN_VBAT = 3, PIN_VIN = 0;            // 1 M / 1 M dividers: battery (LOAD rail), input power (USB / solar)
const int PWM_HZ = 20000, PWM_BITS = 8;

// ---- sensor (the move's limits: tilter.h)
// The sensor's supply is this far below the 3.3 V rail (EN pin + 10 ohm). Measured 2026-11-15: at the 0/360 point the
// output jumped from 62 mV to 2727 mV with the rail at 2.99 V, so full scale (360 deg) = rail - 0.26 V.
const float EN_DROP_V = 0.26f;

// ---- power
const float VIN_ON = 3.8f, VIN_OFF = 3.3f;      // input power present (USB or strong sun) / gone. USB reads ~4.3 V here.
const float VBAT_LOW = 3.35f;                   // no moves below this (resting)
const float VBAT_CRIT = 3.20f;                  // sleep long, do nothing
const uint32_t POLL_SLEEP_S = 30;               // asleep on battery: look for input power this often
const uint32_t CRIT_SLEEP_S = 600;
const uint32_t GRACE_BOOT_S = 180;              // stay awake this long after a power-on / unplug before sleeping
const uint32_t GRACE_ACTIVITY_S = 120;          // ... and this long after the last request from a browser
const uint32_t CHECKIN_AWAKE_S = 25;            // a battery check-in stays on Wi-Fi this long if nobody talks to it

// ---- network
#define DEFAULT_HOSTNAME "blinds-pcb"
#define AP_NAME "Blinds-Setup"
const uint32_t WIFI_FALLBACK_AP_MS = 30000;     // no Wi-Fi after this long: also open the setup network
const uint32_t OTA_VERIFY_MS = 120000;          // a new firmware that can't get on Wi-Fi in this time rolls back
