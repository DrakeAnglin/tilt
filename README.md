# Automated Blinds

Quiet, open-source, 3D-printable motorization for existing cordless horizontal blinds.
One ESP32 controller drives up to 3 blinds over Wi-Fi, with voice control through
Alexa and Apple Home, and a setup app for calibration.

> Status: **tilt mechanism v0.3, ready for a test print** (see [hardware/mechanical/ASSEMBLY.md](hardware/mechanical/ASSEMBLY.md)).
> History: **v2 restart.** v1 used large hobby servos. They were loud, could only turn 180°,
> and burned out from being powered all the time. v2 uses small gear motors with encoders that switch
> off once they reach position.

## Goals at a glance

| | |
|---|---|
| Controller | ESP32-S3 on a custom PCB, 3 motor ports (+1 spare) |
| Motors | N20 micro gear motor (no encoder) driving the factory worm through a printed helical gear; AS5600 magnetic sensor reads the tilt rod |
| Power | One 5 V USB-C wall adapter. No mains wiring on the board |
| Smart home | Matter over Wi-Fi as a Window Covering device: Apple Home, Alexa, Google Home, Home Assistant |
| Setup | Web app served by the controller, optional phone app later |
| Mechanics | All 3D printed. Rigid PETG/PLA frame with soft TPU isolation for quiet operation |
| Bonus | Motorized raise/lower using the cordless spring mechanism ([lift notes](docs/lift-bonus.md)) |

## Repository layout

```
docs/
  requirements.md         What the system must do (numbered, testable)
  motor-analysis.md       Will the N20 work? Torque, speed, noise, alternatives
  measure-your-blinds.md  How to measure torque/turns before committing to a motor
  architecture.md         Electronics, power, firmware, connectivity, app
  lift-bonus.md           Ideas for raising/lowering cordless blinds
  open-questions.md       Decisions still needed + things the original list missed
  reference/              Sketches and photos of the existing blinds
hardware/
  pcb/                    KiCad project (TBD)
  mechanical/             CAD sources + STLs/3MF (TBD)
firmware/                 ESP32 firmware (TBD)
app/                      Setup app (TBD)
```

## Roadmap

1. **Measure** the real blinds (torque, turns, headrail internals). See [measure-your-blinds.md](docs/measure-your-blinds.md)
2. **Breadboard prototype:** ESP32-S3 dev board + DRV8833 breakout + one N20. Prove torque, noise, encoder homing
3. **Matter spike:** expose one blind to Apple Home and Alexa, and confirm how each ecosystem handles tilt
4. **Mechanical v1:** printed headrail mount + coupler, noise testing with different TPU hardnesses
5. **PCB v1:** 3-port controller, USB-C power
6. **Firmware v1:** calibration, stall detection, position memory, OTA
7. **Setup app:** web UI first
8. **Lift (bonus)**
9. **MakerWorld release:** print profiles, assembly guide, BOM with links

## License

TBD before publishing. Common choice for open hardware: CERN-OHL-S (hardware) + MIT (firmware/app) + CC BY-SA (docs/models).
