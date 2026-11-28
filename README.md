# Tilt

Most smart blinds need one device per blind. Tilt uses **one controller for up to three blinds**, and each blind
still has its own name in Apple Home and Alexa, its own Schedule and its own tilt.

- **One blind:** 1 tilter + 1 controller + 1 Tilt Hub.
- **Up to three blinds:** more tilters on the same controller.
- **More blinds:** another controller for each three. Still one Tilt Hub for the whole home.

Tilt is open-source, 3D-printable motorized **tilt** for cordless horizontal blinds. Each blind gets a printed tilter
in its headrail; the wand still works by hand. A battery-powered controller drives up to 3 blinds. Control is from the
**Tilt** iPhone app, **Apple Home** and **Alexa**, through a **Tilt Hub**: the controllers talk Thread to the hub and
sleep, and the hub is the Matter device for every blind. No cloud, no account.

Only the current version of each thing is kept here. Older versions are in the Git history.

## Start here
- **Build one:** [docs/build-guide.md](docs/build-guide.md): one blind start to finish, then more blinds.
- **What to buy:** [hardware/BOM.md](hardware/BOM.md), with how many of each for your number of blinds.
- **How it works:** [docs/architecture.md](docs/architecture.md). Words used everywhere: [CONTEXT.md](CONTEXT.md).
- **What to do next:** [GitHub issues](https://github.com/DrakeAnglin/tilt/issues). There are no to-do files.

## Build one
| Page | What |
|---|---|
| [build-guide.md](docs/build-guide.md) | The whole build, in order |
| [hardware/BOM.md](hardware/BOM.md) | Parts to buy, and how many |
| [measure-your-blinds.md](docs/measure-your-blinds.md) | Measuring blinds that differ from the reference blinds |
| [Tilter](hardware/mechanical/stl/tilter/README.md), [sensor module](docs/tilter-wiring.md), [mechanical build](docs/tilter-assembly.md) | Printing, wiring and assembling a tilter |
| [pcb-build.md](docs/pcb-build.md), [controller-box.md](docs/controller-box.md) | Soldering the controller PCB; the box |
| [hub-box.md](docs/hub-box.md) | The Tilt Hub's box |
| [firmware/README.md](firmware/README.md), [Tilt Hub](firmware/tilt_hub/README.md) | Flashing and updates |

## Work on Tilt
For people working on Tilt itself. You do not need any of this to build one.

| Page | What |
|---|---|
| [architecture.md](docs/architecture.md), [requirements.md](docs/requirements.md) | How it works; what it must do |
| [CONTEXT.md](CONTEXT.md) | The words used everywhere |
| [docs/adr](docs/adr) | Decisions on record |
| [docs/developer](docs/developer/README.md) | App Store notes, firmware releases, security hardening, the agent workflow |
| [pcb-v3-concept.md](docs/pcb-v3-concept.md) | The next PCB (design proposal) |

### What is in here
| Folder | What |
|---|---|
| [app/Tilt](app/README.md) | The iPhone app (SwiftUI) with its widget and Control Center buttons |
| [firmware/blinds_matter](firmware/README.md) | Controller firmware (ESP32-C6, ESP-IDF + esp-matter) |
| [firmware/tilt_hub](firmware/tilt_hub/README.md) | Tilt Hub firmware |
| [firmware/as5600_setup](firmware/README.md#as5600_setup-sensor-bench-tool) | Bench tool that switches a new AS5600 angle sensor to PWM output |
| [hardware/mechanical](hardware/mechanical/README.md) | Tilter and controller box: Fusion 360 generators and print files; headrail measurements |
| [hardware/pcb](hardware/pcb/README.md) | Controller PCB v2.2 |
| [tools](tools) | Build, check and print helpers (below) |
| [docs](docs) | Guides, notes, reference photos (`docs/reference/`) |

### Tools
| Tool | Does |
|---|---|
| `tools/fusion_tilter.py` | Builds the tilter in Fusion, runs the collision and gear checks, exports STLs |
| `tools/fusion_thin.py` | Thin-wall scan of the built tilter |
| `tools/orient.py`, `tools/bambu.py` | Turn the STLs to print orientation; build the Bambu Studio projects (PLA plate + PETG plate) |
| `tools/fusion_controller.py` | Builds the controller box in Fusion |
| `tools/flash.sh` | Builds the controller firmware and installs it through the Tilt Hub |
| `tools/flash_hub.sh` | Builds the Tilt Hub firmware and installs it over Wi-Fi; `--usb <port>` for its first flash |
| `tools/device_identity.py` | A first USB flash (`flash_hub.sh --usb`, `flash.sh --usb`): a hub's Apple Home code and setup code, made on the Mac, saved in `~/.tilt/devices/`, and its setup label (`labels` prints one again) |
| `tools/release_firmware.py` | Builds and signs a public firmware release (a version tag runs it in GitHub Actions: `docs/developer/firmware-release.md`) |
| `tools/blinds_client.py` | Talks to a controller over its secured channel (testing) |
| `tools/pcb_guide.py` | Generates the PCB build guide and its pictures |
| `tools/check_docs.py` | Checks the docs: links, anchors, and no leftovers from one house |
| `tools/firmware_tests.sh`, `tools/app_tests.sh`, `tools/test_tools.py` | Tests |
| `tools/host_cjson.py` | Finds the real cJSON (ESP-IDF's copy, else the system's) for the Tilt Hub's Mac tests |
| `tools/coverage.sh`, `tools/coverage_gate.py` | Line coverage of the tests, and the gate every pull request must pass (below) |

Fusion scripts run through the FusionBridge add-in: `python3 hardware/mechanical/fusion/fusion.py exec tools/<script>.py`.

### Coverage
<!-- coverage:start -->
[![CI](https://github.com/DrakeAnglin/tilt/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DrakeAnglin/tilt/actions/workflows/ci.yml?query=branch%3Amain)

| Area | Line coverage |
|---|---|
| Tilt app | at least 23% |
| controller firmware | at least 64% |
| Tilt Hub firmware | at least 17% |
| tools | at least 99% |

Every pull request covers at least 90% of the lines it changes in our own code, and no area may drop under its floor (`tools/coverage-floors.txt`). The live numbers: the `coverage` job of the [latest CI run on main](https://github.com/DrakeAnglin/tilt/actions/workflows/ci.yml?query=branch%3Amain). The rule: [docs/agents/workflow.md](docs/agents/workflow.md#coverage).
<!-- coverage:end -->

## License
- Code (firmware, app, tools, docs): [MIT](LICENSE).
- Hardware (`hardware/`: CAD, printed parts, PCB, BOM): [CC BY-NC-SA 4.0](hardware/LICENSE.md). Build it and share it, but do not sell it.
