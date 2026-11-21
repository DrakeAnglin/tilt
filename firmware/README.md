# Firmware

ESP32-C6 (SuperMini), Arduino-ESP32 3.x. Hardware it drives:
[architecture](../docs/architecture.md), pins: [controller-v4.md](../docs/controller-v4.md#dev-board).

## V1 app: [blinds](blinds/blinds.ino) (on the PCB now)
Web app at http://blinds-pcb.local, made for the phone. Build and send over Wi-Fi: `tools/flash_blinds.sh`
(a firmware that cannot join Wi-Fi rolls back to the old one by itself).

- **Blinds page:** each blind has Close up / Open / Close down, a tilt slider, a favorite, Stop. One blind moves at a time.
- **Setup:** three marks per blind (closed up, open, closed down), with hold-to-turn buttons. Tilt is -100..0..+100.
- **Schedule:** 8 slots (time, days, position, blinds). They run on battery with Wi-Fi off.
- **Settings:** names, what "Close" means, time zone, battery mode, check-in time, Wi-Fi network.
- **Developer page** (switch in Settings): live readings + angle graph, raw motor tests and marks, battery week graph
  and use estimate, firmware / network / counters, update from a file, log.
- **Battery plan** (sleep.h): input power present (above 3.8 V on the input sense) = Wi-Fi on. On battery it deep-sleeps,
  wakes every 30 s for a moment to look for input power and run schedules, and joins Wi-Fi every 15 min (setting) for
  25 s. "Stay on" mode keeps Wi-Fi on instead (about a week per charge).
- **No Wi-Fi for 30 s:** it opens its own network `Blinds-Setup` (http://192.168.4.1) to pick one.
- **Motion** (motion.h): soft start, slows near the target, stops on a stall (then backs off 120 ms), 20 s limit, final
  position read with the motor stopped and corrected with short nudges. Motor direction is learned.
- **Angle is corrected for the 3.3 V rail** (power.h): the AS5600's output is a fraction of its supply, and the rail
  sags with the battery (3.0 V at a 3.6 V cell). The rail is measured on the input-sense pin's capacitor.
- **Empty ports** are found by pushing the angle pin low then high: a floating line keeps the push, a sensor does not.
- Work on the app without the board: `python3 tools/ui_mock.py` then http://localhost:8765 (`tools/build_ui.py` packs
  `blinds/ui/` into `blinds/ui.h`).
- Not yet: Matter (Apple Home, Alexa). It needs the 1.9 MB app layout, which takes one USB flash.

## Per port (3 per controller)
- **Motor:** IN1 / IN2 PWM (20 kHz) to the DRV8833 in the tilter. **EN** high wakes the driver and powers the AS5600;
  low between moves (both sleep).
- **Angle:** AS5600 analog OUT on an ADC pin (1 kΩ + 100 nF filter), read only while EN is high. Absolute, so no
  homing; a wand move while asleep is read correctly at the next wake.
- **Move:** soft start/stop, stop at the target angle, **stall stop** when the angle stops changing (≤ 250 ms).
- **Angle while moving reads high:** motor current returns on the same RJ12 GND wire the angle is measured against,
  shifting it by up to ~0.2 V (~20°) at 0.5 A. Use moving readings only for "still turning", and take the final
  position with the motor stopped (brake, wait ~20 ms, then sample).

## Planned modules
`motor` (PWM, EN, motion profile, stall detection), `angle` (ADC averaging, calibration to the slat range),
`calibration` (end limits, which end is "closed"), `storage` (NVS), `matter` (one Window Covering endpoint with tilt per
port; Power Source cluster for battery level), `power` (Thread sleepy end device, battery voltage on GPIO 3,
input-power voltage on GPIO 6 (1 M / 1 M; charging = input present and the cell below 4.2 V)), `ota`.

## PCB test
[pcb_test](pcb_test/pcb_test.ino): the bench test with the carrier PCB's pin map (hardware/pcb/netlist.py) and a port
selector (one port runs at a time). Web page http://blinds-pcb.local; serial / telnet keys as bench_test plus `p` (next
port) and `v` (battery, input and all three angles). Needs its own `secrets.h` (copy of bench_test's).
`cd firmware && bin/arduino-cli compile --upload --fqbn esp32:esp32:esp32c6:CDCOnBoot=cdc -p <USB port or blinds-pcb.local> pcb_test`

## First milestone
[bench_test](bench_test/bench_test.ino) (wiring in [docs/bench-test.md](../docs/bench-test.md)): drive one tilter from the battery, read the angle, find out why the motor stalls under load, measure sleep current.
