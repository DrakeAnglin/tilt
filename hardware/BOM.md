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
- **RJ12 cords** = one per tilter: one 3.3 ft per controller (its own blind), then 6.6 ft or 10 ft by distance
  ([cord lengths](#cord-to-the-controller)).
- **Tilt Hub** = 1 per home, however many controllers.
- **ESP32-C6 SuperMini** = one per controller, plus one for the hub.
- **RJ12 jack (87180-066LF) and fuse (0ZRE0075FF1A)** = one of each per controller port you use, so one per tilter.
  A controller with one blind needs one jack and one fuse, not three.

| Blinds | Tilters | Controllers | Tilt Hub | ESP32-C6 |
|---|---|---|---|---|
| 1 | 1 | 1 | 1 | 2 |
| 2 | 2 | 1 | 1 | 2 |
| 3 | 3 | 1 | 1 | 2 |
| 7 | 7 | 3 | 1 | 4 |

Example: 7 blinds = 7 tilters, 3 controllers, 1 hub.

Then add the [Buy once](#buy-once) supplies and the [tools](#tools). These counts hold only what every build needs.
Extras you may choose (solar, a cord through a wall, no crimper) are in [Optional](#optional).

## One tilter

### Printed
Every printed part, the plastic and how each sits on the bed: [tilter build](mechanical/stl/tilter/README.md).
White PLA for the housing and most gears, white PETG for the four parts that rub on PLA all the time.

### Electronics
| Part | Per tilter | Sold as | Link |
|---|---|---|---|
| N20 gear motor, 6 V **150 RPM**, metal gearbox, 3 mm D-shaft, no encoder; see [motor speed](#motor-speed) | 1 | 3-pack | [B0F83XS7PW](https://www.amazon.com/dp/B0F83XS7PW) |
| AS5600 magnetic angle sensor board, with its Ø4 × 2 mm magnet | 1 | 5-pack | [B097QNG1CN](https://www.amazon.com/dp/B097QNG1CN) |
| DRV8833 dual motor driver board, Suuoo | 1 | 10-pack | [B0GX9F695H](https://www.amazon.com/dp/B0GX9F695H) |
| RJ11/RJ12 6P6C breakout board, risingsaplings | 1 | 4-pack | [B0B9BHX7T3](https://www.amazon.com/dp/B0B9BHX7T3) |
| 30 AWG silicone stranded wire, 6 colors | about 40 cm | kit ([Buy once](#buy-once)) | [B07G2SWB19](https://www.amazon.com/dp/B07G2SWB19) |
| 22 AWG stranded wire, red and black | about 12 cm | roll ([Buy once](#buy-once)) | [search](https://www.amazon.com/s?k=22+AWG+silicone+wire+red+black) |
| 2-conductor 22 AWG (motor leads: one red, one black) | about 8 cm | roll ([Buy once](#buy-once)) | [B0DRTS9P8N](https://www.amazon.com/dp/B0DRTS9P8N) |

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
| M3 × 25 flat-head screw | 1 (sensor, through the lid and the AS5600) | pack of 50 | [B0DKY4B3VG](https://www.amazon.com/dp/B0DKY4B3VG) |
| M3 × 20 flat-head screw | 4 (2 case, 2 tray; one tray bolt is the cluster gear's axle). The case bolts can be M3 × 25 instead | in the M3 kit ([Buy once](#buy-once)) | [B0DZCFNKHZ](https://www.amazon.com/dp/B0DZCFNKHZ) |
| M3 × 8 flat-head screw | 1 (lid corner) | in the M3 kit ([Buy once](#buy-once)) | [B0DZCFNKHZ](https://www.amazon.com/dp/B0DZCFNKHZ) |
| M3 heat-set insert, M3 × 5.7 × 4.6 (Ø4.0 hole) | 6 | pack of 100 (the boxes use them too) | [B0DQL4ZSCP](https://www.amazon.com/dp/B0DQL4ZSCP) |
| M1.6 × 4 socket screw (holds the N20 to the motor shell) | 2 | in the M1.6 kit ([Buy once](#buy-once)) | [B0DK9TQVT4](https://www.amazon.com/dp/B0DK9TQVT4) |
| Ø2 × 6 mm stainless dowel pin (4 planet axles, 1 worm top pin) | 5 | pack of 50 | [HARFINGTON 2 × 6 mm](https://www.amazon.com/s?k=HARFINGTON+50pcs+Dowel+Pins+M2+2mm+x+6mm+304+Stainless+Steel) |
| PTFE grease, Super Lube 21030 | a little | tube ([Buy once](#buy-once)) | [B000XBH9HI](https://www.amazon.com/dp/B000XBH9HI) |
| Stick-on **foam** pad, 3/8 in (about 10 mm) across and 2 mm thick (the same set as the box's feet) | 6 (4 under, 1 on each side) | 504-piece set ([Buy once](#buy-once)) | [B0HKVXW9MW](https://www.amazon.com/dp/B0HKVXW9MW) |

The foam pads keep the tilter off the metal rail, so the rail does not pick up the motor's buzz. Use soft foam
pads, not hard rubber: hard rubber passes the vibration on. Where they go: [tilter assembly, step D6](../docs/tilter-assembly.md#d6-foam-pads).

### Cord to the controller
| Part | Per tilter | Sold as | Link |
|---|---|---|---|
| RJ12 6P6C cord, **straight-wired**, 3.3 ft | 1, for the blind beside the controller | 2-pack | [B0C1VHVJTS](https://www.amazon.com/dp/B0C1VHVJTS) |
| RJ12 6P6C cord, **straight-wired**, 6.6 ft | 1, for the 2nd blind | 2-pack | [B0C1VJN3DL](https://www.amazon.com/dp/B0C1VJN3DL) |
| RJ12 6P6C cord, **straight-wired**, 10 ft | 1, for a 3rd blind | 2-pack | [B0C1VK4W51](https://www.amazon.com/dp/B0C1VK4W51) |

Each tilter needs one cord. Measure from the controller to each tilter first, then pick:
- **The blind beside the controller:** 3.3 ft. The controller sits in the same headrail as one of its tilters, so
  every controller needs at least one 3.3 ft cord.
- **The 2nd blind:** 6.6 ft.
- **A 3rd blind:** 10 ft, or 6.6 ft if the controller sits in the middle.

Example: 3 blinds with the controller in the middle = one 3.3 ft + two 6.6 ft. Any color works: the cords sit
hidden in the headrail. White is nicest if you can find it. Check every cord before use: pin 1
must beep to pin 1 ([tilter wiring](../docs/tilter-wiring.md)).

## One controller

### Boards and battery
| Part | Per controller | Sold as | Link |
|---|---|---|---|
| Controller PCB v2.2 ([order it](pcb/README.md#ordering)) | 1 | minimum order 5 | [PCBWay](https://www.pcbway.com/) |
| ESP32-C6 SuperMini (the hub uses one too) | 1 | 5-pack | [B0GD19KJ4B](https://www.amazon.com/dp/B0GD19KJ4B) |
| Adafruit 6092 charger (bq25185, USB-C) | 1 | each | [adafruit.com/product/6092](https://www.adafruit.com/product/6092) |
| 18650 2600 mAh **protected** cell with a JST-XH lead, XINLANTECH | 1 | each | [B0CHY872T5](https://www.amazon.com/dp/B0CHY872T5) |

### Parts on the PCB
References match the [PCB build guide](../docs/pcb-build.md).

| Part | Exact part (or equivalent) | Per board | Sold as | Link |
|---|---|---|---|---|
| RJ12 PCB jack | Amphenol **87180-066LF** | 1 per port you use (J9–J11, up to 3) | each | [DigiKey](https://www.digikey.com/en/products/result?keywords=87180-066LF) |
| Resettable fuse 0.75 A, radial, 5.1 mm pitch | Bel Fuse **0ZRE0075FF1A** | 1 per port you use (F1–F3, up to 3) | each | [DigiKey](https://www.digikey.com/en/products/result?keywords=0ZRE0075FF1A) |
| Electrolytic 470 µF, 10 V or more, 8 mm, 3.5 mm pitch | Panasonic EEU-FR1A471 | 1 (C9) | each | [DigiKey](https://www.digikey.com/en/products/result?keywords=EEU-FR1A471) |
| Zener 6.2 V 3 W | onsemi **1N5920BRLG** | 1 (D4) | each | [DigiKey](https://www.digikey.com/en/products/result?keywords=1N5920BRLG) |
| Schottky diode | **1N5819** | 3 (D1–D3) | pack | [B0FC2CWKPL](https://www.amazon.com/dp/B0FC2CWKPL) |
| JST-XH header, 2-pin, vertical | **B2B-XH-A(LF)(SN)** | 1 (J4, battery) | each | [DigiKey](https://www.digikey.com/en/products/result?keywords=B2B-XH-A%28LF%29%28SN%29) |
| JST-XH header, 6-pin, vertical | **B6B-XH-A(LF)(SN)** | 1 (J5, charger) | each | [DigiKey](https://www.digikey.com/en/products/result?keywords=B6B-XH-A%28LF%29%28SN%29) |
| JST-XH 6-pin housing | **XHP-6** | 1 | each | [DigiKey](https://www.digikey.com/en/products/result?keywords=XHP-6) |
| JST-XH crimp pins, for 22 AWG wire | JST **SXH-001T-P0.6** | 4 (J5 plug: 2 splice, GND, PWR) | bag ([Buy once](#buy-once)) | [DigiKey](https://www.digikey.com/en/products/result?keywords=SXH-001T-P0.6) |
| 2.54 mm female header, 2 × 10 pins: two single-row 10-pin sockets, any brand | for example Sullins **PPTC101LFBN-RC** | 2 (J1, J2: ESP) | each | [DigiKey](https://www.digikey.com/en/products/result?keywords=PPTC101LFBN-RC) |
| Resistors, 1/4 W metal film | 1 MΩ ×4, 1 kΩ ×3, 220 Ω ×6, 10 Ω ×3, 100 kΩ ×3 | 19 | kit ([Buy once](#buy-once)) | [B072BL2VX1](https://www.amazon.com/dp/B072BL2VX1) |
| Ceramic capacitors | 100 nF ×5, 10 µF ×1 | 6 | kit ([Buy once](#buy-once)) | [B0C1V8Q93P](https://www.amazon.com/dp/B0C1V8Q93P) |
| 22 AWG stranded wire | about 30 cm (the J5 harness) | | the red and black rolls ([Buy once](#buy-once)) | [search](https://www.amazon.com/s?k=22+AWG+silicone+wire+red+black) |

### Box
| Part | Per box | Sold as | Link |
|---|---|---|---|
| Printed tray, lid (white PLA) | 1 each | | [controller box](../docs/controller-box.md) |
| M3 heat-set insert | 3 | from the tilters' pack of 100 | [B0DQL4ZSCP](https://www.amazon.com/dp/B0DQL4ZSCP) |
| M3 × 10 flat-head screw | 3 | in the M3 kit ([Buy once](#buy-once)) | [B0DZCFNKHZ](https://www.amazon.com/dp/B0DZCFNKHZ) |
| M2 × 6 screw (charger; it cuts its own thread in the printed post) | 2 | any small pack | [search](https://www.amazon.com/s?k=M2+x+6+screw) |
| **Stick-on foam pad, 3/8 in (about 10 mm) across and 2 mm thick** | **4** | 504-piece set ([Buy once](#buy-once)) | [B0HKVXW9MW](https://www.amazon.com/dp/B0HKVXW9MW) |

The pads lift the box off the rail floor so it does not pinch the blind's lift cord, which runs down the middle of the
rail: one pad in each corner, none in the middle. Where they go:
[controller box, step 8](../docs/controller-box.md#assembly).

## One Tilt Hub
Every home needs one. One hub serves every controller, and it stays plugged in: any 5 V USB plug in the house works
(a phone charger). Need one? See [Optional](#optional).

| Part | Per hub | Sold as | Link |
|---|---|---|---|
| Printed box (white) | 1 | | [hub box](../docs/hub-box.md) |
| ESP32-C6 SuperMini, **no pins soldered** | 1 | from the controllers' 5-pack | [B0GD19KJ4B](https://www.amazon.com/dp/B0GD19KJ4B) |
| USB-C male-to-male adapter | 1 | each | [B0HFHVN7B6](https://www.amazon.com/dp/B0HFHVN7B6) |

## Buy once
Shared kits and supplies: many tilters, controllers and hubs draw from one of each. Buy them once, not per unit. The
per-unit amounts say how far a pack goes.

| Part | Uses | Sold as | Link |
|---|---|---|---|
| M3 countersunk screw kit, 4–20 mm | M3 × 20 and M3 × 8 (5 per tilter), M3 × 10 (3 per box) | kit | [B0DZCFNKHZ](https://www.amazon.com/dp/B0DZCFNKHZ) |
| M1.6 × 4 socket screws | 2 per tilter | kit | [B0DK9TQVT4](https://www.amazon.com/dp/B0DK9TQVT4) |
| 30 AWG silicone stranded wire, 6 colors | about 40 cm per tilter | kit | [B07G2SWB19](https://www.amazon.com/dp/B07G2SWB19) |
| 22 AWG stranded wire, red and black | about 12 cm per tilter, 30 cm per controller | small roll each | [search](https://www.amazon.com/s?k=22+AWG+silicone+wire+red+black) |
| 2-conductor 22 AWG (motor leads: one red, one black) | about 8 cm per tilter | roll (30 ft) | [B0DRTS9P8N](https://www.amazon.com/dp/B0DRTS9P8N) |
| Heat-shrink kit | a few pieces per tilter and controller | kit | [B01MFA3OFA](https://www.amazon.com/dp/B01MFA3OFA) |
| PTFE grease, Super Lube 21030 | a little per tilter | tube | [B000XBH9HI](https://www.amazon.com/dp/B000XBH9HI) |
| Stick-on foam pad, 3/8 in (about 10 mm) across, 2 mm thick, black | 6 per tilter, 4 per box | 504-piece set | [B0HKVXW9MW](https://www.amazon.com/dp/B0HKVXW9MW) |
| Resistor kit, 1/4 W metal film | 19 per controller | kit | [B072BL2VX1](https://www.amazon.com/dp/B072BL2VX1) |
| Ceramic capacitor kit | 6 per controller | kit | [B0C1V8Q93P](https://www.amazon.com/dp/B0C1V8Q93P) |
| JST-XH crimp pins, SXH-001T-P0.6 | 4 per controller | bag | [DigiKey](https://www.digikey.com/en/products/result?keywords=SXH-001T-P0.6) |
| White PLA and white PETG filament | the tilters, the boxes and the hub box | spool each | any brand |

## Optional
Only what you choose. None of it is in the counts above.

### Solar: yes or no
Solar is on hold: v3 gets a DC jack instead ([#8](https://github.com/DrakeAnglin/tilt/issues/8)). With **no** solar, buy
none of this and leave J8 empty. With **yes**, the v2 board takes a panel on J8:

| Part | Per controller | Sold as | Link |
|---|---|---|---|
| JST-ZH header, 2-pin, vertical, JST **B2B-ZR(LF)(SN)** (J8 on the PCB) | 1 | each | [DigiKey](https://www.digikey.com/en/products/result?keywords=B2B-ZR%28LF%29%28SN%29) |
| 6 V 0.8 W mono ETFE solar panel, 70 × 70 mm | 1 to 6, wired in parallel | 3-pack | [B0H1LQFFPN](https://www.amazon.com/dp/B0H1LQFFPN) |
| Solar housing: tray sections + end cap (1 to 6 panels in a row, printed) | 1 | | [docs/solar-housing.md](../docs/solar-housing.md) |
| Double-sided tape, for the housing's ends on the window | about 20 cm | 1 roll | any |
| JST-ZH 1.5 mm 2-pin plugs | 1 | pack of 20 + 20 | [B0D9SMKFNS](https://www.amazon.com/dp/B0D9SMKFNS) |

### A wall plug for the hub
Only if the house has no spare 5 V USB plug for it.

| Part | Per hub | Sold as | Link |
|---|---|---|---|
| 5 V USB-C wall plug (1 A is plenty) | 1 | each | any |

### No JST crimper
Pre-crimped JST-XH leads, 6", crimped both ends, **ASXHSXH22K152**: 2 per controller, cut in half for the 4 J5 plug
wires, in place of the crimp pins and most of the wire ([PCB build, step 11](../docs/pcb-build.md#step-11-the-charger-the-battery-and-solar)).
[DigiKey](https://www.digikey.com/en/products/result?keywords=ASXHSXH22K152).

### A cord through a wall
A 5/8 in hole and one printed [wall plug](../docs/wall-plug.md) on each side (white PLA, about 1.1 g each). Tools: a
drill and a 5/8 in bit.

## Tools
Soldering iron (also presses the heat-set inserts), multimeter with beep mode, flush cutters, wire strippers, a
crimper for JST-XH pins (an open-barrel crimper, any brand, such as an Engineer PA-09 or IWISS SN-28B), a USB-C cable to flash
the ESP. No crimper? See [Optional](#optional).
Handy: a USB-C power meter ([B0DF2LDKFC](https://www.amazon.com/dp/B0DF2LDKFC)) for charge and motor current.

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
