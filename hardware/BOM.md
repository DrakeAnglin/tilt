# Bill of materials: 8 blinds, 3 controllers

Current as of **2026-10-29** (design: tilter v0.4 + sensor module, ControllerV4). Quantities cover **8 tilters on 3
controllers** (3 + 3 + 2) plus spares. Everything is from Amazon; prices are what the cart showed that day.

## Already bought
| Item | Qty | Covers | Link | Price |
|---|---|---|---|---|
| N20 gear motor, 6 V 300 RPM, metal gearbox, 3 mm D-shaft, no encoder, 3-pack | 3 packs | 9 motors (8 + 1 spare) | [B0F83X6C77](https://www.amazon.com/dp/B0F83X6C77) | $15.99 / pack |
| AS5600 magnetic angle sensor boards (with Ø4 × 2 diametric magnets), 5-pack | 2 packs | 10 boards | [B097QNG1CN](https://www.amazon.com/dp/B097QNG1CN) | $9.99 / pack |
| Super Lube 21030 PTFE grease | 1 | worm, worm wheel, thrust steps, gears | [B000XBH9HI](https://www.amazon.com/dp/B000XBH9HI) | |
| Ø2 × 6 mm 304 stainless dowel pins, 50 pcs (HARFINGTON) | 1 | worm top bearing, 1 per tilter | [search](https://www.amazon.com/s?k=HARFINGTON+50pcs+Dowel+Pins+M2+2mm+x+6mm+304+Stainless+Steel) | |

## In the cart (2026-10-29)
### Electronics
| Item | Qty | Covers | Link | Price | Arrives |
|---|---|---|---|---|---|
| ESP32-C6 SuperMini, 5-pack | 1 | 3 controllers + 2 spare | [B0GD19KJ4B](https://www.amazon.com/dp/B0GD19KJ4B) | $20.69 | Oct 31 |
| DRV8833 dual motor driver, 10-pack (Suuoo) | 1 | 1 per tilter (8) + 2 spare | [B0GX9F695H](https://www.amazon.com/dp/B0GX9F695H) | $14.88 | Oct 31 |
| MCP73871 USB/solar Li-ion charger, power path (Comimark) | 3 | 1 per controller | [B07V4PHKNX](https://www.amazon.com/dp/B07V4PHKNX) | $8.99 each | Oct 31 |
| 18650 2600 mAh protected cell, JST-XH lead (XINLANTECH) | 4 | 3 + 1 spare | [B0CHY872T5](https://www.amazon.com/dp/B0CHY872T5) | $11.72 each | Oct 31 |
| USB-C female breakout, 5.1 kΩ CC resistors, 21.6 × 12.8 mm, 10-pack (Cermant) | 1 | 1 per controller (charge port) | [B0CB2VFJ54](https://www.amazon.com/dp/B0CB2VFJ54) | $9.99 | Oct 31 |
| RJ11/RJ12 6P6C breakout, 4-pack (risingsaplings) | 5 | 20 jacks: 8 tilters + 9 controller ports = 17 | [B0B9BHX7T3](https://www.amazon.com/dp/B0B9BHX7T3) | $9.99 each | Nov 3 |

### Solar (optional: drop all four rows to save ~$46; the controllers then charge only over USB-C)
| Item | Qty | Covers | Link | Price | Arrives |
|---|---|---|---|---|---|
| 6 V 0.8 W mono ETFE solar panel, 70 × 69 mm, 3-pack | 1 | 1 per controller | [B0H1LQFFPN](https://www.amazon.com/dp/B0H1LQFFPN) | $19.90 | Nov 4 |
| JST-ZH 1.5 mm 2-pin plugs + sockets, 20 + 20 | 1 | solar extension ends | [B0D9SMKFNS](https://www.amazon.com/dp/B0D9SMKFNS) | $7.99 | Oct 31 |
| White flat 2-conductor 22 AWG, 30 ft | 1 | solar extensions, cut to length | [B0DRTS9P8N](https://www.amazon.com/dp/B0DRTS9P8N) | $9.99 | Oct 31 |
| 1 W zener kit incl. 6.2 V (Chanzon) | 1 | solar over-voltage clamp | [B07BTKVRG8](https://www.amazon.com/dp/B07BTKVRG8) | $7.99 | Oct 31 |

### Cords
| Item | Qty | Covers | Link | Price | Arrives |
|---|---|---|---|---|---|
| RJ12 cord, **white, straight-wired**, 10 ft, 2-pack (LanSenSu) | 2 | 4 cords (far blinds) | [B0C1VK4W51](https://www.amazon.com/dp/B0C1VK4W51) | $7.15 each | Oct 31 |
| RJ12 cord, **white, straight-wired**, 6.6 ft, 2-pack (LanSenSu) | 2 | 4 cords (near blinds) | [B0C1VJN3DL](https://www.amazon.com/dp/B0C1VJN3DL) | $5.98 each | Oct 31 |

### Passives and build supplies
| Item | Qty | Covers | Link | Price | Arrives |
|---|---|---|---|---|---|
| 1N5819 Schottky diodes, 150 pcs (EEEEE) | 1 | 3 per controller (USB in, solar in, ESP 5V) | [B0FC2CWKPL](https://www.amazon.com/dp/B0FC2CWKPL) | $7.99 | Oct 31 |
| Metal-film resistor kit, 525 pcs (ELEGOO) | 1 | 1 k ×3, 1 M ×2, 10 k ×1 per controller | [B072BL2VX1](https://www.amazon.com/dp/B072BL2VX1) | $9.99 | Oct 31 |
| Ceramic capacitor kit, 10 pF–10 µF (ALLECIN) | 1 | 100 nF filters, 10 µF at each ESP and each DRV8833 | [B0C1V8Q93P](https://www.amazon.com/dp/B0C1V8Q93P) | $9.99 | Oct 31 |
| 10 kΩ NTC thermistors, 10 pcs | 1 | 1 per cell (charger THERM: no charging when hot) | [B0F3X2G4D2](https://www.amazon.com/dp/B0F3X2G4D2) | $7.99 | Oct 31 |
| Double-sided perfboard kit + headers (ALLECIN) | 1 | the 3 controller dev boards | [B0CKZ7GFSK](https://www.amazon.com/dp/B0CKZ7GFSK) | $13.99 | Oct 31 |
| 30 AWG silicone stranded wire, 6 colours (TUOFENG) | 1 | point-to-point wiring, tilter leads | [B07G2SWB19](https://www.amazon.com/dp/B07G2SWB19) | $16.29 | Oct 31 |
| **22 AWG stranded silicone wire, red + black (not ordered yet)** | 1 each | power wires in the colour code: charger +/−, RJ12 battery + / GND (or band the white 22 AWG with red / black heat-shrink) | search "22 AWG silicone wire red black" | | |
| **22 AWG solid tinned copper bus wire, bare (not ordered yet)** | 1 roll | dev-board bridges and rails: ~0.4 m per board | search "22 AWG tinned bus wire solid" | | |
| **JST-XH 2.5 mm connector kit (not ordered yet)**: per controller 3 × 2-pin top-entry headers, 1 × 3-pin right-angle header, 2 × 2-pin + 1 × 3-pin housings, 6 crimp pins (crimper needed) | 1 | battery and charger plug into the dev board ([guide](../docs/dev-board-build.md)) | search "JST XH 2.54 kit right angle" | | |
| Heat-shrink kit, 580 pcs (Ginsco) | 1 | splices | [B01MFA3OFA](https://www.amazon.com/dp/B01MFA3OFA) | $7.99 | Oct 30 |
| USB-C power meter (YEREADW) | 1 | bench: charge and motor current | [B0DF2LDKFC](https://www.amazon.com/dp/B0DF2LDKFC) | $16.97 | Oct 31 |

### Fasteners
| Item | Qty | Covers | Link | Price | Arrives |
|---|---|---|---|---|---|
| M3 × 25 flat head, 50 pcs | 1 | tilter bolts: 3 per tilter (24) | [B0DKY4B3VG](https://www.amazon.com/dp/B0DKY4B3VG) | $6.61 | Oct 31 |
| M3 heat-set inserts M3 × 5.7 × 4.6 (Ø4.0 hole), 100 pcs (Moicstiy) | 1 | 3 per tilter (24) + 4 per controller (12) | [B0DQL4ZSCP](https://www.amazon.com/dp/B0DQL4ZSCP) | $5.99 | Oct 31 |
| M3 countersunk screw kit, 4–20 mm, 500 pcs (Zmbroll) | 1 | controller lids: 4 × M3 × 8 each (12) | [B0DZCFNKHZ](https://www.amazon.com/dp/B0DZCFNKHZ) | $9.98 | Oct 31 |
| M1.6 socket screw kit, 4–12 mm (Kozelo) | 1 | N20 gearbox screw: 1 × M1.6 × 4 per tilter | [B0DK9TQVT4](https://www.amazon.com/dp/B0DK9TQVT4) | $11.59 | Oct 31 |

## Per unit (what each build uses)
**Tilter (×8):** printed worm, worm wheel, pinion, sensor gear, case halves, sensor module; 1 N20, 1 AS5600 (+ its
magnet), 1 DRV8833 + 10 µF, 1 RJ12 breakout, 1 dowel pin, 3 × M3 × 25 + 3 inserts, 1 × M1.6 × 4, grease.
**Controller (×3):** printed tray + lid; 1 ESP32-C6, 1 MCP73871 (+ its bulk capacitor), 1 18650 + NTC, 1 USB-C breakout,
3 RJ12 breakouts trimmed to 15 mm, 3 × 1N5819, 1 × 6.2 V zener, resistors and capacitors per
[controller-v4.md](../docs/controller-v4.md), 4 × M3 × 8 + 4 inserts; optional solar panel + extension lead.

## Before soldering (check on arrival)
- **AS5600:** run at 3.3 V; tie GPO to VCC for the analog output (some boards also need R4 removed).
- **DRV8833:** cut the J2 pad on each board so the ULT (sleep) pin works; confirm the pin order on the silkscreen.
- **ESP32-C6 SuperMini:** confirm the pin order against the board; desolder the RGB LED (GPIO8) and the power LED
  before battery tests; flash it on the bench before it goes in the box (the box's USB-C is charge-only).
- **Charger (Comimark MCP73871):** solder pads only (PWR, BATT, LOAD, THERM); replace its fixed THERM resistor with the NTC.
- **RJ12 cords:** check pin 1 → pin 1 continuity on every cord ("straight-wired" is used loosely in listings).
- **Solar:** measure the panel's open-circuit voltage behind glass; the zener clamps it if it exceeds ~6.8 V.
- **Power meter:** reads charge and motor current; use a multimeter's µA/mA range for sleep current.
- **USB-C breakout (Cermant):** measure the board, the socket's stick-out past the front edge and the two holes
  (position, spacing). The box uses photo-scaled values (`usb_*` in ControllerV4.py); correct them before printing.

## Removed during design (not needed)
JST-PH connector kit, electrolytic capacitor kit, M3 × 18 screws, 5 V boost converter (motors run from the battery;
re-add only if bench tests show too little torque), breadboards and jumper wires (straight to perfboard), silver RJ12
cords, 2 W solar panel (too large), 5-core cable (replaced by RJ12 cords), ESP32-S3 boards and wall supplies (now
cordless), separate 6 × 2.5 mm magnets, M2 standoffs and inserts.
