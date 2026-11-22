# Battery cost of a sleeping Thread controller on the ESP32-C6

Research for [#40](https://github.com/DrakeAnglin/tilt/issues/40), part of the
[Tilt Hub spec map (#37)](https://github.com/DrakeAnglin/tilt/issues/37). Checked 2026-11.

**These are estimates from datasheets and SDK source, not measurements.** Espressif publishes no average-current
figure for an ESP32-C6 Thread sleepy device, so the numbers here are built from parts. The real numbers come from
measuring ([#6](https://github.com/DrakeAnglin/tilt/issues/6)).

## Short answer

- **Sleep floor:** about **45–100 µA** for the whole board (chip about 35 µA plus charger, dividers, motor drivers
  and the regulator). That is about **1–2.4 mAh a day**.
- **One check-in (data poll):** about **150–450 µC**, with about 250 µC as the middle guess. The C6 radio is hungry
  (119 mA to send at 0 dBm), so one poll costs about 15× what a Nordic chip pays.
- **Fastest rate that is still cheap: a 1 s check-in** (a tap waits 0.5 s on average, 1 s at worst), about
  **7 mAh a day** (range 5–13). At 2 s it is about 4.4 mAh a day. Either way the radio stops being the main load:
  the motors (3–5 mAh a day) are about the same size.
- **Today's Wi-Fi estimate is 70–150 mAh a day.** Thread at 1 s is about 10× better, so a cell lasts months, not
  weeks.
- **Biggest single trap, on Wi-Fi or Thread:** `CONFIG_BT_LE_LP_CLK_SRC_MAIN_XTAL=y` in
  `firmware/blinds_matter/sdkconfig.defaults` keeps the main crystal running in light sleep. Espressif lists
  **3.3 mA** in light sleep for that (34 µA with a 32 kHz crystal). That alone is about 80 mAh a day, about all of
  today's Wi-Fi estimate. Turn Bluetooth off after setup, or change the sleep clock.

## Sleep floor

| Part | Sleep draw | Source |
|---|---|---|
| ESP32-C6, light sleep, CPU, radio and peripherals powered down | 35 µA typ (180 µA if peripherals stay powered) | [ESP32-C6 datasheet v1.6, Table 5-11](https://documentation.espressif.com/esp32-c6_datasheet_en.html) |
| ESP32-C6, light sleep with BLE using the main crystal as its sleep clock | 3.3 mA | [ESP-IDF NimBLE power_save example README](https://github.com/espressif/esp-idf/blob/master/examples/bluetooth/nimble/power_save/README.md); [BLE low-power guide](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-guides/low-power-mode/low-power-mode-ble.html) |
| bq25185 (Adafruit 6092), battery only | about 4 µA | [TI BQ25185 product page](https://www.ti.com/product/BQ25185) |
| DRV8833 × 3, asleep (EN low) | 1.6 µA each, about 5 µA | [TI DRV8833 product page](https://www.ti.com/product/DRV8833) |
| Battery divider, 1 MΩ + 1 MΩ at 4.2 V | about 2 µA | Ohm's law, `docs/architecture.md` "Pins" |
| AS5600 | 0 (powered from EN only while moving) | `docs/architecture.md` "RJ12 pinout" |
| SuperMini 3.3 V regulator | unknown part, often 1–60 µA | **check the board** |
| SuperMini power LED, if it has one | about 1–2 mA | **check the board; remove it if present** |

So the floor is about **45–100 µA** with no LED and Bluetooth off (or on a 32 kHz sleep clock). The ESP-IDF sleepy
example also sets `CONFIG_PM_POWER_DOWN_PERIPHERAL_IN_LIGHT_SLEEP=y`, `CONFIG_IEEE802154_SLEEP_ENABLE=y` and
`CONFIG_ESP_SLEEP_POWER_DOWN_FLASH=y` to reach the 35 µA row
([light_sleep sdkconfig.defaults](https://github.com/espressif/esp-idf/blob/master/examples/openthread/ot_sleepy_device/light_sleep/sdkconfig.defaults)).
The example warns when no 32 kHz crystal is in use; a plain sleepy end device still works on the internal RC clock,
because the device itself decides when to poll.

## Cost of one check-in

A sleepy end device (SED) wakes, sends a short "any mail for me?" frame (a data request) to its parent, and listens
for the reply. If the parent has nothing, it goes back to sleep.

Built from datasheet currents ([Table 5-9](https://documentation.espressif.com/esp32-c6_datasheet_en.html):
send 119 mA at 0 dBm, 187 mA at 12 dBm, 305 mA at 20 dBm; listen 74 mA):

| Step | Time (802.15.4 runs at 250 kbit/s) | Charge |
|---|---|---|
| Wake from light sleep and restore the radio, CPU at about 15–20 mA ([Table 5-10](https://documentation.espressif.com/esp32-c6_datasheet_en.html)) | about 1–3 ms | 20–60 µC |
| Send the secured data request (about 30 bytes) | about 1 ms | 119 µC at 0 dBm, 305 µC at 20 dBm |
| Listen for the clear channel and the ack | about 0.5–1 ms | 40–75 µC |
| **Total** | **about 3–5 ms** | **about 150–450 µC (middle 250 µC)** |

For scale, Nordic measures 14–18 µC per poll on its own chips at 0 dBm
([nRF Connect SDK, OpenThread power consumption](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/protocols/thread/overview/power_consumption.html)).
The C6 radio draws about 20× more current to send, so its poll costs much more. **Turn the send power down** (the
hub is in the same house): it is the biggest part of each poll. Espressif's ICD example was measured at 20 dBm
([esp-matter icd_app](https://github.com/espressif/esp-matter/tree/main/examples/icd_app)), the worst case.

## Check-in interval vs reaction time vs battery

Average current = floor + (charge per poll ÷ interval). mAh a day = average mA × 24. Middle case: 60 µA floor,
250 µC a poll. Low: 45 µA, 150 µC. High: 100 µA, 450 µC (20 dBm). Radio only; add about 3–5 mAh a day for motors and
about 0.5 mAh a day for Matter traffic (see below).

| Check-in every | Tap waits (avg / worst) | Average current (middle) | mAh a day: low / **middle** / high | Days on 2300 mAh, middle, with motors |
|---|---|---|---|---|
| 0.25 s | 0.13 / 0.25 s | 1.06 mA | 15.5 / **25.4** / 45.6 | about 75 |
| 0.5 s | 0.25 / 0.5 s | 560 µA | 8.3 / **13.4** / 24.0 | about 125 |
| **1 s** | **0.5 / 1 s** | **310 µA** | **4.7 / 7.4 / 13.2** | **about 190** |
| 2 s | 1 / 2 s | 185 µA | 2.9 / **4.4** / 7.8 | about 255 |
| 3 s | 1.5 / 3 s | 143 µA | 2.3 / **3.4** / 6.0 | about 290 |
| 5 s | 2.5 / 5 s | 110 µA | 1.8 / **2.6** / 4.6 | about 320 |
| 15 s (most a Matter SIT device may use) | 7.5 / 15 s | 77 µA | 1.3 / **1.8** / 3.1 | about 360 |
| 30 s (LIT only) | 15 / 30 s | 68 µA | 1.2 / **1.6** / 2.8 | about 370 |
| Wi-Fi today (`docs/architecture.md`) | about 0.1–1 s | 3–6 mA | **70–150** | weeks |

Below about 1 s the cost climbs fast; above about 3 s it barely drops, because the floor and the motors are left.

## Compared with Wi-Fi

- Today's estimate is 70–150 mAh a day. The Bluetooth sleep clock (3.3 mA, above) explains most of it.
- Espressif's own Wi-Fi numbers for the C6 in auto light sleep, in a shielded box: 0.919 mA at DTIM 1, 0.368 mA at
  DTIM 3, 0.172 mA at DTIM 10, so about 22 / 9 / 4 mAh a day for the chip alone
  ([ESP-IDF Wi-Fi low-power guide](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-guides/low-power-mode/low-power-mode-wifi.html)).
  A real home adds broadcast and mDNS traffic and reconnects, so expect more.
- So a tuned Wi-Fi build (Bluetooth off, DTIM 3) might reach 10–25 mAh a day. Thread at 1 s (about 7) is still
  better, with a similar reaction time, and has no Wi-Fi chatter to wake it. But **fixing the Bluetooth clock is the
  first win either way**, and it can be tested on today's Wi-Fi firmware.

## Matter low-power modes (ICD)

A Matter Thread device that sleeps is an ICD (intermittently connected device). From the connectedhomeip SDK and the
esp-matter example:

- **SIT (short idle time):** the slow poll may be at most **15 s**; the SDK clamps a longer one to 15 s
  (`kSITPollingThreshold`,
  [ICDConfigurationData.h](https://github.com/project-chip/connectedhomeip/blob/master/src/app/icd/server/ICDConfigurationData.h)).
  This is the right mode for blinds: a command must get through without the device asking first.
- **LIT (long idle time):** slower polls, but the controller must register with the device (check-in protocol), and
  an unregistered LIT device falls back to SIT limits
  ([esp-matter icd_app README](https://github.com/espressif/esp-matter/tree/main/examples/icd_app)). LIT is for
  sensors that report, not for things you command. Not needed here.
- **Settings** (esp-matter example defaults, SIT): fast poll 500 ms, slow poll 5 s, active mode 1 s, idle mode 60 s,
  active threshold 1 s. For Tilt: **slow poll 1 s, fast poll 200–500 ms, active threshold about 5 s** (so a second tap
  right after the first is quick), **idle mode duration long, 600 s or more** (see subscriptions below).
- The firmware has `CONFIG_SUPPORT_ICD_MANAGEMENT_CLUSTER=n` today; a Thread ICD build needs it on.

## What makes it worse

- **Matter subscriptions.** Apple Home, Google and the Tilt app each hold a subscription. An ICD picks its report
  max interval to match its **idle mode duration** (`ReadHandler.cpp`,
  [connectedhomeip](https://github.com/project-chip/connectedhomeip/blob/master/src/app/ReadHandler.cpp)). Each
  heartbeat wakes the CPU, sends a report, waits for the ack and runs fast polls for a while: guess 4–10 mC each. With
  a 60 s idle mode and 2 subscribers that is about **3–6 mAh a day**, as much as the polling. With 600 s it is about
  0.5 mAh a day. Also report only real changes (battery level in whole steps, position only after a move).
- **MRP retries.** A sleepy device's advertised retry interval is the base (2 s on Thread) **plus its slow poll**
  ([ReliableMessageProtocolConfig.cpp](https://github.com/project-chip/connectedhomeip/blob/master/src/messaging/ReliableMessageProtocolConfig.cpp),
  [ReliableMessageProtocolConfig.h](https://github.com/project-chip/connectedhomeip/blob/master/src/messaging/ReliableMessageProtocolConfig.h)).
  If a poll is missed, the command waits for the next one, or for a resend about 3+ s later (up to 4 resends). A long
  slow poll makes every lost frame slow. Keep the device close to its parent and the slow poll short.
- **Send power.** At 20 dBm each poll costs about twice what it does at 0 dBm.
- **Deep sleep instead of light sleep.** Each wake is a reboot and a re-attach to the network
  ([deep_sleep example](https://github.com/espressif/esp-idf/blob/master/examples/openthread/ot_sleepy_device/deep_sleep/README.md));
  Espressif suggests it only for sleeps over about 30 minutes. Not for blinds.
- **CSL (synchronized sleepy end device, Thread 1.2).** The parent sends at times the device is listening, so the
  device does not send a poll. On the C6 the listen still costs 74 mA and needs an accurate sleep clock; the
  SuperMini most likely has no 32 kHz crystal (check), so the listen windows get wide. Not worth it here.
- **Always-on extras:** a power LED, the INA3221 monitor in the v3 concept (0.35 mA unless powered down,
  `docs/pcb-v3-concept.md`), or a lock that keeps the chip awake.

## Recommendation

1. **First, on today's Wi-Fi firmware:** turn Bluetooth off after setup (or stop using the main crystal as its sleep
  clock), power down peripherals and flash in light sleep, and check the SuperMini for a power LED. Measure (#6).
2. **For the hub design:** Matter over Thread as a **SIT ICD**, **1 s slow poll**, 200–500 ms fast poll, about 5 s
  active threshold, **600 s or longer idle mode**, low send power. That is about 7 mAh a day for the radio (5–13),
  about 12 with motors and Matter traffic: about half a year on a charge. If measurement shows the high end, 2 s is
  the fallback (about 4.4 mAh a day, a tap waits 1 s on average).
3. Measure two things before deciding: the sleep floor, and the charge of one poll at the chosen send power.

## Open points

- No Espressif measurement of a C6 SED's poll charge was found; the 150–450 µC range is built from datasheet
  currents and frame timing.
- The SuperMini's regulator part and whether it has a power LED.
- The subscription max intervals Apple Home and Google ask for.
