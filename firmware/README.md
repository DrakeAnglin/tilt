# Firmware

## [blinds_matter](blinds_matter): the controller
ESP32-C6, ESP-IDF v5.5 + esp-matter. One controller drives up to 3 blinds.

- **Control:** the Tilt iPhone app (secured channel over Wi-Fi, Bluetooth for first setup) and Apple Home (Matter over Wi-Fi).
- **Per port:** IN1 / IN2 to the DRV8833 in the tilter, EN wakes the driver and the angle sensor, angle = AS5600 PWM
  output read by a capture timer (`main/pwmin.h`).
- **Motion** (`main/motion.h`): soft start, slows near the target, stops on a stall, blinds can move at the same time,
  and can follow a blind that is turned by hand.
- **Battery** (`main/sleep.h`, `main/power.h`): dozes between jobs; schedules run from the controller.

Build and send over Wi-Fi (a firmware that cannot join Wi-Fi rolls back by itself):

```bash
tools/flash_matter.sh
```

Needs `blinds_matter/main/secrets.h` (copy `secrets.h.example`). Test from the Mac with `tools/blinds_client.py`.

## [as5600_setup](as5600_setup): sensor bench tool
Switches a new AS5600 from analog to PWM output (burned once, over I2C) before it goes into a tilter.
