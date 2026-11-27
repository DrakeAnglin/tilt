# Requirements

IDs are stable so issues, tests, and commits can reference them. **Must** = v1 release blocker.
**Should** = targeted for v1. **Could** = later. How the design meets them: [architecture.md](architecture.md).

## Functional

| ID | Pri | Requirement | Verification |
|---|---|---|---|
| F-1 | Must | Tilt each blind through its **full mechanical range** (fully closed one way → open → fully closed the other way). No 180° limit | Angle sensor covers the measured full range on every test blind |
| F-2 | Must | One controller drives **up to 3 blinds**, each on its own | Run 3 motors at the same time on the bench |
| F-3 | Must | Knows blind position from an **absolute angle sensor** (AS5600), so it is correct after power loss and after hand use | Cut power, turn the wand, power up: position is correct |
| F-4 | Must | **Calibration**: per motor, set direction and both end limits; choose which end "Close" goes to (slats down or up) | Done from the setup app |
| F-5 | Must | **Stall / jam detection** stops the motor within 250 ms and never strips the gearbox | Hold the rod by hand; motor stops, no damage |
| F-6 | Must | Motors are **unpowered when idle**; the self-locking worm holds the slats | Idle current per port ≈ 0 mA (driver + sensor asleep) |
| F-7 | Should | Calibration stays valid with no re-homing (absolute sensor) | Drift < 2% after 500 cycles |
| F-8 | Could | **Physical button** on the controller (pairing/reset) | — |
| F-9 | Should | **Groups and scenes** (e.g. "living room blinds") | Through the ecosystem or the app |
| F-10 | Should | **Schedules** (time, sunrise/sunset, or the Light trigger: when it gets dark or light, read from the solar panel), stored on the device so they work without the cloud | — |
| F-12 | Must | **Manual use**: the wand still tilts the blind by hand; the position updates at the next wake | Turn the wand; the app shows the new angle |

## Connectivity & integrations

| ID | Pri | Requirement |
|---|---|---|
| C-1 | Must | Controllers talk **Thread** to a **Tilt Hub** (one per home); the hub is the Matter device on Wi-Fi for every blind ([ADR 0003](adr/0003-thread-only-tilt-hub.md)) |
| C-2 | Must | Works with **Amazon Alexa** voice commands ("Alexa, open the bedroom blinds", "...set to 50%") |
| C-3 | Must | Works with **Apple Home / Siri** |
| C-4 | Should | Works with Google Home and Home Assistant (free with Matter) |
| C-5 | Must | **Works locally**: no vendor cloud, account or server ([ADR 0001](adr/0001-no-cloud-local-first.md)) |
| C-6 | Must | **Firmware updates through the Tilt Hub**, signed, installed from the app |
| C-7 | Should | Each blind shows up as its **own named blind** in Apple Home and Alexa |

## App

| ID | Pri | Requirement |
|---|---|---|
| A-1 | Must | Set up a new controller over Bluetooth; it joins the Tilt Hub (no Wi-Fi password), and its blinds show up in Apple Home through the hub |
| A-2 | Must | Name each motor port / blind, enable/disable ports |
| A-3 | Must | Calibration wizard (jog, set limits, test) |
| A-4 | Should | Manual control per blind, status (tilt, Battery level, firmware version) |
| A-5 | Must | Native iPhone and iPad app (**Tilt**, App Store), finds the controllers through the Tilt Hub |
| A-6 | Should | Share a controller with the people you live with (an Owner lets in Guests) |
| A-7 | Could | Android |

## Mechanical

| ID | Pri | Requirement |
|---|---|---|
| M-1 | Must | Everything except electronics, motors, and screws/fasteners is **3D printable** on a Bambu-class printer |
| M-2 | Must | Motor fits **inside the existing headrail** (inner section ≈ 55.5 × 36 mm, see [cross-section](reference/headrail-cross-section.png)) |
| M-3 | Must | **Reversible install**: no permanent changes to the blinds (no cutting/drilling of the headrail) |
| M-4 | Should | Low drive noise: printed helical gears, grease, foam pads between the tilter and the rail |
| M-5 | Should | Parametric CAD so other people (MakerWorld) can adapt it to their headrail size and tilt rod shape |
| M-6 | Must | Gears and their faces print without supports (the tilter's tray lid needs support under one shelf); assembly with common M3 / M1.6 screws and M3 heat-set inserts |
| M-7 | Must | Controller box fits **inside a headrail**, under the tilt rod |

## Performance

| ID | Pri | Requirement | Target |
|---|---|---|---|
| P-1 | Must | **Quiet** | < 35 dBA at 1 m during a move (fridge level); measure with a phone SPL app vs. the old servo setup |
| P-2 | Must | **Strong enough for the largest blind** | Motor *rated* torque ≥ 2× measured worst-case torque (see [measure-your-blinds.md](measure-your-blinds.md)) |
| P-3 | Should | Full tilt travel time (closed to closed, about 260° of rod) | under 15 s (one motor reduction set: about 19°/s at the rod, so about 14 s) |
| P-4 | Must | Positioning repeatability | ±2% of travel |
| P-5 | Should | Lifetime | 10 years at 6 moves/day ≈ 22,000 cycles |

## Power & safety

| ID | Pri | Requirement |
|---|---|---|
| E-1 | Must | **Cordless**: 18650 cell per controller, charged from any USB-C charger. No wall (AC) power on the boards. Target ≥ 2 months per charge with no sun; measured in [#6](https://github.com/DrakeAnglin/tilt/issues/6) |
| E-2 | Should | Optional small solar panel keeps the cell charged (v3: DC jack, [#8](https://github.com/DrakeAnglin/tilt/issues/8)) |
| E-3 | Must | A stalled motor never browns out the ESP32 (one motor runs at a time; stall stop) |
| E-4 | Must | Solar input clamped; fuse on each port; protected cells only. Charging stops when the cell is hot: open (the v2 board has no probe on the cell) |
| E-5 | Should | Motor cables up to 3 m from the controller to each blind |
| E-6 | Must | No exposed pinch points that could catch fingers; the box must not pinch the blind's lift cord |

## Distribution

| ID | Pri | Requirement |
|---|---|---|
| D-1 | Should | Published on MakerWorld with 3MF print profiles, assembly guide, and BOM |
| D-2 | Should | PCB orderable as one fabrication + assembly order (JLCPCB-friendly parts) |
| D-3 | Should | Firmware flashable from a browser (ESP Web Tools) so makers do not need a toolchain |
