# Controller PCB v3: concept (rev 2)

One board that carries everything: the cell, charger, USB-C, solar jack, three tilter ports and a lifter port, and the
ESP32-C6. The case is then just a shell with openings. This is the placement-and-parts proposal for review, before the
schematic and routing.

![layout, to scale](renders/pcb-v3-layout.png)

## Requirements added (2026-11-06)
1. **See each source separately:** the ESP reads the **USB charge current and voltage**, the **solar charge current and
   voltage**, and the **battery's own voltage and current** (charging and discharging), each on its own. V5's PCB can
   only read the battery + rail, which shows the input voltage, not the cell, whenever USB or solar is plugged in.
2. **USB, solar and battery all plugged in at once**, with nothing back-feeding anything and no switching by hand.
3. **No small parts that need the PCB maker to assemble them.** Everything on the board must be hand-solderable:
   through-hole parts, or ready-made modules on header pins (like the ESP and the USB-C board today). The order is a
   bare PCB; no assembly service. This **replaces the chip-level design below** (BQ25185, DW01A/FS8205A, INA3221 chip,
   SMD USB-C, SMD fuses). See [Hand-solder only: what changes](#hand-solder-only-what-changes).

How v3 meets 1 and 2 is under [Power monitoring](#power-monitoring-usb-solar-and-battery-separately), and 3 under
[Hand-solder only](#hand-solder-only-what-changes). The parts table and layout further down are the first (chip-level)
pass and are kept for reference; where they disagree, the hand-solder section wins.

## Hand-solder only: what changes
Every part either goes through holes or is a module that plugs onto header pins. Nothing smaller than a 1206-size
resistor, and preferably not even that.

| Job | Chip-level pass (needs assembly) | **Hand-solder version** |
|---|---|---|
| Charger + power path | BQ25185, WSON-10 2.2 × 2 mm | **A charger module on header pins**, as in V5. The MCP73871 module you have works (power path, USB + solar input) but needs its input clamped at 6.2 V, so it keeps V2.1's 3 W zener. A module that takes the panel's ~7 V directly would drop the zener: to research before drawing the board |
| Cell protection | DW01A + FS8205A, SOT-23 / TSSOP | **Protected 18650 cells** (the protection board is built into the cell, button top). Nothing on the PCB |
| USB-C input | 16-pin SMD receptacle | **The Cermant USB-C breakout on a header** (as on V2.1), its own 5.1 k CC resistors on board |
| Solar input | DC003 barrel jack | same jack: it's through-hole, hand-solderable. Or the V2.1 JST-ZH header |
| Power monitor (USB / solar / battery separately) | INA3221 chip, QFN-16 4 × 4 mm | **An INA3221 3-channel module** (common breakout, about 25 × 20 mm, header pins, I²C), plugged onto the board. Its stock shunts are 0.1 Ω, fine for USB and solar (to 1.6 A); the **battery channel's shunt gets swapped for 0.02 Ω** (a 2512-size resistor, large and easy to hand-solder) so lifter peaks of 3–4 A stay in range |
| Port fuses | SMD 1812 PTCs | **Radial through-hole PTCs**, as on V2.1 (0.75 A × 3), plus a radial 2 A for the lifter. They fold flat, as in V5 |
| Source OR-ing | Schottkys | 1N5819 / 1N5822 through-hole (1N5822 for 3 A) |
| Everything else | — | through-hole resistors, capacitors, RJ12 / RJ45 jacks, ESP on sockets, cell holder (Keystone 1042P is through-hole) |

**What that costs:** the board gets bigger again. The charger module (30.5 × 31.5 mm) and the INA3221 module sit on
the board on headers, so the 121 mm case grows back toward V5's length. The layout and case size get re-done once the
modules are picked. GPIO stays at 18 of 18: the INA3221 module is I²C (2 pins), as in the chip version.

| | V5 (today) | **v3 concept** |
|---|---|---|
| Case | 164.6 × 52.5 × 25.8 mm | **121.0 × 52.8 × 26.4 mm** (44 mm shorter) |
| Inside the case | PCB + charger module + capacitor + USB-C board + cell, wired together | **one board**, four screws |
| Brackets | cell saddles, charger seats, capacitor saddle, USB-C card slot, PCB nest | **none**: four bosses under the board |
| Wiring inside | charger harness, battery lead, USB lead, solar lead | **none** |
| Ports | 3 tilter | 3 tilter + **1 lifter (RJ45)** |

Checked in Fusion with every part as a datasheet-sized block in a minimal case in the rail: **no interference**,
including the tilt rod against the lid. The cell's top sets the height (0.4 mm under the lid). The ESP's pins have
3 mm under the groove.

![board](renders/pcb-v3-board.png)

| | |
|---|---|
| ![end A](renders/pcb-v3-case-end-a.png) | ![end B](renders/pcb-v3-case-end-b.png) |

## What's on the board
| Function | Part | Notes |
|---|---|---|
| Charger | **TI BQ25185** (LCSC C19725033, WSON-10 2.2 × 2) | 3.0–18 V operating input, 25 V tolerant: the 6 V panel (≈7 V open-circuit) plugs straight in, with **no zener**. Power path (the ESP runs while the cell charges), battery-tracking input regulation for the panel, charge-status pin to the ESP. The usual alternatives (BQ24074, MCP73871) shut off at ~6.6 V, under the panel's open-circuit voltage |
| Cell protection | DW01A + FS8205A (JLC basic parts) | so any standard 18650, protected or not, is safe |
| Cell | 18650 in a **Keystone 1042P** holder (77 × 21 × 15 mm, through-hole) | see "Is the 18650 right?" below |
| Temperature | 10 k NTC at the holder → charger TS pin | no charging when the cell is hot (you have these) |
| USB-C | 16-pin SMD receptacle + 5.1 k CC resistors, at the board edge | |
| Solar | **3.5 × 1.35 mm barrel jack, SHOU HAN DC003-1.3** (LCSC C668594, JLC can solder it) | 9 × 6.3 × 5 mm, round 4 mm opening in end wall A. The panel lead gets a 3.5 × 1.35 plug (common) |
| Source OR-ing | 2 Schottkys (USB, solar) | both can stay plugged in with the battery: either charges, neither back-feeds the other |
| **Power monitor** | **TI INA3221** (LCSC C181255, QFN-16 4 × 4), 3 channels on I²C, + 3 shunt resistors | USB in, solar in, battery: current and voltage of each, separately. See below |
| Tilter ports | 3 × RJ12 87180-066LF (yours): 1 at end A, 2 at end B | V5's plug-shaped openings carry over |
| **Lifter port** | **RJ45 8P8C** at end B, its own **2 A** PTC | see below |
| Port fuses | SMD PTCs (1812): 0.75 A × 3, 2 A × 1 | nothing to fold |
| ESP32-C6 SuperMini | **on sockets**, room side, clear of the groove | stays replaceable |

```
USB-C VBUS --[R1 0.1]--|>|--+                     SYS --> ESP 5V pin (its LDO makes 3.3 V)
                            +--> BQ25185 IN ------+
solar 1.35 --[R2 0.1]--|>|--+    (3-18 V)         BAT --+--> 0.75 A PTC x3 --> RJ12 tilters (pin 1)
                                                        +--> 2 A PTC --> RJ45 lifter (2 x VBAT, 2 x GND)
                                                        |
                                                     [R3 0.02] --> DW01A/FS8205A --> 18650
INA3221 (I2C to the ESP): ch1 across R1 = USB, ch2 across R2 = solar, ch3 across R3 = battery (+ charging / - discharging)
NTC --> TS
```

**GPIO:** 4 ports × (IN1, IN2, EN, angle) = 16, plus **I²C (SDA, SCL) to the INA3221** = **18 of the SuperMini's 18 free
pins**. The INA3221 replaces both the battery ADC divider and the CHG pin: it reads the cell's voltage directly, and the
sign of the battery current says charging or not. The 4 angle inputs fit GPIO0–6. If the lifter needs more signals later, its
own small driver/MCU at the lifter can share the same I²C bus over 2 of the RJ45's wires.

## Power monitoring: USB, solar and battery separately
One **TI INA3221** (three-channel current / voltage monitor, I²C, 0–26 V on every channel) with a shunt resistor in each path:

| Channel | Shunt | Where | Reads | Range / resolution |
|---|---|---|---|---|
| 1 USB | 0.1 Ω, 0805 | VBUS, **before** its Schottky | USB charge current + USB voltage | 0–1.6 A, 0.4 mA steps |
| 2 Solar | 0.1 Ω, 0805 | panel +, **before** its Schottky | solar charge current + panel voltage (up to 26 V) | 0–1.6 A, 0.4 mA steps |
| 3 Battery | 0.02 Ω, 1206 | between the charger's BAT node (where the ports tap off) and the cell | **the cell's own voltage**, and its current: + charging, − discharging (motor peaks included) | ±8 A, 2 mA steps |

Each shunt sits in only one path, so the ESP reports **USB in, solar in and battery** as separate numbers (volts, amps,
watts), and from those the charge rate and where it comes from. The battery channel is on the cell side of every load, so
it is the cell's true net current: charging minus whatever the ESP and motors draw. The monitor draws about 0.35 mA, or
can sit in power-down between readings on a sleepy device.

**All three plugged in at once:** the two Schottkys make a diode-OR into the charger's single input, so USB and solar
can both stay connected with the cell, and neither can push current back into the other.
- Whichever source is higher at the moment feeds the charger. A sunny panel (6–7 V) takes over from USB (5 V). In
  shade, when the panel sags below about 5 V, USB takes over. Channels 1 and 2 show that handover live.
- Both together don't add up: it's one or the other at any instant (or a share during the handover). If summing
  both is ever wanted, that needs two chargers, not this one.
- The cell stays on the charger's BAT pin the whole time. The BQ25185's power path runs the ESP from SYS while it charges.
  Unplugging either source, or both, needs no action.
- Option: ideal-diode chips (TI **LM66100**, ~0.08 Ω instead of a Schottky's 0.3–0.45 V drop) in place of the two
  Schottkys, if the lost ~0.4 V on USB matters. Same behavior, slightly cooler.

## The lifter port
Raising slats means lifting the stack, roughly **6–15 W** for small blind motors (about 1 A at 12 V). From a
3.7 V cell that's **3–4 A peaks**, more than an RJ12's thin wires should carry. So the 4th port is an RJ45:
- **pins 1, 2:** battery +. **Pins 3, 6:** GND. Two wires each way, about 2 A on 24 AWG cable, fused at 2 A.
- **pins 4, 5, 7, 8:** IN1, IN2, EN and angle/sensor, the same signals as a tilter. The lifter can have the tilter's
  driver + AS5600 arrangement, or its own driver (and a boost to 12 V if it needs one) at the motor end.

The energy is no problem: 2 lifts a day at 12 W for 15 s is 0.1 Wh against the cell's ~9 Wh. Only the peak current
matters, and a high-drain 18650 handles it (below). If the lifter design ends up needing much more, we revisit it then.
The port and its wiring are reserved now, so no new board is needed.

## Is the 18650 right?
| Option | Capacity | Fits? | Verdict |
|---|---|---|---|
| **18650, high-drain** (e.g. Molicel P28A 2800 mAh / 35 A, Samsung 25R 2500 mAh / 20 A) | 9–10 Wh | yes (this layout) | **recommended**: standard, cheap ($4–6), holders everywhere, easily handles lifter peaks |
| 21700 (4000–5000 mAh, 30–45 A) | 15–18 Wh | +3.5 mm wide, +2.6 mm tall, +4 mm long | worth it only if the ESP has to stay always-on without solar, or the lifter is heavy |
| LiPo pouch | any | flat | no standard size or holder, swells in heat (a sunny window), easy to puncture: no |
| LiFePO4 18650 | ~5 Wh | yes | safest in heat, but 3.2 V makes the N20s weaker (already torque-limited): no |
| AA NiMH ×2–3 | 2.4–3.6 V | — | too low a voltage for the motors: no |

What decides the capacity is the ESP. As a Thread sleepy device it averages roughly 1–2 mA, so a 2800 mAh cell runs
~2–4 months on its own. Always-on (Thread router) is ~30–40 mA, ~3 days, which needs the panel. The motors are a
rounding error. The window's heat matters more than capacity: the NTC stops charging above ~45 °C, and the case should
stay out of direct sun.

## Costs, stock and lead times (checked 2026-11)
| Part | Source | Price | Stock / lead time |
|---|---|---|---|
| BQ25185DLHR | LCSC C19725033 | $1.83 (1), $1.12 (1k) | 2,377 at LCSC; TI: active |
| INA3221AIRGVR | LCSC C181255 | ~$0.83–0.92 (1), ~$0.51 (100) | ~2,000–3,000 at LCSC (2026-11); TI: active |
| Shunts 0.1 Ω 0805 ×2, 0.02 Ω 1206 ×1 | LCSC | cents | stocked |
| DC003-1.3 jack | LCSC C668594 | ~$0.1 | in JLC's assembly library |
| Keystone 1042P holder | DigiKey 36-1042P-ND | ~$5.40 (1), $4.23 (25) | ~7,600 in stock; 14-week factory lead time if that runs out. Alternative: MPD BH-18650-PC or a generic LCSC 18650 holder (JLC can solder those) |
| DW01A, FS8205A, USB-C, R/C | JLC basic parts | cents | stocked |
| SMD PTCs (0.75 A, 2 A) | LCSC | ~$0.2–0.4 | stocked |
| RJ45 8P8C right angle, unshielded | LCSC | ~$0.3–0.6 | stocked |
| RJ12 87180-066LF | you have 10 | — | — |
| 18650 cell (high-drain) | battery shops | $4–6 | — |

## JLC assembly (superseded: requirement 3 says no assembly; kept for reference)
JLC solders through-hole parts too: hand-soldered, $3.50 labor per order plus a small per-joint charge. So the board
can arrive with **everything soldered** (charger, protection, USB-C, solar jack, RJ12s, RJ45, holder, ESP sockets). You
plug in the ESP and the cell. If they don't stock a part (your RJ12s, the Keystone holder), it can be bought through their
global sourcing, or left off for you to solder.

**Estimate for 5 boards** (JLC's published Economic PCBA rates; the real quote comes from uploading the files):

| | |
|---|---|
| PCB, 117 × 48 mm, 2-layer, ×5 | ~$5–8 |
| Assembly setup + stencil | $9.71 |
| Extended-part fees (~5 parts × $3.07) | ~$15 |
| SMD joints (~180 per board × 5 × $0.0016) | ~$1.50 |
| Through-hole labor + joints | ~$9 |
| Parts (~$16/board fully loaded, ~$5 without RJ12s/holder) | ~$25–80 |
| Shipping (DHL) | ~$15–20 |
| **Total** | **~$80–140 for 5** (~$16–28 each), depending on who supplies the RJ12s and holders |

When the board is drawn I'll generate the BOM and placement files and fill in JLC's quote form (stopping before checkout, as with
the PCB) so you see the exact number.

## Decided
- ~~JLC assembly: yes (quote first).~~ **No assembly (2026-11-06):** bare PCB, everything hand-soldered or plugged in.
- **Off-the-shelf modules with mounting points (2026-11-06):** the charger / battery module, the INA3221 monitor and the
  USB-C board are bought ready-made. The PCB just gives each one its mounting points: header holes it plugs into (or
  pads its wires solder to), plus screw holes or standoff points where the module has mounting holes, and a keep-out
  under it. Each module is measured when it arrives and its footprint drawn from the real part.
- Solar: 3.5 × 1.35 mm barrel jack.
- Port split: doesn't matter. 1 + USB-C + solar at end A; 2 + lifter at end B.
- Cells: either. The board protects them; the holder takes both lengths (check the 1042P's length range against the cell you buy).

## Next
1. Your OK on the 18650 recommendation, the lifter port, and the INA3221 power monitor (it takes the two pins that were
   the battery ADC and CHG).
2. Schematic, then a KiCad board generated like v2 (netlist → placement → routing → DRC / ERC / parity), then the
   PCB's 3D export into this same Fusion fit check.
3. Pick the charger module (ideally one that takes the panel's ~7 V with no zener) and the INA3221 module; measure both.
4. Bare PCB order (no assembly). Then the V6 case around the real board.
