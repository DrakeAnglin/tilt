# Bill of materials: 8 blinds, 3 controllers

Bought on Amazon (Prime, delivery within the week) on 2026-10-25. Quantities cover **8 blinds on 3 controllers**
(3 + 3 + 2 motors) plus spares. Prices are what the cart showed that day.

| # | Item | Why | Qty bought | Covers | Link | Price |
|---|---|---|---|---|---|---|
| 1 | N20 gear motor, 6 V 300 RPM, metal gearbox, 3 mm D-shaft (9.3 mm long), no encoder, 3-pack | Tilter drive (≈1:50, back-drivable through the wand) | 3 packs | 9 motors (8 + 1 spare) | [B0F83X6C77](https://www.amazon.com/dp/B0F83X6C77) | $15.99 / pack |
| 2 | AS5600 magnetic angle sensor boards, 23 × 23 mm, I²C / PWM / analog voltage output, 5-pack | Slat angle sensing (one per blind, analog OUT to the ESP32) | 2 packs | 10 boards | [B097QNG1CN](https://www.amazon.com/dp/B097QNG1CN) | $9.99 / pack |

**AS5600 notes (from buyer reviews):** run them at **3.3 V**; for the analog output tie **GPO to VCC** (some boards
also need resistor R4 removed for PWM/analog). The magnets that come in these kits are often the wrong kind. The
sensor needs a **diametrically** magnetized 6 × 2.5 mm magnet, 0.5–2 mm from the chip.

## Still to add (not in the cart yet)
Controller hardware follows [docs/architecture.md](../docs/architecture.md) (cordless, Matter over Thread).

| Item | Qty | Notes |
|---|---|---|
| ESP32-C6 SuperMini | 3 (+1 spare) | One per controller; Thread + Wi-Fi + BLE |
| DRV8833 dual motor driver board | 6 (+spares) | 2 per controller (3 motors) |
| Li-ion charger board, bq24074 power-path, USB-C + solar input | 3 | e.g. Adafruit 4755-style "USB/DC/Solar" charger; confirm it has USB-C |
| 18650 Li-ion cell, protected, ~3000 mAh | 3 (+1) | One per controller |
| 18650 holder or nickel strip + printed holder | 3 | Printed into the controller case |
| 5 V boost module with EN pin (≥ 1 A) | 3 | Motors only, switched on while moving |
| 6 V 1–2 W solar panel (~80 × 55 mm or smaller) | 3 | Faces the glass |
| P-channel MOSFET (logic-level, SOT-23) + 2 × 1 MΩ resistors | 3 sets | Sensor power switch, battery-voltage divider |
| JST-PH 2.0 mm 5-pin connectors + pre-crimped leads | 8 + 8, spares | One plug per blind (tilter end + controller end) |
| 5-core 26 AWG cable | ~25 m | Controller to each blind |
| M1.6 × 4 screws | 8+ | N20 gearbox face, 1 per motor |
| M3 heat-set inserts (Ø4.0 × 6.7 mm hole) + M3 flat head × 16 / × 18 | 24 + 24 | 3 per tilter |
| Plastic-safe grease: [Super Lube 21030 (PTFE)](https://www.amazon.com/dp/B000XBH9HI) | 1 tube | Worm, worm wheel, thrust steps, helical gears; one tube covers all units |
| Ø2 × 6 mm steel dowel pin: [HARFINGTON 50 pcs, 304 stainless](https://www.amazon.com/s?k=HARFINGTON+50pcs+Dowel+Pins+M2+2mm+x+6mm+304+Stainless+Steel) | 1 per unit | **In the cart 2026-10-28.** Worm top bearing, pressed into the case's dome |
| Breadboard + jumper wire kit | 1 | Bench testing |
| USB power meter (USB-C) | 1 | Measure the real sleep current and charge rate |

Dropped from the earlier plan: ESP32-S3 boards and 5 V wall supplies (now cordless), the separate 6 × 2.5 mm
magnets (the boards' own Ø4 × 2 magnets are used), M2 standoffs and M2 inserts (the AS5600 now bolts through the
case with M3).
