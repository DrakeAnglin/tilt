# System architecture

How the parts fit together today: the tilter on each blind, the controller that drives up to 3 of them, and the phone.
Words like Blind, Tilter, Controller, Port and Marks are defined in [CONTEXT.md](../CONTEXT.md).

## The parts
- **Tilter** (one per blind): a printed worm gearbox on the blind's tilt rod, an N20 300 RPM motor, and a sensor module
  with an AS5600 angle sensor, a DRV8833 motor driver and an RJ12 jack. The wand still turns the blind by hand.
  Build: [tilter](../hardware/mechanical/stl/tilter/README.md), [wiring](tilter-wiring.md).
- **Controller** (one per up to 3 blinds): an ESP32-C6 SuperMini on a carrier PCB, one protected 18650 cell, an
  Adafruit 6092 charger with its own USB-C, and 3 RJ12 ports, in a box that slides into a headrail.
  Build: [PCB](pcb-build.md), [box](controller-box.md).
- **Cord**: a white, straight-wired RJ12 phone cord from each tilter to a port.
- **Tilt Hub** (one per home): an ESP32-C6 on a USB wall plug ([firmware/tilt_hub](../firmware/tilt_hub/README.md)).
  The controllers talk to it over Thread and sleep between check-ins. **Apple Home** adds the hub once (Matter over
  Wi-Fi) and sees every blind through it.
- **Phone**: the **Tilt** iPhone app reaches each controller through the hub, on the home Wi-Fi.

```
 USB-C ─► Adafruit 6092 ─VIN─┐                      ┌───────────────────────────────┐
 solar (optional) ─J8─D2─────┴─ PWR (6.2 V zener)   │ ESP32-C6 SuperMini            │
                  6092 BAT ═══ 18650 (protected)    │ Thread to the hub, BLE setup  │
                     │                              │ GPIO: IN1, IN2, EN, angle ×3  │
                     └─ BAT+ ──D3──► ESP 5V pin      │ ADC: battery, PWR             │
                     │                              └──┬──────┬──────┬──────────────┘
                     └─ 0.75 A fuse ×3                   │220 Ω │10 Ω   ▲ 1 k + 100 nF
                            ▼                            ▼      ▼       │
     RJ12 port ×3 ═══ white RJ12 cord ═══ tilter: DRV8833 ─ N20, AS5600 (PWM out)
     (battery +, IN1, GND, angle, EN, IN2)       (EN wakes the driver and powers the sensor)
```

## Why it is built this way
- **No cloud.** The app talks to controllers directly, and Apple Home covers voice and away-from-home control
  ([ADR 0001](adr/0001-no-cloud-local-first.md)). The one use of iCloud is for notices: join requests between phones
  and the hub's push alerts (no server of our own).
- **Thread only, through a Tilt Hub** ([ADR 0003](adr/0003-thread-only-tilt-hub.md)). A sleeping Thread device uses
  about a tenth of the battery of Wi-Fi power save, and a tap reacts in about half a second. The hub is Apple Home's
  Matter device for every blind, so no Apple Thread border router is needed.
- **ESP32-C6 SuperMini.** Small (about 22.5 × 18 mm), Thread and Bluetooth (Bluetooth for first setup),
  enough pins for 3 ports. It plugs into sockets, so it can be swapped.
- **Motor driver in each tilter.** The cord carries battery power and logic, not motor current switching at 20 kHz.
  So the flat, untwisted cord does not couple motor noise into the angle wire, and a tilter is a complete unit (motor,
  driver, sensor, plug).
- **AS5600 in PWM mode.** Every AS5600 has the same I2C address, so each port reads its own sensor on one wire
  instead. The sensor is switched to PWM output once on the bench ([as5600_setup](../firmware/README.md)): the angle
  is the share of each 115 Hz frame that the line is high, so it does not shift with the supply or with motor current
  in the ground wire. The ESP's capture timer stamps every edge, so all 3 ports can be read while blinds move.
- **Sensors on only while moving.** The AS5600 is absolute, so it can be off between moves. One EN line per port
  wakes that tilter's driver and powers its sensor. A wand turn while it is off is still read right next time.
- **Motors straight from the cell.** The DRV8833 runs from 2.7 to 10.8 V, so the motor gets the cell's 3.0–4.2 V. The
  6 V N20 runs at about 60% of its rated speed; the worm gearbox has torque to spare.
- **Charger used as a charger only.** The cell feeds the whole board (motors and ESP) through a splice in the J5 plug,
  and the 6092 just keeps it topped up. A charger's load output gives about 1 A; an 18650 gives 3 A or more. The
  6092 stops after 6 hours of nonstop charging; replugging restarts it.
- **Protection.** A 0.75 A resettable fuse on each port's battery +, series resistors on the cord lines, a 470 µF
  capacitor by the jacks, keyed and labeled plugs, and a 6.2 V zener that clamps the solar input. The cell has its own
  protection board (protected cells only).
- **White outside.** White cords, white printed parts.

## Battery rules
From [CONTEXT.md](../CONTEXT.md) and `firmware/blinds_matter/main/config.h`. The Battery level is worked out from the
resting cell voltage.

| State | When | What happens |
|---|---|---|
| Low battery | under 20% | warning in the app and in Apple Home |
| Critical battery | under 10% | Schedules pause; blinds still move when told |
| Motor cut-off | resting cell under 3.35 V | no motor runs until it charges |

## Power budget (estimates, not measured)
These are rough estimates for 3 blinds and about 4 moves each a day. **They have not been measured.** Real numbers
come from [#6 (battery life)](https://github.com/DrakeAnglin/tilt/issues/6) and will replace this table.

| Load | mAh a day (estimate) |
|---|---|
| ESP32-C6 asleep on Thread (one check-in a second), plus regulator and charger standby | about 7–15 (research estimate; on Wi-Fi it was about 70–150) |
| Motors: 12 moves × about 3 s × about 250 mA from the cell | about 3–5 |
| AS5600, one at a time, only while moving | under 1 |

The radio is most of it. If the estimate holds, a 2600 mAh cell (about 2300 mAh usable) lasts several months without
charging (on Wi-Fi it was weeks). It is still to be measured.

## Pins
From `firmware/blinds_matter/main/config.h` (PCB v2):

| Port | IN1 | IN2 | EN | Angle |
|---|---|---|---|---|
| 1 | GPIO14 | GPIO18 | GPIO7 | GPIO6 |
| 2 | GPIO19 | GPIO20 | GPIO5 | GPIO4 |
| 3 | GPIO16 | GPIO17 | GPIO1 | GPIO2 |

Battery voltage on GPIO3 and input power (USB or solar) on GPIO0, each through a 1 MΩ / 1 MΩ divider. USB reads
about 4.3 V on the input line.

## RJ12 pinout
Cords must be **straight-wired**: pin 1 to pin 1. Check every cord.

| Pin | Net | At the tilter |
|---|---|---|
| 1 | battery + (3.0–4.2 V) | DRV8833 VCC, 10 µF to GND |
| 2 | IN1 (PWM) | DRV8833 IN1 |
| 3 | GND | DRV8833 GND, AS5600 GND |
| 4 | angle | AS5600 OUT |
| 5 | EN (3.3 V from an ESP pin) | AS5600 VCC **and** DRV8833 EEP (sleep): one line wakes both |
| 6 | IN2 (PWM) | DRV8833 IN2 |

A reversed cord would put battery + on IN2, so the continuity check matters.

## Connectors
| Link | Connector |
|---|---|
| Tilter to controller | RJ12 6P6C, white straight-wired cord |
| Battery to PCB | JST-XH 2-pin (on the cell's lead) |
| Charger to PCB | JST-XH 6-pin harness |
| Solar to PCB (optional) | JST-ZH 2-pin. v3 gets a DC jack instead ([#8](https://github.com/DrakeAnglin/tilt/issues/8)) |
| Charging | the 6092's own USB-C, at end B of the box |

## Software
- **Firmware** ([firmware/README.md](../firmware/README.md)): ESP-IDF and esp-matter. Soft start, slows near the
  target, stops on a stall, follows a blind turned by hand. Schedules run on the controller, so they work with the
  phone away.
- **App** ([app/README.md](../app/README.md)): SwiftUI, with a widget and Control Center buttons. No server. It sets up
  a new controller over Bluetooth and hands it the hub's Thread network (sealed, to the controller only), then talks to
  it through the hub over a secured channel with a key per phone (Owner and Guests); the hub cannot read it. Apple
  Home sees the blinds through the hub (added once, with the hub's own setup code).
- **Push alerts** (owners only, at home or away): the hub watches for problems (a blind stalled, a controller not
  responding, battery low / almost empty / empty, an update failed) and writes an Alert record to the app's iCloud
  (CloudKit public database) with a server-to-server key. Each owner's iPhone has a subscription on that controller's
  random topic, so iCloud pushes it; the app's alerts extension (TiltAlerts) words it. Each alert is sent once; alerts
  wait on the hub while the internet is down. The only alert made on the phone is "Tilt Hub is offline" (on the home
  Wi-Fi), since the hub can't send that one. Records hold no keys or addresses. Details:
  [firmware/tilt_hub/README.md](../firmware/tilt_hub/README.md#push-alerts).
- **Firmware updates**: signed release files on the public `DrakeAnglin/tilt-site` repo; the app hands them to the hub,
  which feeds them to the controller over Thread
  ([app-store.md](app-store.md)).
