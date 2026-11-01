# Firmware

ESP32-C6 (SuperMini), Arduino-ESP32 3.x or ESP-IDF with esp-matter. **Not started.** Hardware it drives:
[architecture](../docs/architecture.md), pins: [controller-v4.md](../docs/controller-v4.md#dev-board).

## Per port (3 per controller)
- **Motor:** IN1 / IN2 PWM (20 kHz) to the DRV8833 in the tilter. **EN** high wakes the driver and powers the AS5600;
  low between moves (both sleep).
- **Angle:** AS5600 analog OUT on an ADC pin (1 kΩ + 100 nF filter), read only while EN is high. Absolute, so no
  homing; a wand move while asleep is read correctly at the next wake.
- **Move:** soft start/stop, stop at the target angle, **stall stop** when the angle stops changing (≤ 250 ms).

## Planned modules
`motor` (PWM, EN, motion profile, stall detection), `angle` (ADC averaging, calibration to the slat range),
`calibration` (end limits, which end is "closed"), `storage` (NVS), `matter` (one Window Covering endpoint with tilt per
port; Power Source cluster for battery level), `power` (Thread sleepy end device, battery voltage on GPIO 3, charger
STAT on GPIO 7), `ota`.

## First milestone
[bench_test](bench_test/bench_test.ino) (wiring in [docs/bench-test.md](../docs/bench-test.md)): drive one tilter from the battery, read the angle, find out why the motor stalls under load, measure sleep current.
