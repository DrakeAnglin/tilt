# Tilt

Open-source, 3D-printable motorized **tilt** for cordless horizontal blinds. Each blind gets a printed tilter in its
headrail; the wand still works by hand. A battery-powered controller drives up to 3 blinds. Control is from the
**Tilt** iPhone app and **Apple Home**, through a **Tilt Hub**: the controllers talk Thread to the hub and sleep,
and the hub is Apple Home's Matter device for every blind. No cloud, no account.

Only the current version of each thing is kept here. Older versions are in the Git history.

## Start here
- **Build one:** [docs/build-guide.md](docs/build-guide.md): parts, printing, tilter, controller, flashing, app,
  Apple Home.
- **How it works:** [docs/architecture.md](docs/architecture.md). Words used everywhere: [CONTEXT.md](CONTEXT.md).
- **What to do next:** [GitHub issues](https://github.com/DrakeAnglin/tilt/issues). There are no to-do files.

## Docs
| Page | What |
|---|---|
| [build-guide.md](docs/build-guide.md) | The whole build, in order |
| [hardware/BOM.md](hardware/BOM.md) | Parts to buy |
| [Tilter](hardware/mechanical/stl/tilter/README.md), [tilter wiring](docs/tilter-wiring.md) | Printing, assembling and wiring a tilter |
| [pcb-build.md](docs/pcb-build.md), [controller-box.md](docs/controller-box.md) | Soldering the controller PCB; the box |
| [firmware/README.md](firmware/README.md) | Flashing and updates |
| [architecture.md](docs/architecture.md), [requirements.md](docs/requirements.md) | How it works; what it must do |
| [measure-your-blinds.md](docs/measure-your-blinds.md) | Measuring other blinds |
| [pcb-v3-concept.md](docs/pcb-v3-concept.md) | The next PCB (on hold) |
| [app-store.md](docs/app-store.md) | App Store answers and how firmware is published |
| [docs/adr](docs/adr) | Decisions on record |

## What is in here
| Folder | What |
|---|---|
| [app/Tilt](app/README.md) | The iPhone app (SwiftUI) with its widget and Control Center buttons |
| [firmware/blinds_matter](firmware/README.md) | Controller firmware (ESP32-C6, ESP-IDF + esp-matter) |
| [firmware/as5600_setup](firmware/README.md#as5600_setup-sensor-bench-tool) | Bench tool that switches a new AS5600 angle sensor to PWM output |
| [hardware/mechanical](hardware/mechanical/README.md) | Tilter and controller box: Fusion 360 generators and print files; headrail measurements |
| [hardware/pcb](hardware/pcb/README.md) | Controller PCB v2.2 |
| [tools](tools) | Build, check and print helpers (below) |
| [docs](docs) | Guides, notes, reference photos (`docs/reference/`) |

## Tools
| Tool | Does |
|---|---|
| `tools/fusion_tilter.py` | Builds the tilter in Fusion, runs the collision and gear checks, exports STLs |
| `tools/fusion_thin.py` | Thin-wall scan of the built tilter |
| `tools/orient.py`, `tools/bambu.py` | Turn the STLs to print orientation; build the Bambu Studio projects (PLA plate + PETG plate) |
| `tools/fusion_controller.py` | Builds the controller box in Fusion |
| `tools/flash.sh` | Builds the controller firmware and installs it through the Tilt Hub |
| `tools/release_firmware.py` | Builds and signs a public firmware release |
| `tools/blinds_client.py` | Talks to a controller over its secured channel (testing) |
| `tools/pcb_guide.py` | Generates the PCB build guide and its pictures |
| `tools/firmware_tests.sh`, `tools/app_tests.sh`, `tools/test_tools.py` | Tests |

Fusion scripts run through the FusionBridge add-in: `python3 hardware/mechanical/fusion/fusion.py exec tools/<script>.py`.

## License
To be decided before publishing.
