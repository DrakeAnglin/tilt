# Bench wiring check (before first power): tilter and controller

Nothing plugged in: no cord, no battery. Meter in **beep (continuity) mode** unless a line says otherwise. Probe the
**RJ12 breakout's pads** on one side and the board pins on the other. Wiring: [tilter-wiring.md](tilter-wiring.md).

**Reading the beeps:** a **continuous** beep is a connection. A **short chirp that stops** is a capacitor charging up
(the 10 µF, or the AS5600's own capacitors): that's normal, not a short. Treat it as "no beep".

## 1. Look first
- [ ] No solder blobs bridging neighbouring pins on any of the three boards.
- [ ] No bare wire or stray strand touching a neighbouring pad; heat-shrink where it could.
- [ ] DRV8833 **J1** (between "en" and "sleep") is **open**.
- [ ] Nothing soldered to IN3, IN4, OUT3, OUT4, EEP (driver) or SCL, SDA (sensor).

## 2. Every connection is there (must beep)
| ✓ | From | To | Wire |
|---|---|---|---|
| [ ] | RJ12 **1** | DRV8833 **VCC** | red |
| [ ] | RJ12 **3** | DRV8833 **GND** | black |
| [ ] | RJ12 **3** | AS5600 **GND** | black |
| [ ] | RJ12 **2** | DRV8833 **IN1** | green |
| [ ] | RJ12 **6** | DRV8833 **IN2** | yellow |
| [ ] | RJ12 **5** | DRV8833 **ULT** | blue |
| [ ] | RJ12 **5** | AS5600 **VCC** | blue |
| [ ] | RJ12 **4** | AS5600 **OUT** | white |
| [ ] | AS5600 **GPO** | AS5600 **VCC** (so also RJ12 5) | link on the back |
| [ ] | AS5600 **DIR** | AS5600 **GND** (so also RJ12 3) | link on the back |
| [ ] | 10 µF legs | DRV8833 VCC and GND | |

## 3. No shorts between the six RJ12 pins (must NOT beep)
Each pair once. Any continuous beep here is a wiring fault: find it before going on.

| | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|
| **1** battery + | [ ] | [ ] **most important** | [ ] | [ ] | [ ] |
| **2** IN1 | | [ ] | [ ] | [ ] | [ ] |
| **3** GND | | | [ ] | [ ] | [ ] |
| **4** angle | | | | [ ] | [ ] |
| **5** EN | | | | | [ ] |

Also, no beep from:
- [ ] DRV8833 **ULT** to **VCC** (should read megohms on the Ω range).
- [ ] DRV8833 **OUT1** to **GND**, **OUT2** to **GND**.

## 4. A few resistance readings (Ω range)
- [ ] RJ12 **1 to 3** (battery + to GND): climbs to **well over 10 kΩ** as the 10 µF charges. Stuck near 0 = short.
- [ ] RJ12 **5 to 3** (EN to GND): **not near 0**. Anything from a few kΩ up is fine (the unpowered sensor chip).
- [ ] DRV8833 **OUT1 to OUT2** with the motor attached: the motor winding, **roughly 5–40 Ω**. That one is supposed
  to beep.

## 5. The cord
- [ ] Plug end to plug end: **pin 1 beeps to pin 1** (and not to pin 6), for all six pins.
- [ ] Cord plugged into the tilter: RJ12 1 to 3 at the far plug still doesn't beep continuously.

## Controller side (the breadboard rig, [bench-test.md](bench-test.md))
Same rules: no USB, no battery, no cord plugged in; beep mode. Probe the breadboard RJ12 breakout's pins against the
ESP's pins (the SuperMini's pin names are printed next to each pin).

### A. Look first
- [ ] ESP straddles the centre gap; no two ESP pins share a breadboard row.
- [ ] Battery **+ goes only to RJ12 pin 1**. Nothing from the battery goes to the ESP's 5V, 3V3 or BAT pins.
- [ ] ESP GND, battery −, RJ12 pin 3, the 100 kΩ and the 100 nF all reach the **same** GND rail (breadboards often
  split the rail in the middle: check the rail is continuous end to end).

### B. Ohms check (meter on Ω; no USB, no battery, no cord)
Go down the list in order: one RJ12 pin at a time, red probe on that pin. Write down each reading.

**RJ12 pin 1** (red probe here)

| # | Black probe | Correct | Reading |
|---|---|---|---|
| 1 | battery lead **red** | ~0 Ω | |
| 2 | RJ12 pin **2** | OL | |
| 3 | RJ12 pin **3** | OL (**most important**) | |
| 4 | RJ12 pin **4** | OL | |
| 5 | RJ12 pin **5** | OL | |
| 6 | RJ12 pin **6** | OL | |

**RJ12 pin 2** (red probe here)

| # | Black probe | Correct | Reading |
|---|---|---|---|
| 7 | ESP pin **19** | ~0 Ω | |
| 8 | RJ12 pin **3** | OL | |
| 9 | RJ12 pin **4** | OL | |
| 10 | RJ12 pin **5** | OL | |
| 11 | RJ12 pin **6** | OL | |

**RJ12 pin 3** (red probe here)

| # | Black probe | Correct | Reading |
|---|---|---|---|
| 12 | ESP **GND** | ~0 Ω | |
| 13 | battery lead **black** | ~0 Ω | |
| 14 | RJ12 pin **4** | climbs to OL (the 100 nF charging) | |
| 15 | RJ12 pin **5** | ~100 kΩ (the pull-down) | |
| 16 | RJ12 pin **6** | OL | |

**RJ12 pin 4** (red probe here)

| # | Black probe | Correct | Reading |
|---|---|---|---|
| 17 | ESP pin **0** | ~1 kΩ (0.9–1.1 k) | |
| 18 | RJ12 pin **5** | OL | |
| 19 | RJ12 pin **6** | OL | |

**RJ12 pin 5** (red probe here)

| # | Black probe | Correct | Reading |
|---|---|---|---|
| 20 | ESP pin **1** | ~0 Ω | |
| 21 | RJ12 pin **6** | OL | |

**RJ12 pin 6** (red probe here)

| # | Black probe | Correct | Reading |
|---|---|---|---|
| 22 | ESP pin **20** | ~0 Ω | |

**ESP and battery**

| # | Black probe | Correct | Reading |
|---|---|---|---|
| 23 | **ESP 5V** to ESP GND | high, not near 0 | |
| 24 | **ESP 3V3** to ESP GND | high, not near 0 | |
| 25 | **battery red** to ESP 5V | OL | |

~0 Ω reading OL = that wire isn't connected. OL line reading near 0 = a short: don't power up. Resistor lines
wrong = resistor missing, wrong row or wrong value (1 kΩ brown-black-red, 100 kΩ brown-black-yellow).

### E. Power up in stages
1. **USB only** (no battery, no cord), sketch running. EN off (`x`): RJ12 5 to GND ≈ 0 V. EN on (`e`): ≈ 3.3 V.
   Back to `x`.
2. **Add the battery** (still no cord): RJ12 1 to GND = battery voltage; nothing warm; the ESP keeps running.
3. **Unplug the battery, plug in the cord** to both breakouts. Recheck RJ12 1 to 3: no continuous beep (that tests
   the tilter end through the cord).
4. Battery back on, then the tilter's first-power checks below.

## 6. First power (on the bench rig, [bench-test.md](bench-test.md))
With the ESP sketch running, EN off (`x`):
- [ ] DRV8833 VCC to GND = battery voltage (3.0–4.2 V).
- [ ] AS5600 VCC to GND ≈ **0 V**; the battery current is tiny (µA range).

EN on (`e`):
- [ ] AS5600 VCC ≈ **3.1–3.3 V**.
- [ ] Turning the wand by hand changes the angle reading smoothly.
- [ ] Nothing gets warm. If anything does, unplug the battery at once.
