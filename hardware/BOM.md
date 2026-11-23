# Bill of materials

Parts for the current design: **tilter v0.9**, **controller PCB v2.2** with the **Adafruit 6092** charger, and the
**controller box** (`Controller.py`). Each table gives what one unit uses and a buy quantity for the owner's build of
**8 blinds on 3 controllers** (3 + 3 + 2), with spares. Older parts lists are in the Git history.

Links are the parts the owner bought. Any part with the same size and rating works.

## One tilter (×8)

### Printed
Every printed part, the plastic and how each sits on the bed: [tilter build](mechanical/stl/tilter/README.md).
White PLA for the housing and most gears, white PETG for the four parts that rub on PLA all the time.

### Electronics
| Part | Per tilter | Buy | Link |
|---|---|---|---|
| N20 gear motor, 6 V 300 RPM, metal gearbox, 3 mm D-shaft, no encoder (3-pack) | 1 | 3 packs (9) | [B0F83X6C77](https://www.amazon.com/dp/B0F83X6C77) |
| AS5600 magnetic angle sensor board, with its Ø4 × 2 mm magnet (5-pack) | 1 | 2 packs (10) | [B097QNG1CN](https://www.amazon.com/dp/B097QNG1CN) |
| DRV8833 dual motor driver board, Suuoo (10-pack) | 1 | 1 pack (10) | [B0GX9F695H](https://www.amazon.com/dp/B0GX9F695H) |
| RJ11/RJ12 6P6C breakout board, risingsaplings (4-pack) | 1 | 2 packs (8) + 1 spare pack | [B0B9BHX7T3](https://www.amazon.com/dp/B0B9BHX7T3) |
| Ceramic capacitor 10 µF ("106") | 1 | from the kit below | |
| 30 AWG silicone stranded wire, 6 colors | about 40 cm | 1 kit | [B07G2SWB19](https://www.amazon.com/dp/B07G2SWB19) |
| 22 AWG stranded wire, red and black | about 12 cm | 1 small roll each | search "22 AWG silicone wire red black" |
| White flat 2-conductor 22 AWG (motor leads) | about 8 cm | 1 roll (30 ft) | [B0DRTS9P8N](https://www.amazon.com/dp/B0DRTS9P8N) |

### Hardware
| Part | Per tilter | Buy | Link |
|---|---|---|---|
| M3 × 25 flat-head screw | 3 (2 case, 1 sensor) | 50 | [B0DKY4B3VG](https://www.amazon.com/dp/B0DKY4B3VG) |
| M3 × 20 flat-head screw | 2 (tray; one is the cluster gear's axle) | from the M3 kit below | |
| M3 × 8 flat-head screw | 1 (lid corner) | from the M3 kit below | |
| M3 heat-set insert, M3 × 5.7 × 4.6 (Ø4.0 hole) | 6 | 100 (for tilters and boxes) | [B0DQL4ZSCP](https://www.amazon.com/dp/B0DQL4ZSCP) |
| M1.6 × 4 socket screw (holds the N20 to the motor shell) | 2 | 1 kit | [B0DK9TQVT4](https://www.amazon.com/dp/B0DK9TQVT4) |
| Ø2 × 6 mm stainless dowel pin (4 planet axles, 1 worm top pin) | 5 | 50 | [HARFINGTON 2 × 6 mm](https://www.amazon.com/s?k=HARFINGTON+50pcs+Dowel+Pins+M2+2mm+x+6mm+304+Stainless+Steel) |
| PTFE grease, Super Lube 21030 | a little | 1 tube | [B000XBH9HI](https://www.amazon.com/dp/B000XBH9HI) |

### Cord to the controller
| Part | Per tilter | Buy | Link |
|---|---|---|---|
| RJ12 cord, **white, straight-wired**, 10 ft (2-pack) | 1, far blinds | 2 packs | [B0C1VK4W51](https://www.amazon.com/dp/B0C1VK4W51) |
| RJ12 cord, **white, straight-wired**, 6.6 ft (2-pack) | 1, near blinds | 2 packs | [B0C1VJN3DL](https://www.amazon.com/dp/B0C1VJN3DL) |

Check every cord before use: pin 1 must beep to pin 1 ([tilter wiring](../docs/tilter-wiring.md)).

## One controller (×3)

### Boards and battery
| Part | Per controller | Buy | Link |
|---|---|---|---|
| Controller PCB v2.2 ([order it](pcb/README.md#ordering)) | 1 | 5 (the minimum order) | PCBWay |
| ESP32-C6 SuperMini (5-pack) | 1 | 1 pack | [B0GD19KJ4B](https://www.amazon.com/dp/B0GD19KJ4B) |
| Adafruit 6092 charger (bq25185, USB-C) | 1 | 3 | [adafruit.com/product/6092](https://www.adafruit.com/product/6092) |
| 18650 2600 mAh **protected** cell with a JST-XH lead, XINLANTECH | 1 | 3 + 1 spare | [B0CHY872T5](https://www.amazon.com/dp/B0CHY872T5) |

### Parts on the PCB
References match the [PCB build guide](../docs/pcb-build.md).

| Part | Exact part (or equivalent) | Per board | Buy |
|---|---|---|---|
| RJ12 PCB jack | Amphenol **87180-066LF** | 3 (J9–J11) | 10 |
| Resettable fuse 0.75 A, radial, 5.1 mm pitch | Bel Fuse **0ZRE0075FF1A** | 3 (F1–F3) | 10 |
| Electrolytic 470 µF, 10 V or more, 8 mm, 3.5 mm pitch | Panasonic EEU-FR1A471 | 1 (C9) | 4 |
| Zener 6.2 V 3 W | onsemi **1N5920BRLG** | 1 (D4) | 5 |
| Schottky diode | **1N5819** | 3 (D1–D3) | 1 pack ([B0FC2CWKPL](https://www.amazon.com/dp/B0FC2CWKPL)) |
| JST-XH header, 2-pin, vertical | **B2B-XH-A(LF)(SN)** | 1 (J4, battery) | 5 |
| JST-XH header, 6-pin, vertical | **B6B-XH-A(LF)(SN)** | 1 (J5, charger) | 4 |
| JST-XH 6-pin housing | **XHP-6** | 1 | 4 |
| Pre-crimped JST-XH leads, 6", crimp both ends (cut in half = 2 leads) | **ASXHSXH22K152** | 2 (4 half leads: 2 splice, GND, PWR) | 10 |
| JST-ZH header, 2-pin, vertical (solar, optional) | **B2B-ZR(LF)(SN)** | 1 (J8) | 4 |
| Female header socket, 10-way | Sullins **PPTC101LFBN-RC** | 2 (J1, J2: ESP) | 6 |
| Resistors, 1/4 W metal film | 1 MΩ ×4, 1 kΩ ×3, 220 Ω ×6, 10 Ω ×3, 100 kΩ ×3 | 19 | 1 kit ([B072BL2VX1](https://www.amazon.com/dp/B072BL2VX1)) |
| Ceramic capacitors | 100 nF ×5, 10 µF ×1 | 6 | 1 kit ([B0C1V8Q93P](https://www.amazon.com/dp/B0C1V8Q93P)) |
| 22 AWG stranded wire | about 5 cm (charger BAT lead) | | the red roll above |

J3 (a 6-way socket for a separate USB-C board) is not used: USB plugs into the 6092's own USB-C.

### Box
| Part | Per box | Buy | Link |
|---|---|---|---|
| Printed tray, lid (white PLA) | 1 each | | [controller box](../docs/controller-box.md) |
| M3 heat-set insert | 3 | from the tilter's 100 | |
| M3 × 10 flat-head screw | 3 | from the M3 kit below | |
| M2 × 6 self-tapping screw (charger) | 2 | 1 small pack | search "M2 x 6 self tapping screw" |
| **Stick-on pad, about 8 mm across and 1.5 to 2 mm tall: felt, rubber or a clear silicone bumper** | **4** | 1 pack (they come 50 to 200 to a sheet) | search "felt pads 8 mm" or "clear rubber bumper feet 8 mm" |

The pads lift the box off the rail floor so it does not pinch the blind's lift cord, which runs down the middle of the
rail: one pad in each corner, none in the middle. Where they go:
[controller box, step 8](../docs/controller-box.md#assembly).

### Solar (optional)
Solar is on hold: v3 gets a DC jack instead ([#8](https://github.com/DrakeAnglin/tilt/issues/8)). The v2 board takes a
panel on J8.

| Part | Per controller | Buy | Link |
|---|---|---|---|
| 6 V 0.8 W mono ETFE solar panel, 70 × 69 mm (3-pack) | 1 | 1 pack | [B0H1LQFFPN](https://www.amazon.com/dp/B0H1LQFFPN) |
| JST-ZH 1.5 mm 2-pin plugs (20 + 20) | 1 | 1 pack | [B0D9SMKFNS](https://www.amazon.com/dp/B0D9SMKFNS) |

## Tilt Hub (×1)
| Part | Per hub | Buy | Link |
|---|---|---|---|
| Printed box (white) | 1 | | [hub box](../docs/hub-box.md) |
| ESP32-C6 SuperMini, **no pins soldered** | 1 | from the controllers' 5-pack | [B0GD19KJ4B](https://www.amazon.com/dp/B0GD19KJ4B) |
| USB-C male-to-male adapter | 1 | 1 | [B0HFHVN7B6](https://www.amazon.com/dp/B0HFHVN7B6) |

## Shared supplies
| Part | Buy | Link |
|---|---|---|
| M3 countersunk screw kit, 4–20 mm (M3 × 8, × 10, × 20) | 1 | [B0DZCFNKHZ](https://www.amazon.com/dp/B0DZCFNKHZ) |
| Heat-shrink kit | 1 | [B01MFA3OFA](https://www.amazon.com/dp/B01MFA3OFA) |
| White PLA and white PETG filament | 1 spool each | |

## Tools
Soldering iron (also presses the heat-set inserts), multimeter with beep mode, flush cutters, a USB-C cable to flash
the ESP. Handy: a USB-C power meter ([B0DF2LDKFC](https://www.amazon.com/dp/B0DF2LDKFC)) for charge and motor current.

## Check on arrival
- **AS5600:** switch it to PWM output once with the bench tool before it goes in a tilter
  ([firmware/README.md](../firmware/README.md#as5600_setup-sensor-bench-tool)).
- **DRV8833:** the sleep jumper (J1, between "en" and "sleep"; J2 on some batches) must be open
  ([tilter wiring, step 1](../docs/tilter-wiring.md#1-prepare-the-boards-before-any-wiring)).
- **ESP32-C6 SuperMini:** check the pin order against the board. Flash it on the bench before it goes in the box.
- **18650:** the plug's red wire must read **+3.0 to +4.2 V** on the meter. A minus sign means it is wired backwards.
- **RJ12 cords:** pin 1 to pin 1 on every cord ("straight-wired" is used loosely in listings).
- **Solar panel (if used):** check its polarity with the meter in sun before crimping its plug.
