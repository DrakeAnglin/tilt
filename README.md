# Automated Blinds

Quiet, open-source, 3D-printable motorized **tilt** for existing cordless horizontal blinds. Each blind gets a
printed tilter that replaces the factory one, keeps the wand working by hand, and reads its own slat angle. A
battery-powered controller in the headrail drives up to 3 blinds and shows up in **Apple Home and Alexa** through
Matter over Thread.

> **Status (2026-10-29):** tilter v0.4 + sensor module locked and printing; controller box (ControllerV4) and dev
> board designed; parts ordered (see the [BOM](hardware/BOM.md)). Firmware not started.

## How it works
```
 blind ×8                                               controller ×3 (one per 3 blinds, in a headrail)
 ┌───────────────────────────────────────┐   white     ┌────────────────────────────────────────────┐
 │ tilter: worm + worm wheel on the rod  │  RJ12 cord  │ ESP32-C6 (Matter over Thread)              │
 │   N20 motor ─ helical pinion          │◄───────────►│ MCP73871 charger + 18650 cell              │
 │ sensor module: AS5600 angle sensor,   │ VBAT, IN1,  │ USB-C charge port, optional solar panel    │
 │   DRV8833 motor driver, RJ12 jack     │ IN2, EN,    │ 3 RJ12 ports                               │
 │ wand still turns it by hand           │ ANGLE, GND  │                                            │
 └───────────────────────────────────────┘             └────────────────────────────────────────────┘
```
- **Self-locking worm (16:1)** holds the slats with the motor off; the wand back-drives the N20 through a crossed
  helical pair, so hand use still works.
- **Absolute angle** from an AS5600 magnetic sensor on a gear off the worm wheel: the position is known at power-up
  and after someone uses the wand. No homing.
- **Cordless:** 18650 cell, charged over USB-C or by a small solar panel on the glass. Estimated 2.5–3 months per
  charge with no sun.

## Documents
| | |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Electronics, power budget, connectors, RJ12 pinout, why each choice |
| [docs/controller-v4.md](docs/controller-v4.md) | Controller box, dev-board layout, pin plan, assembly |
| [docs/dev-board-build.md](docs/dev-board-build.md) | **Building the controller dev board**: step by step with pictures, which parts have a direction, every hole and wire |
| [docs/tilter-wiring.md](docs/tilter-wiring.md) | **Wiring a tilter** (motor side): RJ12 breakout, DRV8833, AS5600, motor, with a diagram and checks |
| [docs/bench-test.md](docs/bench-test.md) | Breadboard wiring + test plan for one tilter, with a test sketch |
| [hardware/mechanical/stl/v0.4/README.md](hardware/mechanical/stl/v0.4/README.md) | Tilter + sensor module: print files, orientation, hardware, assembly, fits |
| [hardware/BOM.md](hardware/BOM.md) | Everything to buy, with links, quantities and what each part is for |
| [docs/requirements.md](docs/requirements.md) | Numbered requirements |
| [docs/open-questions.md](docs/open-questions.md) | Decisions made and still open |
| [docs/motor-analysis.md](docs/motor-analysis.md), [docs/measure-your-blinds.md](docs/measure-your-blinds.md) | Motor sizing and how to measure a blind |
| [docs/lift-bonus.md](docs/lift-bonus.md) | Ideas for motorized raise/lower (later) |
| [docs/archive/](docs/archive/) | Superseded designs, kept for history |

## Repository layout
```
docs/                      design documents, renders, reference photos, archive/
hardware/
  BOM.md                   shopping list
  mechanical/
    fusion/                Fusion 360 generators (TiltPartsV4, TiltPod, ControllerV4) + FusionBridge add-in
    stl/v0.4/              current print files (+ print/ = already oriented); stl/v0.3/ = old
  pcb/                     custom PCB (after the dev board works)
firmware/                  ESP32-C6 firmware (not started)
app/                       setup / calibration UI (not started)
tools/                     Fusion checks (interference, walls, gear sweeps), STL orientation, Bambu project builder
```

## Roadmap
1. ~~Measure the blinds; design and test-print the tilter~~ (v0.4 printing)
2. **Bench:** one tilter + ESP32-C6 + DRV8833 on the bench: torque from the battery, noise, sensor accuracy, sleep current
3. **Dev boards:** solder the 3 controller boards ([controller-v4.md](docs/controller-v4.md)), print the boxes
4. **Firmware:** motor control with stall stop, angle calibration, Matter Window Covering (tilt) per port, battery level
5. **Install** 8 blinds; live with it; tune
6. **Custom PCB** to replace the perfboard ([hardware/pcb](hardware/pcb/README.md))
7. **MakerWorld release:** print profiles, assembly guide, BOM
8. Lift (bonus)

## License
TBD before publishing. Common choice for open hardware: CERN-OHL-S (hardware) + MIT (firmware/app) + CC BY-SA (docs/models).
