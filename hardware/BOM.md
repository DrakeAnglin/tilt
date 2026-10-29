# Bill of materials: 8 blinds, 3 controllers

Bought on Amazon (Prime, delivery within the week) on 2026-10-25. Quantities cover **8 blinds on 3 controllers**
(3 + 3 + 2 motors) plus spares. Prices are what the cart showed that day.

| # | Item | Why | Qty bought | Covers | Link | Price |
|---|---|---|---|---|---|---|
| 1 | N20 gear motor, 6 V 300 RPM, metal gearbox, 3 mm D-shaft (9.3 mm long), no encoder, 3-pack | Tilter drive (≈1:50, back-drivable through the wand) | 3 packs | 9 motors (8 + 1 spare) | [B0F83X6C77](https://www.amazon.com/dp/B0F83X6C77) | $15.99 / pack |
| 2 | AS5600 magnetic angle sensor boards, 23 × 23 mm, I²C / PWM / analog voltage output, 5-pack | Slat angle sensing (one per blind, analog OUT to the ESP32) | 2 packs | 10 boards | [B097QNG1CN](https://www.amazon.com/dp/B097QNG1CN) | $9.99 / pack |

**AS5600 notes (from buyer reviews):** run them at **3.3 V**; for the analog output tie **GPO to VCC** (some boards
also need resistor R4 removed for PWM/analog). Some kits ship axially magnetized magnets; the owner checked
these kits' Ø4 × 2 magnets and they are fine (diametric).

## In the Amazon cart (validated 2026-10-28, not checked out: 37 items, $389.00)
Controller hardware follows [docs/architecture.md](../docs/architecture.md) (cordless, Matter over Thread). These
parts are for the breadboard and soldered dev-board stages; the custom PCB comes after.

| Item | Qty | Covers | Link | Price |
|---|---|---|---|---|
| ESP32-C6 SuperMini, 5-pack | 1 | 3 controllers + 2 spare | [B0GD19KJ4B](https://www.amazon.com/dp/B0GD19KJ4B) | $20.69 |
| DRV8833 dual motor driver, 10-pack (Suuoo) | 1 | 6 needed | [B0GX9F695H](https://www.amazon.com/dp/B0GX9F695H) | $14.88 |
| MCP73871 USB/DC/Solar Li-ion charger, power path (Comimark) | 3 | 3 controllers | [B07V4PHKNX](https://www.amazon.com/dp/B07V4PHKNX) | $8.99 each |
| 18650 2600 mAh, protected, JST-XH lead (XINLANTECH) | 4 | 3 + 1 spare | [B0CHY872T5](https://www.amazon.com/dp/B0CHY872T5) | $11.72 each |
| 5 V synchronous boost with EN pin, 10-pack (QEBIDUM) | 1 | 3 needed | [B0CPJNTJ96](https://www.amazon.com/dp/B0CPJNTJ96) | $6.99 |
| USB-C female breakout, 5.1 kΩ CC resistors, 10-pack (Teansic) | 1 | 3 needed | [B0GYNCFDDX](https://www.amazon.com/dp/B0GYNCFDDX) | $9.99 |
| 6 V 0.8 W 130 mA mono ETFE solar panel, 70 × 69 mm, ZH 1.5 2-pin lead (4"), 3-pack | 1 | 3 controllers | [B0H1LQFFPN](https://www.amazon.com/dp/B0H1LQFFPN) | $19.90 |
| ZH 1.5 mm 2-pin leads, 20 plug + 20 socket, 200 mm | 1 | solar extension ends + controller socket | [B0D9SMKFNS](https://www.amazon.com/dp/B0D9SMKFNS) | $7.99 |
| **White** flat 2-conductor 22 AWG, 30 ft | 1 | solar extensions, cut to length | [B0DRTS9P8N](https://www.amazon.com/dp/B0DRTS9P8N) | $9.99 |
| RJ12 6P6C cord, **white, straight-wired**, 10 ft, 2-pack (LanSenSu) | 2 | 4 cords | [B0C1VK4W51](https://www.amazon.com/dp/B0C1VK4W51) | $7.15 each |
| RJ12 6P6C cord, **white, straight-wired**, 6.6 ft, 2-pack (LanSenSu) | 2 | 4 cords | [B0C1VJN3DL](https://www.amazon.com/dp/B0C1VJN3DL) | $5.98 each |
| RJ11/RJ12 6P6C breakout board, 2.54 mm pins, 4-pack (risingsaplings) | 5 | 20 jacks (17 needed) | [B0B9BHX7T3](https://www.amazon.com/dp/B0B9BHX7T3) | $9.99 each |
| JST-PH 2.0 connector kit, 2–9 pin housings + headers, pre-crimped leads (EGSCST) | 1 | internal leads, battery adapter | [B0H3WF134X](https://www.amazon.com/dp/B0H3WF134X) | $16.99 |
| ruthex M3 heat-set inserts RX-M3x5.7 (Ø4.0 hole), 100 pcs | 1 | 24 needed | [B08BCRZZS3](https://www.amazon.com/dp/B08BCRZZS3) | $9.99 |
| M3 countersunk socket screws, 4–20 mm, 500 pcs (Zmbroll; has M3 × 16) | 1 | 8 × M3×16 | [B0DZCFNKHZ](https://www.amazon.com/dp/B0DZCFNKHZ) | $9.98 |
| M3 × 18 countersunk socket screws, 50 pcs (HirtuOtter) | 1 | 16 needed | [B0DKY7NFVH](https://www.amazon.com/dp/B0DKY7NFVH) | $6.24 |
| M1.6 socket screw kit, 4–12 mm, 250 pcs (Kozelo) | 1 | 8 × M1.6×4 | [B0DK9TQVT4](https://www.amazon.com/dp/B0DK9TQVT4) | $11.59 |
| Metal-film resistor kit, 525 pcs incl. 1 MΩ (ELEGOO) | 1 | battery divider | [B072BL2VX1](https://www.amazon.com/dp/B072BL2VX1) | $9.99 |
| Breadboards 4 × 830 + 400 + jumper wires (BOJACK) | 1 | bench | [B08Y59P6D1](https://www.amazon.com/dp/B08Y59P6D1) | $9.99 |
| Dupont jumper wires M-F/M-M/F-F, 120 pcs (ELEGOO) | 1 | bench | [B01EV70C78](https://www.amazon.com/dp/B01EV70C78) | $6.98 |
| USB-C / USB-A power meter (YEREADW) | 1 | charge current, motor current | [B0DF2LDKFC](https://www.amazon.com/dp/B0DF2LDKFC) | $16.97 |
| Ceramic capacitor kit, 24 values 10 pF–10 µF (ALLECIN) | 1 | 100 nF ADC/divider filters, decoupling | [B0C1V8Q93P](https://www.amazon.com/dp/B0C1V8Q93P) | $9.99 |
| Electrolytic capacitor kit, 24 values 0.1–1000 µF (ALLECIN) | 1 | 10–100 µF bulk at ESP32 and DRV8833 | [B0C1VBXCQM](https://www.amazon.com/dp/B0C1VBXCQM) | $9.99 |
| 10 kΩ NTC thermistor, B3950 class, 100 mm leads, 10 pcs | 1 | 1 per cell on the charger's THERM pin | [B0F3X2G4D2](https://www.amazon.com/dp/B0F3X2G4D2) | $7.99 |
| 1 W zener diode kit, 3–47 V incl. 6.2 V (1N4735A), 300 pcs (Chanzon) | 1 | solar input clamp | [B07BTKVRG8](https://www.amazon.com/dp/B07BTKVRG8) | $7.99 |
| Double-sided perfboard kit, 6 sizes, male/female headers, screw terminals (ALLECIN) | 1 | soldered dev boards (modules in female headers) | [B0CKZ7GFSK](https://www.amazon.com/dp/B0CKZ7GFSK) | $13.99 |
| Heat-shrink tubing kit, 2:1, 580 pcs, 6 colours incl. white (Ginsco) | 1 | solar extension splices | [B01MFA3OFA](https://www.amazon.com/dp/B01MFA3OFA) | $7.99 |

Removed from the cart: Sunnytech 2 W panel (too large) and the BTF 5-wire cable (replaced by RJ12 cords).

**Added 2026-10-28:** [1N5819 Schottky diodes, 150 pcs (EEEEE) B0FC2CWKPL](https://www.amazon.com/dp/B0FC2CWKPL),
$7.99: 3 per controller (USB in, solar in, ESP 5V); the charger has one PWR input.
**Still to add:** 30 AWG stranded hookup wire (silicone, 6 colours) for the point-to-point wiring under the board.

**Wiring notes** (full list in [docs/dev-board.md](../docs/dev-board.md))
- **Solar extension:** the panel's lead is only 4". Make one white extension per controller: ZH socket + white 22/2
  cable cut to length + ZH plug, soldered and heat-shrunk.
- **Battery plug:** the cells have JST-XH; Adafruit-style MCP73871 boards usually take JST-PH. Check on arrival;
  if so, make a short XH-to-PH adapter (or solder to the BAT pads on the dev board).
- **Charger:** the Comimark board has solder pads only (PWR, BATT, LOAD, THERM) and a 5-pin header, no USB or DC
  jack. USB-C and solar both feed PWR through diodes.
- **DRV8833:** cut the J2 pad on each board so the ULT pin can put it to sleep.
- **Power meter:** good for charge and motor current; it can't resolve the µA–mA sleep current. Use a multimeter's
  mA/µA range for that.
- **Thermistor:** tape one NTC to each cell and wire it to the MCP73871 THERM pin, replacing the board's fixed
  resistor, so charging stops above ~45 °C (headrails in sun get hot).
- **Zener:** 6.2 V 1 W across the solar input (after measuring the panel's open-circuit voltage behind glass).
- **ESP32-C6 SuperMini:** desolder the RGB LED (GPIO8) and the power LED before battery tests.
- **RJ12 cords:** check pin 1 → pin 1 continuity on every cord before use.

**Boost: bench comparison only.** The plan is now to run the motors straight from the battery (DRV8833 VM = VBAT,
see [architecture](../docs/architecture.md)). The QEBIDUM boost is limited to 0.3 A, which caps torque at stall.
It stays in the cart ($7) to compare torque on the bench; if battery drive is strong enough, it's dropped.

## Already bought (2026-10-28)
- Plastic-safe grease: [Super Lube 21030 (PTFE)](https://www.amazon.com/dp/B000XBH9HI): worm, worm wheel, thrust steps, helical gears.
- Ø2 × 6 mm 304 stainless dowel pins, 50 pcs: [HARFINGTON](https://www.amazon.com/s?k=HARFINGTON+50pcs+Dowel+Pins+M2+2mm+x+6mm+304+Stainless+Steel): worm top bearing.

The 18650 holders are printed into the controller case (the cells come with a JST XH lead). Sensors are powered
from a GPIO (≈ 20 mA for three), so no MOSFET.

RJ12 6P6C jacks: 17 (8 tilters + 3 ports × 3 controllers), not in the cart; from the owner's breakout stock for
the prototype. Path: breadboard → soldered dev board → custom PCB.

Dropped from the earlier plan: ESP32-S3 boards and 5 V wall supplies (now cordless), the separate 6 × 2.5 mm
magnets (the boards' own Ø4 × 2 magnets are used), M2 standoffs and M2 inserts (the AS5600 now bolts through the
case with M3).
