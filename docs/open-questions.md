# Decisions and open questions

## Decisions
| # | Question | Decision | Status |
|---|---|---|---|
| D1 | Drive point | **Motorized tilter**: printed worm + worm wheel on the rod, N20 on the worm through crossed helicals; wand kept | Decided, v0.4 printing |
| D2 | N20 gear ratio | 6 V 300 RPM (≈1:50), back-drivable by the wand; full travel ≈ 13 motor turns | Decided (bought) |
| D3 | Ports per controller | 3 tilt ports, all on one end of the box | Decided |
| D4 | MCU | ESP32-C6 (SuperMini for the dev boards) | Decided 2026-10-28 |
| D5 | Firmware framework | Arduino-ESP32 3.x / ESP-IDF with esp-matter | Proposed |
| D6 | Smart home protocol | Matter over Thread (sleepy end device) | Decided 2026-10-28; verify Alexa's tilt handling early |
| D7 | Setup / calibration UI | Through the Matter apps where possible; small web or BLE tool for calibration | Open |
| D8 | Tilter ↔ controller connector | RJ12 6P6C, white straight-wired cords; motor driver in each tilter | Decided 2026-10-28 |
| D9 | Power | 18650 per controller, USB-C charging, optional 6 V 0.8 W solar | Decided 2026-10-28 (solar optional) |
| D10 | Vibration isolation | Not needed so far (printed helicals + grease); revisit after noise tests | Deferred |
| D11 | Keep the manual wand? | Yes: it hangs from the worm's loop as before | Decided |
| D12 | License | CERN-OHL-S / MIT / CC BY-SA | Ask before publishing |
| D13 | Position sensing | AS5600 absolute magnetic sensor, analog out, powered only while moving | Decided |
| D14 | Controller placement | In a headrail, under the tilt rod (rod in a groove along the box lid) | Decided 2026-10-29 |

## Still open
- [ ] Solar: keep it or charge over USB-C only (saves ~$46). If kept: which rail face looks at the glass.
- [ ] Cord lengths from each controller to its blinds, and which blinds group onto which controller.
- [ ] Bench results: N20 torque from the battery, noise at 1 m, sensor accuracy over the travel, sleep current.
- [ ] How the printed worm pair wears; the wheel's square bore fit.
- [ ] Alexa's handling of Matter tilt (Apple Home handles it).
- [ ] License.

## Requirements this project added along the way (now in [requirements.md](requirements.md))
Absolute position (no homing), stall stop, manual wand use, local control without a cloud, OTA updates, cordless power
with battery level reporting, battery temperature protection, modular plug-in wiring, support-free printing.

## Findings from the headrail (2026-10-25 / 26)
| Photo | What it shows |
|---|---|
| [top view](reference/headrail-top-view.jpg) | Cordless **lift module**: two cord spools with gear rims and constant-force spring drums. Self-contained |
| [end, tilt drum](reference/headrail-end-tilt-drum.jpg) | Tilt drum in its cradle on the **4 mm square steel tilt rod** |
| [end profile](reference/headrail-end-profile.jpg) | U-channel profile with inward lips |
| [square rod](reference/headrail-square-tilt-rod.jpg) | Square rod runs the full length above the long lift/holding part |
| [ladder cords](reference/tilt-drum-ladder-cords.jpg), [printed drum](reference/printed-tilt-drum-front.jpg) | Tilt drum with ladder cords; the owner's printed copy |
| [tilter photos](reference/) | Factory tilter: worm + 16T wheel, 16:1, wand loop through the corner notch |

- Headrail and internals are plastic: everything slides into the channel; nothing clamps the thin walls.
- The tilter sits in the 110 mm pocket between the end cap and the first tilt drum; the rod passes through its wheel.
- Tilt travel: 11–12 wand turns closed → closed ≈ 250–270° of rod. Tilt torque is low.
- ~6.5 mm clearance above the installed headrail: nothing may stick up more than ~5 mm.
- Lift is a separate module, not connected to the tilt rod ([lift-bonus.md](lift-bonus.md)).

## To do (mechanical)
- **Short tilt rod** (owner, 2026-11-15): the blind's rod stops about 21 mm into the tilter (a crimp on the rod), so it
  never reached the sensor's rod gear. Rev K (sensor bar + long-hub carrier + wheel bore, `stl/v0.8/README.md`) is the
  fix for the current tilter; drawn and checked in Fusion, not printed yet. **v0.9** (`stl/v0.9/README.md`,
  `TiltPartsV9`) is the new revision: sensor sleeve driven by the carrier (rod still slides through), one motor stage,
  79.1 mm long. Drawn and checked 2026-11-15, not printed.
- **Redesign the gearbox housing for one reduction set, not two** (done in v0.9, to be proven in print) (owner, 2026-11-15). One of the two sets of
  reduction ("torque") gears was taken out: the extra torque had been added to overcome binding that turned out to be
  in the blinds themselves. With one set the blind moves much faster (about 19°/s at the rod, was 3 to 6) and still
  reaches fully closed up and down. The motor shell and its gear stations should be redrawn for the shorter train.
