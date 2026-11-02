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

### B. Must beep
| ✓ | From | To |
|---|---|---|
| [ ] | ESP **GPIO 19** | RJ12 **2** (IN1) |
| [ ] | ESP **GPIO 20** | RJ12 **6** (IN2) |
| [ ] | ESP **GPIO 1** | RJ12 **5** (EN) |
| [ ] | ESP **GND** | RJ12 **3** |
| [ ] | battery lead **−** (black) | RJ12 **3** |
| [ ] | battery lead **+** (red) | RJ12 **1** |

### C. Resistances (Ω range)
- [ ] RJ12 **4** (angle) to ESP **GPIO 6**: **≈ 1 kΩ** (the filter resistor).
- [ ] RJ12 **5** (EN) to RJ12 **3** (GND): **≈ 100 kΩ** (the pull-down).
- [ ] ESP **GPIO 6** to GND: no beep (only the 100 nF there: a chirp at most).

### D. Must NOT beep
- [ ] Every pair of the six RJ12 pins, as in the tilter table (5 to 3 reads the 100 kΩ pull-down, not 0).
- [ ] ESP **5V** to **GND**, **3V3** to **GND**, **5V** to **3V3**.
- [ ] Battery **+** to any ESP pin.
- [ ] Neighbouring ESP pins on each side (catches a jumper in the wrong row).

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
