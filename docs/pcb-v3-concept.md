# Controller PCB v3: concept (rev 3, hand-solder only)

A design note for the next PCB, on hold. Not needed to build the current version.

> **On hold.** Nothing here is ordered. Two things changed since this was written: the v2 build now uses the
> **Adafruit 6092** charger instead of the MCP73871 module ([PCB build, step 11](pcb-build.md#step-11-the-charger-the-battery-and-solar)),
> and the controller is now **Thread-only**, through a Tilt Hub ([ADR 0003](adr/0003-thread-only-tilt-hub.md)). Solar gets a DC jack
> ([#8](https://github.com/DrakeAnglin/tilt/issues/8)); the battery life is measured first
> ([#6](https://github.com/DrakeAnglin/tilt/issues/6)). The must-test list below still stands. "V5" below means
> the current controller box.

One board that carries everything: the cell, charger, USB-C, solar input, three tilter ports, and the
ESP32-C6. The case is then just a shell with openings. This is the parts proposal for review, before the schematic and
routing.

**Rev 3 (2026-11-06): everything on this board is something you can hand-solder.** The order is a bare PCB with no
assembly service. Every part is through-hole, or a ready-made module that plugs onto header pins or solders on by its
own pins. Rev 2's chip-level parts (a 2 × 2 mm charger chip, protection chips, an SMD USB-C socket, SMD fuses, a QFN
power monitor) are gone; they are listed at the bottom only so the reasons stay on record.

## Requirements
1. **See each source separately:** the ESP reads the **USB charge current and voltage**, the **solar charge current and
   voltage**, and the **battery's own voltage and current** (charging and discharging), each on its own. V5's PCB can
   only read the battery + rail, which shows the input voltage, not the cell, whenever USB or solar is plugged in.
2. **USB, solar and battery all plugged in at once**, with nothing back-feeding anything and no switching by hand.
3. **Everything hand-solderable.** Through-hole parts and off-the-shelf modules only. The PCB gives each module its
   mounting points: header holes (or pads for its wires), screw or standoff holes where the module has mounting holes,
   and a keep-out under it. Each module's footprint is drawn from the real part once it's measured.
4. Three tilter ports, the ESP32-C6 on sockets so it stays replaceable.
5. **No 10 µF per port.** The tilters have no capacitor on the DRV8833, and v3 doesn't add one either: the angle is
   read from PWM timing (not changed by a supply dip), the motor soft-starts, and the 470 µF bulk on the battery stays.
   A capacitor here would sit on the far side of the cord from the driver, so it would do little anyway.

## What's on the board
| Function | Part | How it's mounted | Notes |
|---|---|---|---|
| Charger + power path | **A charger module** | header pins or its own pads, plus its mounting holes | The MCP73871 module you have works: power path (the ESP runs while the cell charges), USB and solar both into one input. It needs its input held at 6.2 V or less, so it keeps V2.1's **3 W zener** (through-hole). A module that takes the panel's ~7 V open-circuit directly would drop the zener: **to research** |
| Cell | 18650 in a **Keystone 1042P** holder (77 × 21 × 15 mm) | through-hole | see "Is the 18650 right?" below |
| Cell protection | **Protected 18650 cells** (protection board built into the cell, button top) | nothing on the PCB | the board itself has no protection chips, so **only protected cells** go in |
| Temperature | 10 k NTC on the cell → the charger module's THERM pads | two wires | as in V5: no charging when the cell is hot |
| USB-C | **The Cermant USB-C breakout** (has its own 5.1 k CC resistors) | on a header, at the board edge | as on V2.1 |
| Solar | **3.5 × 1.35 mm barrel jack, SHOU HAN DC003-1.3** (LCSC C668594) | through-hole | 9 × 6.3 × 5 mm, round 4 mm opening in the end wall. The panel lead gets a 3.5 × 1.35 plug (common). Tracked in [#8](https://github.com/DrakeAnglin/tilt/issues/8) |
| Source OR-ing | **1N5822** Schottky × 2 (3 A) | through-hole | USB and solar into the charger's single input: both can stay plugged in, neither back-feeds the other |
| **Power monitor** | **An INA3221 3-channel module** (common breakout, about 25 × 20 mm, I²C) | header pins | USB in, solar in and battery: current and voltage of each, separately. See below |
| Battery current shunt | **0.025 Ω 3 W through-hole current-sense resistor** (e.g. Vishay LVR03 series) | through-hole | across the INA3221 module's battery channel, so motor peaks stay in range with no rework on the module. See below |
| Tilter ports | 3 × RJ12 87180-066LF (yours) | through-hole | V5's plug-shaped openings carry over |
| Port fuses | **Radial PTCs**: Bel 0ZRE0075FF (0.75 A) × 3 | through-hole | as on V2.1; folded flat over their resistors, as in V5 |
| ESP32-C6 SuperMini | female header sockets | through-hole | stays replaceable |
| Resistors, capacitors | 1/4 W axial resistors, radial / disc capacitors | through-hole | as on V2.1 |

```
USB-C board VBUS --[INA ch1]--|>|--+                         OUT --> ESP 5V pin (its LDO makes 3.3 V)
                                   +--> charger module IN ---+
solar jack + ------[INA ch2]--|>|--+   (zener 6.2 V on IN)   BAT --+--> 0.75 A PTC x3 --> RJ12 tilters (pin 1)
                                                                   |
                                                               [INA ch3] --> protected 18650
INA3221 module (I2C to the ESP): ch1 = USB, ch2 = solar, ch3 = battery (+ charging / - discharging)
NTC on the cell --> charger THERM
```

Where the motor ports tap off (the charger's BAT side or its OUT side) gets settled with the module picked: the motor
current has to stay inside what the module's power path can pass.

**GPIO:** 3 ports × (IN1, IN2, EN, angle) = 12, plus **I²C (SDA, SCL) to the INA3221 module** = **14 of the SuperMini's 18
free pins**. The module replaces V2.1's battery and input-power dividers: it reads the cell's voltage directly, and the
sign of the battery current says charging or not. The 3 angle inputs fit GPIO0–6.

## Power monitoring: USB, solar and battery separately
The INA3221 module measures three paths, each through its own shunt resistor, and reports volts and amps on each over I²C
(0–26 V on every channel):

| Channel | Shunt | Where | Reads | Range / resolution |
|---|---|---|---|---|
| 1 USB | the module's own 0.1 Ω | USB VBUS, **before** its Schottky | USB charge current + USB voltage | 0–1.6 A, 0.4 mA steps |
| 2 Solar | the module's own 0.1 Ω | panel +, **before** its Schottky | solar charge current + panel voltage | 0–1.6 A, 0.4 mA steps |
| 3 Battery | the module's 0.1 Ω **in parallel with the board's 0.025 Ω through-hole shunt** = 0.02 Ω | between the ports' tap and the cell | **the cell's own voltage**, and its current: + charging, − discharging, motor peaks included | ±8 A, 2 mA steps |

- **No rework on the module:** the PCB puts the 0.025 Ω shunt straight across channel 3's two terminals. The module's
  own 0.1 Ω carries a fifth of the current (0.8 A at a 4 A peak, 64 mW: fine), and the firmware is set for 0.02 Ω.
- Each shunt sits in only one path, so the ESP reports **USB in, solar in and battery** as separate numbers (volts, amps,
  watts), and from those the charge rate and where it comes from. The battery channel is on the cell side of every load,
  so it is the cell's true net current: charging minus whatever the ESP and motors draw.
- The monitor draws about 0.35 mA, or can sit in power-down between readings on a sleepy device.
- To check when the module arrives: its shunt value (usually R100 = 0.1 Ω, marked on the part), and that each channel's
  IN+ / IN− are on its pins.

**All three plugged in at once:** the two Schottkys make a diode-OR into the charger's single input, so USB and solar
can both stay connected with the cell, and neither can push current back into the other.
- Whichever source is higher at the moment feeds the charger. A sunny panel (6–7 V, held at 6.2 V by the zener) takes over
  from USB (5 V). In shade, when the panel sags below about 5 V, USB takes over. Channels 1 and 2 show that handover live.
- Both together don't add up: it's one or the other at any instant (or a share during the handover). Summing both would
  take two chargers.
- The cell stays on the charger's BAT side the whole time, and the module's power path runs the ESP while it charges.
  Unplugging either source, or both, needs no action.

## Is the 18650 right?
| Option | Capacity | Fits? | Verdict |
|---|---|---|---|
| **18650, high-drain, protected** (e.g. Molicel P28A 2800 mAh / 35 A, Samsung 25R 2500 mAh / 20 A, with a protection board) | 9–10 Wh | yes | **recommended**: standard, cheap ($5–8 protected), holders everywhere, easily handles motor peaks. Protected cells are ~2–3 mm longer: check the holder's length range |
| 21700 (4000–5000 mAh, 30–45 A) | 15–18 Wh | +3.5 mm wide, +2.6 mm tall, +4 mm long | worth it only if the ESP has to stay always-on without solar, |
| LiPo pouch | any | flat | no standard size or holder, swells in heat (a sunny window), easy to puncture: no |
| LiFePO4 18650 | ~5 Wh | yes | safest in heat, but 3.2 V makes the N20s weaker (already torque-limited): no |
| AA NiMH ×2–3 | 2.4–3.6 V | — | too low a voltage for the motors: no |

What decides the capacity is the ESP. Asleep on Thread, with the regulator and charger standby, it is estimated at
about 7–15 mAh a day ([power budget](architecture.md#power-budget-estimates-not-measured); not measured yet:
[#6](https://github.com/DrakeAnglin/tilt/issues/6)), so one cell runs months on its own (on Wi-Fi it was weeks). The
motors are a rounding error. The window's heat matters more than capacity: the NTC stops charging above ~45 °C, and the case should
stay out of direct sun.

## Size: to be redone
Rev 2's layout (121 × 52.8 × 26.4 mm case, everything as chips) no longer applies: the charger module (30.5 × 31.5 mm
for the MCP73871 one) and the INA3221 module (~25 × 20 mm) sit on the board, so it grows back toward V5's 164.6 mm. The
layout, the Fusion fit check and the case get redone once both modules are picked and measured.

## Costs (rough, checked 2026-11)
| Part | Source | Price |
|---|---|---|
| Bare PCB, 2-layer, × 5 | JLC / PCBWay | ~$5–10 + shipping |
| INA3221 3-channel module | Amazon / AliExpress | ~$3–6 |
| Charger module | to pick | ~$2–8 |
| 0.025 Ω 3 W through-hole shunt | DigiKey / Mouser | ~$1 |
| Keystone 1042P holder | DigiKey 36-1042P-ND | ~$5.40 (1), $4.23 (25) |
| DC003-1.3 jack, 1N5822 × 2, 6.2 V 3 W zener, radial PTCs, RJ45 | LCSC / DigiKey | ~$2 together |
| RJ12 87180-066LF | you have 10 | — |
| Protected 18650 (high-drain) | battery shops | $5–8 |

## Decided
- **No assembly (2026-11-06):** bare PCB; everything hand-soldered or plugged in.
- **Off-the-shelf modules on mounting points (2026-11-06):** the charger module, the INA3221 monitor and the USB-C board
  are bought ready-made; the PCB gives them header holes / pads, mounting holes and a keep-out.
- **Protected cells only:** the board has no protection of its own.
- Solar: 3.5 × 1.35 mm barrel jack.
- Port split: doesn't matter. 1 + USB-C + solar at end A; 2 + 3 at end B.

## Must test on the v2 board before ordering v3
Found on the first v2 board (2026-11-07). **v3 is not ordered until each of these is tested on the real board.**

1. **The ESP browns out on USB power.** With USB in and the ESP in, the charger module's LOAD falls to the battery
   voltage (TP4 4.8 V, TP1 3.5 V; 4.4 V with the ESP out). With a low cell, the ESP gets about 3.0 V on 3V3 and keeps
   resetting. The module's SEL and PROG2 (pads on the back) both read high (1.65 A setting), so the input-current
   limit isn't the cause. Most likely: the module's solar input-voltage control (VPCC) backs off when USB arrives at only
   about 4.7 V after D1 and the harness.
   - **Fix to test:** a 1N5819 from TP4 (PWR) to TP2 (5V), band toward TP2, so the ESP runs straight from USB/solar and
     only falls back to the battery through D3. Check TP3 stays at 3.3 V with the radio transmitting, on USB and on battery.
   - **Check with solar:** the ESP's 5V pin would then see up to the zener clamp (about 6.2 V) minus 0.3 V. Confirm
     that's within the ESP regulator's limit, or pick a lower clamp.
   - **For v3:** build this diode path into the board, or pick a charger module whose LOAD output doesn't drop on a
     5 V input.
2. **The ESP on a low battery.** D3 drops about 0.3 V, so below about 3.8 V on the cell the ESP's 3V3 sags below
   3.3 V. Measure the lowest cell voltage where the radio still runs without resets. v3 may need a lower-drop path, such as
   an ideal-diode module.
3. **Charging from USB is only a trickle.** With the cell at 3.45 V, a USB power meter read 0.05 A (it should be
   about 0.35 A: PROG resistor 282 = 2.8 kΩ). SEL/PROG2 high, THERM 10 kΩ, both fine. A wire across D1 (5.02 V at
   TP4) didn't help: overnight the cell rose only from 3.45 V to 3.57 V. Either the module wants more than 5 V on its
   input (set up for solar), or it's faulty. Test: a known-good module, and the panel at the window in daylight.
4. **Solar behind a window (the real use: keep the cell topped up).** Measure TP4 and the charge current in daylight
   at the window. The charger needs the panel at about 5 V or more; a dark-room test read 1 V. The panel's plug was
   wired backwards once: D2 blocked it, nothing damaged.
5. **The J5 PWR crimp lost contact once** (pushed back in, fixed). Check every crimp is clicked in, and tug-test it.

## Next
1. Pick the charger module: ideally one with power path that takes the panel's ~7 V directly (no zener); otherwise the
   MCP73871 module you have, with the zener. Pick an INA3221 module. Measure both.
2. Your OK on the 18650 recommendation.
3. Schematic, then a KiCad board generated like v2 (netlist → placement → routing → DRC / ERC / parity), then the PCB's 3D
   export into the Fusion fit check, then the V6 case around it.
4. Bare PCB order, **only after every item in "Must test on the v2 board" passes.**

## Rev 2 parts that are out (needed factory assembly)
| Part | Why it was there | Replaced by |
|---|---|---|
| TI BQ25185 charger chip (WSON-10, 2.2 × 2 mm) | took the panel's 7 V directly, power path | a charger module |
| DW01A + FS8205A protection (SOT-23-6, TSSOP-8) | made unprotected cells safe | protected cells |
| 16-pin SMD USB-C receptacle | USB-C on the board edge | the Cermant breakout on a header |
| INA3221 chip (QFN-16, 4 × 4 mm) + SMD shunts | per-source monitoring | the INA3221 module + a through-hole shunt |
| SMD 1812 PTCs | fuses that don't need folding | radial PTCs, folded |
| LM66100 ideal diodes (option) | lower drop than Schottkys | dropped: 1N5822 Schottkys |
