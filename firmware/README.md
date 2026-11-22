# Firmware

## [blinds_matter](blinds_matter): the controller
ESP32-C6, ESP-IDF v5.5 + esp-matter. One controller drives up to 3 blinds.

- **Control:** the Tilt iPhone app (secured channel over Wi-Fi, Bluetooth for first setup) and Apple Home (Matter over Wi-Fi).
- **Per port:** IN1 / IN2 to the DRV8833 in the tilter, EN wakes the driver and the angle sensor, angle = AS5600 PWM
  output read by a capture timer (`main/pwmin.h`).
- **Motion** (`main/motion.h`, `main/tilter.h`): soft start, slows near the target, stops on a stall, blinds can move at
  the same time, and can follow a blind that is turned by hand.
- **Battery** (`main/power.h`): dozes between jobs; Battery level, Low and Critical battery, and the 3.35 V Motor
  cut-off (`main/config.h`). Schedules run from the controller.

### First flash (over USB, on the bench)
Flash the ESP32-C6 before it goes on the PCB: in the box there is no room for a cable. Needs ESP-IDF in `~/esp/esp-idf`
and esp-matter in `~/esp/esp-matter`, and `blinds_matter/main/secrets.h` (copy `secrets.h.example` and fill it in).

A public release build (no Wi-Fi in it; set it up from the app over Bluetooth):

```bash
firmware/blinds_matter/build.sh -B build-release -DTILT_RELEASE=1 -p /dev/cu.usbmodemXXXX flash
```

Or a developer build, which joins the Wi-Fi in `secrets.h` by itself:

```bash
firmware/blinds_matter/build.sh -p /dev/cu.usbmodemXXXX flash monitor
```

### Updates
- **From the app:** a room's settings show "Update to …" when a newer firmware is published. Release files are signed and live on the
  public `DrakeAnglin/tilt-site` repo; how to publish one: [docs/app-store.md](../docs/app-store.md).
- **From the Mac** (developer): build and send over Wi-Fi. A firmware that cannot join Wi-Fi rolls back by itself.

```bash
tools/flash_matter.sh
```

Test from the Mac with `tools/blinds_client.py`. Mac tests of the pure logic: `tools/firmware_tests.sh`.

## [as5600_setup](as5600_setup): sensor bench tool
Switches a new AS5600 from analog to PWM output, burned once over I2C, before it goes into a tilter. Runs on a spare
ESP32-C6 over USB serial (115200). Wiring and keys are at the top of
[`as5600_setup.ino`](as5600_setup/as5600_setup.ino): VCC to 3V3, GND, SDA to GPIO6, SCL to GPIO7, OUT to GPIO5, the
magnet over the chip. Press `t` to try PWM, `w` to watch the angle, then `B` to burn (once per sensor; type YES).
