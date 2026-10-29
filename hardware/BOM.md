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

## In the Amazon cart (2026-10-28, not checked out)
Controller hardware follows [docs/architecture.md](../docs/architecture.md) (cordless, Matter over Thread).

| Item | Qty in cart | Qty needed | Link | Price |
|---|---|---|---|---|
| ESP32-C6 SuperMini, 5-pack | 1 | 3 (+2 spare) | [B0GD19KJ4B](https://www.amazon.com/dp/B0GD19KJ4B) | $20.23 |
| DRV8833 dual motor driver, 10-pack (Suuoo) | 1 | 6 | [B0GX9F695H](https://www.amazon.com/dp/B0GX9F695H) | $14.88 |
| MCP73871 USB/DC/Solar Li-ion charger with power path (Comimark) | 1 → **set to 3** | 3 | [B07V4PHKNX](https://www.amazon.com/dp/B07V4PHKNX) | $8.99 each |
| 18650 2600 mAh, protected, JST XH2.54 lead (XINLANTECH) | 1 → **set to 4** | 3 (+1) | [B0CHY872T5](https://www.amazon.com/dp/B0CHY872T5) | $11.72 each |
| 5 V synchronous boost with EN pin, 10-pack (QEBIDUM) | 1 | 3 | [B0CPJNTJ96](https://www.amazon.com/dp/B0CPJNTJ96) | $6.99 |

**Boost check:** the QEBIDUM board is listed at 0.3 A out. That runs one N20 (~250 mA at 5 V), but not at stall.
Only one motor runs at a time, and firmware stops on stall (angle not changing), so it should be OK. Bench test it
with the USB meter before relying on it; if it browns out, swap for a ≥ 1 A board with EN.

## Still to add (Amazon stopped the session with a human check)
| Item | Qty | Notes |
|---|---|---|
| USB-C breakout (5 V in) | 3 | Feeds the charger's DC input |
| 6 V 1–2 W solar panel (~80 × 55 mm or smaller) | 3 | Faces the glass |
| 2 × 1 MΩ resistors (resistor kit) | 3 sets | Battery-voltage divider. Sensors are powered from a GPIO (≈ 20 mA total), so no MOSFET |
| JST-PH 2.0 mm 5-pin connectors + pre-crimped leads | 8 + 8, spares | One plug per blind (tilter end + controller end) |
| 5-core 26 AWG cable | ~25 m | Controller to each blind |
| M1.6 × 4 screws | 8+ | N20 gearbox face, 1 per motor |
| M3 heat-set inserts (Ø4.0 × 6.7 mm hole) + M3 flat head × 16 / × 18 | 24 + 24 | 3 per tilter |
| Plastic-safe grease: [Super Lube 21030 (PTFE)](https://www.amazon.com/dp/B000XBH9HI) | 1 tube | Worm, worm wheel, thrust steps, helical gears; one tube covers all units |
| Ø2 × 6 mm steel dowel pin: [HARFINGTON 50 pcs, 304 stainless](https://www.amazon.com/s?k=HARFINGTON+50pcs+Dowel+Pins+M2+2mm+x+6mm+304+Stainless+Steel) | 1 per unit | Worm top bearing, pressed into the case's dome. Was in the cart earlier, no longer there |
| Breadboard + jumper wire kit | 1 | Bench testing |
| USB power meter (USB-C) | 1 | Measure the real sleep current and charge rate |
| 18650 holder (printed) | 3 | Printed into the controller case; the cells come with a JST XH lead |

Dropped from the earlier plan: ESP32-S3 boards and 5 V wall supplies (now cordless), the separate 6 × 2.5 mm
magnets (the boards' own Ø4 × 2 magnets are used), M2 standoffs and M2 inserts (the AS5600 now bolts through the
case with M3).
