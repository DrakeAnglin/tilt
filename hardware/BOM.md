# Bill of materials

Most smart blinds need one device per blind. Tilt uses **one controller for up to three blinds**, and each blind
still has its own name in Apple Home and Alexa, its own Schedule and its own tilt.

- **One blind:** 1 tilter + 1 controller + 1 Tilt Hub.
- **Up to three blinds:** more tilters on the same controller.
- **More blinds:** another controller for each three. Still one Tilt Hub for the whole home.

Parts for the current design: **tilter v0.9**, **controller PCB v2.2** with the **Adafruit 6092** charger, the
**controller box** (`Controller.py`) and the **Tilt Hub**. Each table gives what one unit uses and how the part is
sold, so you can multiply for your own count. Older parts lists are in the Git history.

Links are the parts used in the reference build. Any part with the same size and rating works.

## How many do I need?
- **Tilters** = blinds.
- **Controllers** = blinds ÷ 3, rounded up. Add one more wherever a blind is farther from a controller than a cord
  reaches (3 m, requirement E-5): controllers are grouped by cord reach, not by room.
- **Tilt Hub** = 1 per home, however many controllers.
- **ESP32-C6 SuperMini** = one per controller, plus one for the hub.

| Blinds | Tilters | Controllers | Tilt Hub | ESP32-C6 |
|---|---|---|---|---|
| 1 | 1 | 1 | 1 | 2 |
| 2 | 2 | 1 | 1 | 2 |
| 3 | 3 | 1 | 1 | 2 |
| 7 | 7 | 3 | 1 | 4 |

Example: 7 blinds = 7 tilters, 3 controllers, 1 hub.

Then add the [Buy once](#buy-once) supplies and the [tools](#tools).

## One tilter

### Printed
Every printed part, the plastic and how each sits on the bed: [tilter build](mechanical/stl/tilter/README.md).
White PLA for the housing and most gears, white PETG for the four parts that rub on PLA all the time.

### Electronics
| Part | Per tilter | Sold as | Link |
|---|---|---|---|
| N20 gear motor, 6 V **150 RPM**, metal gearbox, 3 mm D-shaft, no encoder; see [motor speed](#motor-speed) | 1 | 3-pack | [B0F83X6C77](https://www.amazon.com/dp/B0F83X6C77) |
| AS5600 magnetic angle sensor board, with its Ø4 × 2 mm magnet | 1 | 5-pack | [B097QNG1CN](https://www.amazon.com/dp/B097QNG1CN) |
| DRV8833 dual motor driver board, Suuoo | 1 | 10-pack | [B0GX9F695H](https://www.amazon.com/dp/B0GX9F695H) |
| RJ11/RJ12 6P6C breakout board, risingsaplings | 1 | 4-pack | [B0B9BHX7T3](https://www.amazon.com/dp/B0B9BHX7T3) |
| Ceramic capacitor 10 µF ("106") | 1 | in the controller's capacitor kit | |
| 30 AWG silicone stranded wire, 6 colors | about 40 cm | [Buy once](#buy-once) | |
| 22 AWG stranded wire, red and black | about 12 cm | [Buy once](#buy-once) | |
| White flat 2-conductor 22 AWG (motor leads) | about 8 cm | [Buy once](#buy-once) | |

### Motor speed
150 RPM is the default: quiet, and strong enough for the reference blinds. The tilter gears it down 20:1, so the rod
turns at most 45°/s at 6 V with no load. On the 4 V battery, a blind goes from closed to open in about 6 to 7 s.

The speed is a free choice per blind. Any 6 V N20 with the same shaft fits, and the controller adapts on its own
(it watches the angle, learns how far each blind coasts, and stops on a stall):
- **Heavy or stiff blind** (it stalls or crawls): a slower motor, 100 RPM. More torque, slower.
- **Light blind**, or you want it quicker: 300 RPM. About twice as fast, half the torque, a little louder.

If a faster motor overshoots (the log shows "turn-backs"), raise the stop-early limit:
`/api/set?k=tune.lead10&v=120` (tenths of a degree, 20 to 250; default 80). The motor power per blind
(`speed`, 50 to 100 %) also slows a blind without changing the motor.

### Hardware
| Part | Per tilter | Sold as | Link |
|---|---|---|---|
| M3 × 25 flat-head screw | 3 (2 case, 1 sensor) | pack of 50 | [B0DKY4B3VG](https://www.amazon.com/dp/B0DKY4B3VG) |
| M3 × 20 flat-head screw | 2 (tray; one is the cluster gear's axle) | in the M3 kit ([Buy once](#buy-once)) | |
| M3 × 8 flat-head screw | 1 (lid corner) | in the M3 kit ([Buy once](#buy-once)) | |
| M3 heat-set insert, M3 × 5.7 × 4.6 (Ø4.0 hole) | 6 | pack of 100 (the boxes use them too) | [B0DQL4ZSCP](https://www.amazon.com/dp/B0DQL4ZSCP) |
| M1.6 × 4 socket screw (holds the N20 to the motor shell) | 2 | in the M1.6 kit ([Buy once](#buy-once)) | |
| Ø2 × 6 mm stainless dowel pin (4 planet axles, 1 worm top pin) | 5 | pack of 50 | [HARFINGTON 2 × 6 mm](https://www.amazon.com/s?k=HARFINGTON+50pcs+Dowel+Pins+M2+2mm+x+6mm+304+Stainless+Steel) |
| PTFE grease, Super Lube 21030 | a little | [Buy once](#buy-once) | |
| Stick-on **felt** pad, about 8 mm across and 1.5 to 2 mm tall (the same pack as the box's feet) | 6 (4 under, 1 on each side) | [Buy once](#buy-once) | |

The felt pads keep the tilter off the metal rail, so the rail does not pick up the motor's buzz. Use felt, not
rubber: rubber still passes the vibration on. Where they go: [tilter build, step 9](mechanical/stl/tilter/README.md#assembly).

### Cord to the controller
| Part | Per tilter | Sold as | Link |
|---|---|---|---|
| RJ12 cord, **white, straight-wired**, 10 ft | 1, for a far blind | 2-pack | [B0C1VK4W51](https://www.amazon.com/dp/B0C1VK4W51) |
| RJ12 cord, **white, straight-wired**, 6.6 ft | 1, for a near blind | 2-pack | [B0C1VJN3DL](https://www.amazon.com/dp/B0C1VJN3DL) |

Each tilter needs one cord; pick the length by how far its blind is from the controller. Check every cord before
use: pin 1 must beep to pin 1 ([tilter wiring](../docs/tilter-wiring.md)).

## One controller

### Boards and battery
| Part | Per controller | Sold as | Link |
|---|---|---|---|
| Controller PCB v2.2 ([order it](pcb/README.md#ordering)) | 1 | minimum order 5 | PCBWay |
| ESP32-C6 SuperMini (the hub uses one too) | 1 | 5-pack | [B0GD19KJ4B](https://www.amazon.com/dp/B0GD19KJ4B) |
| Adafruit 6092 charger (bq25185, USB-C) | 1 | each | [adafruit.com/product/6092](https://www.adafruit.com/product/6092) |
| 18650 2600 mAh **protected** cell with a JST-XH lead, XINLANTECH | 1 | each | [B0CHY872T5](https://www.amazon.com/dp/B0CHY872T5) |

### Parts on the PCB
References match the [PCB build guide](../docs/pcb-build.md).

| Part | Exact part (or equivalent) | Per board | Sold as |
|---|---|---|---|
| RJ12 PCB jack | Amphenol **87180-066LF** | 3 (J9–J11) | each |
| Resettable fuse 0.75 A, radial, 5.1 mm pitch | Bel Fuse **0ZRE0075FF1A** | 3 (F1–F3) | each |
| Electrolytic 470 µF, 10 V or more, 8 mm, 3.5 mm pitch | Panasonic EEU-FR1A471 | 1 (C9) | each |
| Zener 6.2 V 3 W | onsemi **1N5920BRLG** | 1 (D4) | each |
| Schottky diode | **1N5819** | 3 (D1–D3) | pack ([B0FC2CWKPL](https://www.amazon.com/dp/B0FC2CWKPL)) |
| JST-XH header, 2-pin, vertical | **B2B-XH-A(LF)(SN)** | 1 (J4, battery) | each |
| JST-XH header, 6-pin, vertical | **B6B-XH-A(LF)(SN)** | 1 (J5, charger) | each |
| JST-XH 6-pin housing | **XHP-6** | 1 | each |
| Pre-crimped JST-XH leads, 6", crimp both ends (cut in half = 2 leads) | **ASXHSXH22K152** | 2 (4 half leads: 2 splice, GND, PWR) | each |
| JST-ZH header, 2-pin, vertical (solar, optional) | **B2B-ZR(LF)(SN)** | 1 (J8) | each |
| Female header socket, 10-way | Sullins **PPTC101LFBN-RC** | 2 (J1, J2: ESP) | each |
| Resistors, 1/4 W metal film | 1 MΩ ×4, 1 kΩ ×3, 220 Ω ×6, 10 Ω ×3, 100 kΩ ×3 | 19 | kit ([B072BL2VX1](https://www.amazon.com/dp/B072BL2VX1)) |
| Ceramic capacitors (the kit also covers each tilter's 10 µF) | 100 nF ×5, 10 µF ×1 | 6 | kit ([B0C1V8Q93P](https://www.amazon.com/dp/B0C1V8Q93P)) |
| 22 AWG stranded wire | about 5 cm (charger BAT lead) | | the red roll ([Buy once](#buy-once)) |

J3 (a 6-way socket for a separate USB-C board) is not used: USB plugs into the 6092's own USB-C.

### Box
| Part | Per box | Sold as | Link |
|---|---|---|---|
| Printed tray, lid (white PLA) | 1 each | | [controller box](../docs/controller-box.md) |
| M3 heat-set insert | 3 | from the tilters' pack of 100 | |
| M3 × 10 flat-head screw | 3 | in the M3 kit ([Buy once](#buy-once)) | |
| M2 × 6 self-tapping screw (charger) | 2 | small pack | search "M2 x 6 self tapping screw" |
| **Stick-on felt pad, about 8 mm across and 1.5 to 2 mm tall** | **4** | [Buy once](#buy-once) | |

The pads lift the box off the rail floor so it does not pinch the blind's lift cord, which runs down the middle of the
rail: one pad in each corner, none in the middle. Where they go:
[controller box, step 8](../docs/controller-box.md#assembly).

### Solar (optional)
Solar is on hold: v3 gets a DC jack instead ([#8](https://github.com/DrakeAnglin/tilt/issues/8)). The v2 board takes a
panel on J8.

| Part | Per controller | Sold as | Link |
|---|---|---|---|
| 6 V 0.8 W mono ETFE solar panel, 70 × 70 mm | 1 to 3, wired in parallel | 3-pack | [B0H1LQFFPN](https://www.amazon.com/dp/B0H1LQFFPN) |
| Solar housing: tray + end cap (3 panels in a row, printed) | 1 | | [docs/solar-housing.md](../docs/solar-housing.md) |
| Double-sided tape, for the housing's ends on the window | about 20 cm | 1 roll | search "clear double sided mounting tape" |
| JST-ZH 1.5 mm 2-pin plugs | 1 | pack of 20 + 20 | [B0D9SMKFNS](https://www.amazon.com/dp/B0D9SMKFNS) |

## One Tilt Hub
Every home needs one. One hub serves every controller, and it stays plugged in.

| Part | Per hub | Sold as | Link |
|---|---|---|---|
| Printed box (white) | 1 | | [hub box](../docs/hub-box.md) |
| ESP32-C6 SuperMini, **no pins soldered** | 1 | from the controllers' 5-pack | [B0GD19KJ4B](https://www.amazon.com/dp/B0GD19KJ4B) |
| USB-C male-to-male adapter | 1 | each | [B0HFHVN7B6](https://www.amazon.com/dp/B0HFHVN7B6) |
| 5 V USB-C wall plug (1 A is plenty) | 1 | each | any |

## Buy once
Shared supplies: one of each covers many blinds. The per-unit amounts say how far a pack goes.

| Part | Uses | Sold as | Link |
|---|---|---|---|
| M3 countersunk screw kit, 4–20 mm | M3 × 20 and M3 × 8 (3 per tilter), M3 × 10 (3 per box) | kit | [B0DZCFNKHZ](https://www.amazon.com/dp/B0DZCFNKHZ) |
| M1.6 × 4 socket screws | 2 per tilter | kit | [B0DK9TQVT4](https://www.amazon.com/dp/B0DK9TQVT4) |
| 30 AWG silicone stranded wire, 6 colors | about 40 cm per tilter | kit | [B07G2SWB19](https://www.amazon.com/dp/B07G2SWB19) |
| 22 AWG stranded wire, red and black | about 12 cm per tilter, 5 cm per controller | small roll each | search "22 AWG silicone wire red black" |
| White flat 2-conductor 22 AWG (motor leads) | about 8 cm per tilter | roll (30 ft) | [B0DRTS9P8N](https://www.amazon.com/dp/B0DRTS9P8N) |
| Heat-shrink kit | a few pieces per tilter and controller | kit | [B01MFA3OFA](https://www.amazon.com/dp/B01MFA3OFA) |
| PTFE grease, Super Lube 21030 | a little per tilter | tube | [B000XBH9HI](https://www.amazon.com/dp/B000XBH9HI) |
| Stick-on felt pad, about 8 mm across and 1.5 to 2 mm tall | 6 per tilter, 4 per box | pack of 100 or more | search "felt pads 8 mm" |
| White PLA and white PETG filament | the tilters, the boxes and the hub box | spool each | |

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
- **N20 motors:** they carry no speed marking. Check one from each pack: put a tape flag on the shaft, run it from
  5 V (a USB supply) and count turns for 10 s, or film it in slow motion. **150 RPM: about 20 turns. 300 RPM: about
  40. 100 RPM: about 14.** Keep the packs apart until checked.
- **In the blind:** each move's line in the controller's log shows its time and °/s. With 150 RPM on battery, a full
  closed-to-open move takes about 6 to 7 s (15 to 19°/s); 300 RPM is about half that. One blind far off the others
  with the same motor points to friction in that blind or its gears.
- **RJ12 cords:** pin 1 to pin 1 on every cord ("straight-wired" is used loosely in listings).
- **Solar panel (if used):** check its polarity with the meter in sun before crimping its plug.
