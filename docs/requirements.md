# Requirements

IDs are stable so issues, tests, and commits can reference them. **Must** = v1 release blocker.
**Should** = targeted for v1. **Could** = later / bonus.

## Functional

| ID | Pri | Requirement | Verification |
|---|---|---|---|
| F-1 | Must | Tilt each blind through its **full mechanical range** (fully closed one way → open → fully closed the other way). No 180° limit | Angle sensor covers the measured full range on every test blind |
| F-2 | Must | One controller drives **up to 3 motors** independently | Run 3 motors at the same time on the bench |
| F-3 | Must | Knows blind position from an **absolute angle sensor** (AS5600), so it is correct after power loss and after hand use | Cut power, turn the wand, power up: position is correct |
| F-4 | Must | **Calibration**: per motor, set direction and both end limits; choose which end "Close" goes to (slats down or up) | Done from the setup app |
| F-5 | Must | **Stall / jam detection** stops the motor within 250 ms and never strips the gearbox | Hold the rod by hand; motor stops, no damage |
| F-6 | Must | Motors are **unpowered when idle**; the self-locking worm holds the slats | Idle current per port ≈ 0 mA (driver + sensor asleep) |
| F-7 | Should | Calibration stays valid with no re-homing (absolute sensor) | Drift < 2% after 500 cycles |
| F-8 | Could | **Physical button** on the controller (pairing/reset) | — |
| F-9 | Should | **Groups and scenes** (e.g. "living room blinds") | Through the ecosystem or the app |
| F-10 | Should | **Schedules** (time, sunrise/sunset), stored on the device so they work without the cloud | — |
| F-11 | Could | **Lift**: raise and lower cordless blinds (see [lift-bonus.md](lift-bonus.md)) | — |
| F-12 | Must | **Manual use**: the wand still tilts the blind by hand; the position updates at the next wake | Turn the wand; the app shows the new angle |

## Connectivity & integrations

| ID | Pri | Requirement |
|---|---|---|
| C-1 | Must | **Matter over Thread** (sleepy end device) through the house's Thread border router |
| C-2 | Must | Works with **Amazon Alexa** voice commands ("Alexa, open the bedroom blinds", "...set to 50%") |
| C-3 | Should | Works with **Apple Home / Siri** |
| C-4 | Should | Works with Google Home and Home Assistant (free with Matter) |
| C-5 | Must | **Works locally**: no vendor cloud required for basic control |
| C-6 | Must | **OTA firmware updates** |
| C-7 | Should | Each of the 3 motors shows up as its **own named blind** in Alexa/Home |

## Setup app

| ID | Pri | Requirement |
|---|---|---|
| A-1 | Must | Commissioning a new controller into Apple Home / Alexa (Matter QR code over BLE) |
| A-2 | Must | Name each motor port / blind, enable/disable ports |
| A-3 | Must | Calibration wizard (jog, set limits, test) |
| A-4 | Should | Manual control per blind, status (position, battery level, firmware version) |
| A-5 | Should | Works on iPhone and Android **without App Store distribution** (web app served by the device) |
| A-6 | Could | Native app (Flutter) with discovery of all controllers in the house |

## Mechanical

| ID | Pri | Requirement |
|---|---|---|
| M-1 | Must | Everything except electronics, motors, and screws/fasteners is **3D printable** on a Bambu-class printer |
| M-2 | Must | Motor fits **inside the existing headrail** (inner section ≈ 55.5 × 36 mm, see [cross-section](reference/headrail-cross-section.png)) |
| M-3 | Must | **Reversible install**: no permanent changes to the blinds (no cutting/drilling of the headrail) |
| M-4 | Should | Low drive noise: printed helical gears, grease; TPU isolation only if tests show it's needed |
| M-5 | Should | Parametric CAD so other people (MakerWorld) can adapt it to their headrail size and tilt rod shape |
| M-6 | Must | Prints without supports; assembly with common M3 / M1.6 screws and M3 heat-set inserts |
| M-7 | Must | Controller box fits **inside a headrail**, under the tilt rod |

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
| E-1 | Must | **Cordless**: 18650 cell per controller, ≥ 2 months per charge with no sun; charged from any USB-C charger. No mains on our boards |
| E-2 | Should | Optional small solar panel on the glass keeps the cell charged |
| E-3 | Must | A stalled motor never browns out the ESP32 (one motor runs at a time; stall stop) |
| E-4 | Must | Charging stops when the cell is hot (NTC); solar input clamped; ESD protection on the ports (PCB) |
| E-5 | Should | Motor cables up to 3 m from the controller to each blind |
| E-6 | Must | No exposed pinch points that could catch fingers; child safety for any cords (lift bonus) |

## Distribution

| ID | Pri | Requirement |
|---|---|---|
| D-1 | Should | Published on MakerWorld with 3MF print profiles, assembly guide, and BOM |
| D-2 | Should | PCB orderable as one fabrication + assembly order (JLCPCB-friendly parts) |
| D-3 | Should | Firmware flashable from a browser (ESP Web Tools) so makers do not need a toolchain |
