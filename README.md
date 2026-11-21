# Automated Blinds

Open-source, 3D-printable motorized **tilt** for cordless horizontal blinds. Each blind gets a printed tilter in its
headrail; the wand still works by hand. A battery-powered controller drives up to 3 blinds. Control is from the
**Tilt** iPhone app and **Apple Home** (Matter over Wi-Fi).

Only the current version of each thing is kept here. Older versions are in the Git history.

## What is in here
| Folder | What |
|---|---|
| [app/Tilt](app/Tilt) | The iPhone app (SwiftUI) with its widget and Control Center buttons |
| [firmware/blinds_matter](firmware/blinds_matter) | Controller firmware (ESP32-C6, ESP-IDF + esp-matter) |
| [firmware/as5600_setup](firmware/as5600_setup) | Bench tool that switches a new AS5600 angle sensor to PWM output |
| [hardware/mechanical](hardware/mechanical/README.md) | Tilter and controller box: Fusion 360 generators and print files |
| [hardware/pcb](hardware/pcb/README.md) | Controller PCB (v2 built; v3 concept on hold) |
| [hardware/BOM.md](hardware/BOM.md) | Parts to buy |
| [tools](tools) | Build, check and print helpers (see below) |
| [docs](docs) | Design notes, build guides, reference photos |

## Start here
- **What to do next:** [docs/todo.md](docs/todo.md)
- **Tilter** (parts, printing, assembly, checks): [hardware/mechanical/stl/tilter/README.md](hardware/mechanical/stl/tilter/README.md)
- **Controller box:** [docs/controller-box.md](docs/controller-box.md). **PCB build:** [docs/pcb-build.md](docs/pcb-build.md)
- **Wiring a tilter:** [docs/tilter-wiring.md](docs/tilter-wiring.md)
- **Firmware and updates:** [firmware/README.md](firmware/README.md)
- Background: [architecture](docs/architecture.md), [requirements](docs/requirements.md), [decisions](docs/open-questions.md), [lift ideas](docs/lift-bonus.md)

## Tools
| Tool | Does |
|---|---|
| `tools/fusion_tilter.py` | Builds the tilter in Fusion, runs the collision and gear checks, exports STLs |
| `tools/fusion_thin.py` | Thin-wall scan of the built tilter |
| `tools/orient.py`, `tools/bambu.py` | Turn the STLs to print orientation; build the Bambu Studio project (PLA plate + PETG plate) |
| `tools/fusion_controller.py` | Builds the controller box in Fusion |
| `tools/flash_matter.sh` | Builds the firmware and sends it to a controller over Wi-Fi |
| `tools/blinds_client.py` | Talks to a controller over its secured channel (testing) |
| `tools/pcb_guide.py` | Generates the PCB build guide |

Fusion scripts run through the FusionBridge add-in: `python3 hardware/mechanical/fusion/fusion.py exec tools/<script>.py`.

## License
To be decided before publishing.
