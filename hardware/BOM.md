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
| Item | Qty | Notes |
|---|---|---|
| Diametric 6 × 2.5 mm NdFeB magnets | 10+ | Best found: "NdFeB Disc Dia. 6x2.5 mm Diametrically Magnetized (50PCS)", ~$21, arrives Nov 3–6 (no faster option found) |
| ESP32-S3 dev board (N8R2 / N8R8) | 3 (+1 spare) | One per controller |
| DRV8833 dual motor driver board | 6 (+spares) | 2 per controller (3 motors each) |
| 5 V 3 A USB-C power supply | 3 | One per controller |
| M1.6 × 4 screws | 16+ | N20 gearbox face, 2 per motor |
| M2 screws: × 16 (24) and × 12 (16) | — | Tilter halves (3 each), sensor halves (2 each). An M2 assortment covers both |
| Plastic-safe grease (PTFE, e.g. Super Lube) | 1 | Worm, worm gear, helical gears |
| 6-core 24–26 AWG cable | ~25 m | One 5-wire run per blind to its controller: motor ±, 3V3, GND, sensor OUT |
| Breadboard + jumper wire kit | 1 | Bench testing |
| M2 × 5 mm brass standoffs (male-female) + M2 × 4 screws | 16 + 16 | AS5600 mounting, 2 per blind |
| M2 heat-set inserts | 16 | Owner already has these |
