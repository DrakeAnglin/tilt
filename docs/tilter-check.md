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
| [ ] | RJ12 **5** | DRV8833 **EEP** (sleep; NOT ULT) | blue |
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
- [ ] DRV8833 **EEP** to **VCC** (should read megohms on the Ω range).
- [ ] Nothing on DRV8833 **ULT** (that's FAULT, an output).
- [ ] DRV8833 **OUT1** to **GND**, **OUT2** to **GND**.

## 4. A few resistance readings (Ω range)
- [ ] RJ12 **1 to 3** (battery + to GND): climbs to **well over 10 kΩ** as the 10 µF charges. Stuck near 0 = short.
- [ ] RJ12 **5 to 3** (EN to GND): **not near 0**. Anything from a few kΩ up is fine (the unpowered sensor chip).
- [ ] DRV8833 **OUT1 to OUT2** with the motor attached: the motor winding, **roughly 5–40 Ω**. That one is supposed
  to beep.

## 5. The cord
- [ ] Plug end to plug end: **pin 1 beeps to pin 1** (and not to pin 6), for all six pins.
- [ ] Cord plugged into the tilter: RJ12 1 to 3 at the far plug still doesn't beep continuously.

## Controller side (the dev board)
No USB, no battery, no charger, no cord plugged in. Meter on Ω. The RJ12 board's six leads go into the dev board;
probe the **RJ12 breakout's pads** against the holes / ESP pins listed. The battery + connections on their own:
[devboard-hot.png](renders/devboard-hot.png).

**Note:** on the dev board the cell's + reaches RJ12 pin 1 only **through the charger**. With the charger unplugged,
battery + to RJ12 pin 1 reads OL, and that is correct.

### B. Ohms check, in RJ12 pin order (red probe on the RJ12 pin)

**RJ12 pin 1 (battery + lead)**

| # | Other probe | Correct | Reading |
|---|---|---|---|
| 1 | hole **j16** (the battery + rail, column j) | ~0 Ω | |
| 2 | charger LOAD+ header pin (**j20**) | ~0 Ω | |
| 3 | battery header **+** (b19) | OL (only joined through the charger) | |
| 4 | RJ12 pin **2** | OL | |
| 5 | RJ12 pin **3** | OL (**most important**) | |
| 6 | RJ12 pin **4** | OL | |
| 7 | RJ12 pin **5** | OL | |
| 8 | RJ12 pin **6** | OL | |

**RJ12 pin 2 (IN1 lead)**

| # | Other probe | Correct | Reading |
|---|---|---|---|
| 9 | ESP pin **18** | ~0 Ω | |
| 10 | RJ12 pin **3** | OL | |
| 11 | RJ12 pin **4** | OL | |
| 12 | RJ12 pin **5** | OL | |
| 13 | RJ12 pin **6** | OL | |

**RJ12 pin 3 (GND lead)**

| # | Other probe | Correct | Reading |
|---|---|---|---|
| 14 | ESP **GND** | ~0 Ω | |
| 15 | battery header **−** (a19) | ~0 Ω | |
| 16 | RJ12 pin **4** | climbs to OL (the 100 nF charging) | |
| 17 | RJ12 pin **5** | high (no pull-down on the dev board) | |
| 18 | RJ12 pin **6** | OL | |

**RJ12 pin 4 (angle lead)**

| # | Other probe | Correct | Reading |
|---|---|---|---|
| 19 | ESP pin **0** | ~1 kΩ (0.9–1.1 k) | |
| 20 | RJ12 pin **5** | OL | |
| 21 | RJ12 pin **6** | OL | |

**RJ12 pin 5 (EN lead)**

| # | Other probe | Correct | Reading |
|---|---|---|---|
| 22 | ESP pin **1** | ~0 Ω | |
| 23 | RJ12 pin **6** | OL | |

**RJ12 pin 6 (IN2 lead)**

| # | Other probe | Correct | Reading |
|---|---|---|---|
| 24 | ESP pin **19** | ~0 Ω | |

**Battery and ESP**

| # | Other probe | Correct | Reading |
|---|---|---|---|
| 25 | battery header **+** (b19) to charger header BATT+ (**d19**) | ~0 Ω | |
| 26 | battery header **+** (b19) to battery header **−** (a19) | OL | |
| 27 | **ESP 5V** to ESP GND | high, not near 0 | |
| 28 | **ESP 3V3** to ESP GND | high, not near 0 | |

~0 Ω line reading OL = that lead / bridge isn't connected. OL line reading near 0 = a short: don't power up.
Line 19 (~1 kΩ) wrong = the 1 kΩ filter resistor or its bridges.

### D. Polarity, before ANY battery goes on (do not skip)
A battery plugged in backwards destroys the charger in a second. Check every plug against its header **unpowered**:
- [ ] **Battery plug:** hold it against the battery header. The **red** wire lines up with **b19** (+), the **black**
  with **a19** (−). If red lines up with a19, the header is turned the wrong way: desolder it, rotate it 180°,
  resolder, check again. Mark b19 with a red "+".
- [ ] **Battery voltage at the plug:** meter on DC V, red probe on the red wire: **+3.0 to +4.2 V**. A minus sign
  means the plug itself is wired backwards: stop.
- [ ] **Charger harness, each wire:** from the charger pad to the dev-board hole it plugs into, meter on Ω, ~0 Ω:
  BATT+ pad → **d19**, PWR+ pad → **e19**, LOAD+ pad → **j20**, the three GND pads → **a21, a22, a23**.
- [ ] **Charger harness, no swaps:** BATT+ pad to GND pads: OL. LOAD+ pad to GND pads: OL.

### E. Power up in stages
1. **USB only** (no battery, no cord), sketch running. EN off (`x`): RJ12 5 to GND ≈ 0 V. EN on (`e`): ≈ 3.3 V.
   Back to `x`.
2. **Only after section D passes:** plug in the charger harness, then the battery (still no cord): RJ12 pin 1 to GND = battery voltage (it comes
   through the charger); nothing warm; the ESP keeps running.
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
