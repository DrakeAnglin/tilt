# Firmware

## [blinds_matter](blinds_matter): the controller
ESP32-C6, ESP-IDF v5.5 + esp-matter. One controller drives up to 3 blinds.

- **Network:** Thread only, to the [Tilt Hub](tilt_hub/README.md) (`main/hub_link.h`); no Wi-Fi
  ([ADR 0003](../docs/adr/0003-thread-only-tilt-hub.md)). The app's secured commands come through the hub, or over
  Bluetooth at first setup; Apple Home sees the blinds through the hub.
- **Per port:** IN1 / IN2 to the DRV8833 in the tilter, EN wakes the driver and the angle sensor, angle = AS5600 PWM
  output read by a capture timer (`main/pwmin.h`).
- **Motion** (`main/motion.h`, `main/tilter.h`): soft start, slows near the target, stops on a stall, blinds can move at
  the same time, and can follow a blind that is turned by hand.
- **Battery** (`main/power.h`): sleeps between check-ins with the hub; Battery level, Low and Critical battery, and the 3.35 V Motor
  cut-off (`main/config.h`). Schedules run from the controller.

### First flash (over USB, on the bench)
Flash the ESP32-C6 before it goes on the PCB: in the box there is no room for a cable. Needs ESP-IDF in `~/esp/esp-idf`
and esp-matter in `~/esp/esp-matter`. No secrets are built in: set it up from the app over Bluetooth.

```bash
firmware/blinds_matter/build.sh -p <USB port> flash monitor
```

### Updates
From the app: a room's settings show "Update to …" when a newer firmware is published. Release files are signed and
live on this repo's GitHub releases.

### For developers
- **Publish a release:** [docs/developer/firmware-release.md](../docs/developer/firmware-release.md).
- **Update from the Mac:** build, sign and send through the hub. A firmware that cannot reach the hub rolls back by
  itself.

  ```bash
  tools/flash.sh <controller id>
  ```
- **Test tools:** talk to a controller from the Mac with `tools/blinds_client.py`. Mac tests of the logic and, on a
  stand-in board, of the controller's own code: `tools/firmware_tests.sh`.

## [tilt_hub](tilt_hub): the Tilt Hub
ESP32-C6 on a USB wall plug: Matter bridge on Wi-Fi for Apple Home, its own Thread network for the controllers,
firmware updates, backups and finding new controllers. See its [README](tilt_hub/README.md).

## [as5600_setup](as5600_setup): sensor bench tool
Switches a new AS5600 from analog to PWM output, burned once over I2C, before it goes into a tilter. Runs on a spare
ESP32-C6 over USB serial (115200). Wiring and keys are at the top of
[`as5600_setup.ino`](as5600_setup/as5600_setup.ino): VCC to 3V3, GND, SDA to GPIO6, SCL to GPIO7, OUT to GPIO5, the
magnet over the chip. Press `t` to try PWM, `w` to watch the angle, then `B` to burn (once per sensor; type YES).
