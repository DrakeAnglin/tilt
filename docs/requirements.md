# Requirements

IDs are stable so issues, tests, and commits can reference them. **Must** = v1 release blocker.
**Should** = targeted for v1. **Could** = later / bonus.

## Functional

| ID | Pri | Requirement | Verification |
|---|---|---|---|
| F-1 | Must | Tilt each blind through its **full mechanical range** (fully closed one way → open → fully closed the other way). No 180° limit | Encoder counts cover measured full range on every test blind |
| F-2 | Must | One controller drives **up to 3 motors** independently | Run 3 motors at the same time on the bench |
| F-3 | Must | Knows blind position via **encoder**, and keeps it across power loss | Cut power mid-session; position is correct after reboot |
| F-4 | Must | **Calibration**: per motor, set direction and both end limits; choose which end "Close" goes to (slats down or up) | Done from the setup app |
| F-5 | Must | **Stall / jam detection** stops the motor within 250 ms and never strips the gearbox | Hold the rod by hand; motor stops, no damage |
| F-6 | Must | Motors are **unpowered when idle** (no holding current) | Idle current per motor ≈ 0 mA |
| F-7 | Should | **Re-homing**: automatically corrects drift by detecting the end stop during normal moves to fully closed | Drift < 2% after 500 cycles |
| F-8 | Should | **Physical button** on the controller: short press = toggle all, long press = pairing/reset | — |
| F-9 | Should | **Groups and scenes** (e.g. "living room blinds") | Through the ecosystem or the app |
| F-10 | Should | **Schedules** (time, sunrise/sunset), stored on the device so they work without the cloud | — |
| F-11 | Could | **Lift**: raise and lower cordless blinds (see [lift-bonus.md](lift-bonus.md)) | — |
| F-12 | Could | Manual override detection: if someone turns the blind by hand, position updates rather than going wrong | — |

## Connectivity & integrations

| ID | Pri | Requirement |
|---|---|---|
| C-1 | Must | Connects over **2.4 GHz Wi-Fi** |
| C-2 | Must | Works with **Amazon Alexa** voice commands ("Alexa, open the bedroom blinds", "...set to 50%") |
| C-3 | Should | Works with **Apple Home / Siri** |
| C-4 | Should | Works with Google Home and Home Assistant (free with Matter) |
| C-5 | Must | **Works locally**: no vendor cloud required for basic control |
| C-6 | Must | **OTA firmware updates** |
| C-7 | Should | Each of the 3 motors shows up as its **own named blind** in Alexa/Home |

## Setup app

| ID | Pri | Requirement |
|---|---|---|
| A-1 | Must | Wi-Fi provisioning for a new device |
| A-2 | Must | Name each motor port / blind, enable/disable ports |
| A-3 | Must | Calibration wizard (jog, set limits, test) |
| A-4 | Should | Manual control slider per blind, status (position, firmware version, Wi-Fi signal) |
| A-5 | Should | Works on iPhone and Android **without App Store distribution** (web app served by the device) |
| A-6 | Could | Native app (Flutter) with discovery of all controllers in the house |

## Mechanical

| ID | Pri | Requirement |
|---|---|---|
| M-1 | Must | Everything except electronics, motors, and screws/fasteners is **3D printable** on a Bambu-class printer |
| M-2 | Must | Motor fits **inside the existing headrail** (inner section ≈ 55.5 × 36 mm, see [cross-section](reference/headrail-cross-section.png)) |
| M-3 | Must | **Reversible install**: no permanent changes to the blinds (no cutting/drilling of the headrail) |
| M-4 | Must | Motor is **vibration-isolated** from the headrail and the printed frame (TPU decoupling) |
| M-5 | Should | Parametric CAD so other people (MakerWorld) can adapt it to their headrail size and tilt rod shape |
| M-6 | Should | Prints without supports where possible; assembly with common M2/M3 hardware |
| M-7 | Should | Controller enclosure small enough to hide on top of the headrail or window frame |

## Performance

| ID | Pri | Requirement | Target |
|---|---|---|---|
| P-1 | Must | **Quiet** | < 35 dBA at 1 m during a move (fridge level); measure with a phone SPL app vs. the old servo setup |
| P-2 | Must | **Strong enough for the largest blind** | Motor *rated* torque ≥ 2× measured worst-case torque (see [measure-your-blinds.md](measure-your-blinds.md)) |
| P-3 | Should | Full tilt travel time (11–12 worm turns ≈ 13 motor turns) | 3–10 s (300 RPM N20 ≈ 2.5–4 s) |
| P-4 | Must | Positioning repeatability | ±2% of travel |
| P-5 | Should | Lifetime | 10 years at 6 moves/day ≈ 22,000 cycles |

## Power & safety

| ID | Pri | Requirement |
|---|---|---|
| E-1 | Must | Powered from a **standard wall outlet** through an off-the-shelf certified adapter. No mains voltage on our PCB |
| E-2 | Must | Single supply voltage (5 V USB-C) for logic and motors |
| E-3 | Must | Survives all 3 motors stalling at once without browning out the ESP32 |
| E-4 | Must | Protection against reverse polarity / ESD on motor connectors |
| E-5 | Should | Motor cables up to 3 m from the controller to each blind |
| E-6 | Must | No exposed pinch points that could catch fingers; child safety for any cords (lift bonus) |

## Distribution

| ID | Pri | Requirement |
|---|---|---|
| D-1 | Should | Published on MakerWorld with 3MF print profiles, assembly guide, and BOM |
| D-2 | Should | PCB orderable as one fabrication + assembly order (JLCPCB-friendly parts) |
| D-3 | Should | Firmware flashable from a browser (ESP Web Tools) so makers do not need a toolchain |
