// Blinds controller firmware, V1. Board: carrier PCB (hardware/pcb), ESP32-C6, Arduino-ESP32 core 3.x.
#pragma once
#include "ardu.h"

#define FW_BUILD __DATE__ " " __TIME__

// ---- pins (hardware/pcb/netlist.py): per port IN1, IN2, EN, angle
const int PORTS = 3;
const int P_IN1[PORTS] = {14, 19, 16}, P_IN2[PORTS] = {18, 20, 17}, P_EN[PORTS] = {7, 5, 1}, P_ANG[PORTS] = {6, 4, 2};
const int PIN_VBAT = 3, PIN_VIN = 0;            // 1 M / 1 M dividers: battery (LOAD rail), input power (USB / solar)
const int PWM_HZ = 20000, PWM_BITS = 8;

// ---- motion
// Stall and time limits are in store.h (Tune): they can be changed from the Developer page.
// The sensor's supply is this far below the 3.3 V rail (EN pin + 10 ohm). Measured 2026-11-15: at the 0/360 point the
// output jumped from 62 mV to 2727 mV with the rail at 2.99 V, so full scale (360 deg) = rail - 0.26 V.
const float EN_DROP_V = 0.26f;
const float SAME_DIR_GRACE_MS = 2500;           // stall wait when the motor carries on the way it last turned (no gear play)
const float NUDGE_MS_PER_DEG = 350.0f;           // the rod turns about 2 to 3 degrees a second
const float TOL_DEG = 2.0f;                     // "reached"
const float OVER_OK_DEG = 5.0f;                 // past the target by less than this: leave it (turning back costs the gear play)
const int START_DUTY = 45;                      // percent
const uint32_t RAMP_MS = 150, SETTLE_MS = 120;  // soft start; wait after braking before the true reading
const int MAX_NUDGES = 8;
const uint32_t POST_MS = 400;                   // after a move: keep the sensor on this long and take the final position then
const float END_STALL_DEG = 10.0f;              // a stall this close to a closed mark counts as "at the end stop"
const float MAX_HALF_SPAN = 170.0f, MIN_HALF_SPAN = 8.0f;   // open -> closed, each way (degrees of rod turn)

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
