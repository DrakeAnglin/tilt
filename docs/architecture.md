# System architecture (v0.4: cordless, Matter over Thread)

Decided 2026-10-28 with the owner: **ESP32-C6 SuperMini, Matter over Thread, controller inside a headrail, one 18650
cell charged from USB-C or a small solar panel facing the window.** One controller drives up to 3 blinds.

**Path to hardware:** breakout boards on a breadboard first, then everything soldered onto a perfboard dev board,
then a custom PCB once that works. Everything is modular: every device plugs in, nothing is hard-wired between units.

```
 6 V solar panel ──[6.2 V zener clamp]──┐              (facing the glass)
 USB-C 5 V ─────────────────────────────┤
                                        ▼
            ┌──────────────┐   VBAT 3.0–4.2 V   ┌──────────────────────────────────────────────┐
 10 k NTC ─►│ Li-ion charger│──────────────────►│ ESP32-C6 SuperMini (5V pin; on-board 3.3 V LDO)│
 (on cell)  │ (MCP73871,    │   ▲  18650 cell    │  Matter over Thread, sleepy end device        │
            │  power-path)  │───┘  (protected)   └──┬───────────┬───────────┬────────────┬───────┘
            └──────────────┘                       │ PWM ×6     │ ADC ×3     │ GPIO ×3    │ ADC
                   │ VBAT                           ▼            ▲ (RC)      ▼            ▼
                   └──► 2 × DRV8833 (VM = VBAT, nSLEEP) ─► M1 M2 M3        sensor 3V3   VBAT/2 divider
                                                        │                  (one per blind)
                       RJ12 6P6C per blind ─────────────┘  (M+, M−, GND, angle OUT, 3V3, GND)
```

## Why these choices
- **Thread, not Wi-Fi.** On battery the radio dominates. A Wi-Fi ESP32 in power-save mode averages ~3–6 mA
  (~70–150 mAh/day); an ESP32-C6 as a Thread *sleepy end device* averages well under 1 mA. The owner has a Thread
  border router, and Matter over Thread works with both Apple Home and Alexa.
- **ESP32-C6 SuperMini.** Small (≈ 22.5 × 18 mm), Wi-Fi 6 + Thread + BLE (BLE for commissioning), enough GPIO
  including the 4 ADC inputs needed. **Remove the RGB LED (GPIO8) and the power LED**: a WS2812 draws ~0.5–1 mA
  even when off, which alone would double the power budget. Check whether the board has a diode on its 5V pin
  before feeding VBAT there.
- **AS5600 analog OUT, not I²C.** All AS5600s share one I²C address; three analog inputs avoid a multiplexer. The
  sensors are absolute, so they are **powered only while a motor moves** (3 × 6.5 mA would otherwise drain
  ~470 mAh/day). A wand move while they're off is still read correctly next time.
- **One GPIO per sensor, only the moving blind's sensor on.** The analog OUT is ratiometric to the sensor's
  supply, so a sagging supply reads as angle error. One sensor (~6.5 mA) per GPIO keeps the sag to a few tens of
  mV and constant. If bench tests still show drift, add a P-FET switch.
- **ADC filtering.** RC filter (1 kΩ + 100 nF) at each ADC input: the flat phone cord runs the 20 kHz motor PWM
  next to the angle wire. Sample the angle with the motor coasting for a few ms if noise remains. Set the sensor so
  the tilt range sits mid-scale (no 0/360° wrap, away from the ADC's nonlinear top end).
- **Motors straight from the battery (to confirm on the bench).** The DRV8833 runs from 2.7–10.8 V, so VM = VBAT
  (3.0–4.2 V): the N20 gets ~62 % of its 6 V stall torque with no current cap and runs ~185 RPM. The 5 V boost
  in the cart is limited to 0.3 A, which caps torque when it matters (stiff slats, end of travel). Bench test both
  ways; if battery drive has enough torque the boost is dropped. The DRV8833s sleep (≈ 2 µA) between moves.
- **Charger with power-path (MCP73871).** Takes 5 V from a USB-C breakout or a 5–6 V solar panel, charges the
  cell, and powers the load at the same time.
- **Battery temperature.** A headrail behind blinds in sun can pass 50–60 °C, and Li-ion must not charge above
  ~45 °C. A 10 kΩ NTC taped to each cell goes on the MCP73871's THERM pin (most breakout boards tie it to a fixed
  resistor; replace that) so charging stops when hot.
- **Solar over-voltage.** A "6 V" panel's open-circuit voltage can reach ~7 V cold in full sun; the MCP73871 is
  rated 6 V operating / 7 V absolute. Measure the panel's open-circuit voltage behind glass on arrival; fit a
  6.2 V 1 W zener across the solar input if it exceeds ~6.8 V (fit it anyway on the dev board).

## Power budget (estimates, 3 blinds, ~4 moves each per day)
| Load | mAh / day |
|---|---|
| ESP32-C6, Thread sleepy end device + LDO + charger quiescent (LEDs removed) | ~15–25 |
| Motors: 12 moves × ~3 s × ~250 mA from the cell | ~3–5 |
| AS5600, one at a time, only during moves | < 1 |
| **Total** | **~20–30** |

18650 at 2600 mAh (≈ 2300 usable) → **~2.5–3 months with no sun**. A 6 V 0.8 W panel (70 × 69 mm) behind glass
gives maybe 80–250 mAh on a sunny day (less behind low-E glass), so in a window it should stay charged. Verify on
the bench: USB meter for charge and motor current, a multimeter's µA/mA range for sleep current.

## Pin plan
See [dev-board.md](dev-board.md#pin-plan-header-pins-only-physical-order-to-confirm-against-the-board): header pins
only (the SuperMini's GPIO 21–23 are bottom pads), motors on 18/19, 20/14, 16/17, sensors on ADC 0/1/2 with power
from 4/5/6, battery on 3, driver sleep on 15. The case's USB-C breakout carries D+/D− to GPIO 13/12, and three
1N5819 diodes OR the USB and solar inputs into the charger and protect the ESP's 5V pin.

## Connectors (everything modular)
| Link | Connector |
|---|---|
| Tilter ↔ controller | **RJ12 6P6C** jack on the tilter's plug cover and 3 on the controller; white straight-wired phone cords |
| Solar panel ↔ controller | 2-pin ZH 1.5 mm (comes on the panel's lead); matching socket on the controller |
| Battery ↔ controller | JST-XH 2-pin (comes on the cell) |
| Charging | USB-C on the controller end |

**Motor driver at each tilter** (decided 2026-10-28): every tilter carries its own DRV8833 in the plug pod on its
sensor side, so the phone cord carries battery power and logic instead of the 20 kHz motor PWM. The flat, untwisted
cord no longer couples motor noise into the angle wire, the controller loses both drivers, and a tilter is a
complete unit (motor + driver + sensor + plug). 8 drivers from the 10-pack.

**RJ12 pinout** (cords must be *straight-wired*, pin 1 to pin 1; check continuity on every cord before use):
| Pin | Net | At the tilter |
|---|---|---|
| 1 | VBAT (3.0–4.2 V) | DRV8833 VCC, 10 µF to GND |
| 2 | IN1 (PWM) | DRV8833 IN1 |
| 3 | GND | DRV8833 GND, AS5600 GND |
| 4 | ANGLE | AS5600 OUT (GPO tied to VCC) |
| 5 | EN (3.3 V from an ESP GPIO) | AS5600 VCC **and** DRV8833 ULT (sleep): one line wakes both |
| 6 | IN2 (PWM) | DRV8833 IN2 |

Motor wires: DRV8833 OUT1 / OUT2 → N20 tabs, inside the pod. Each tilter uses one channel of its DRV8833; the other
is spare. A reversed cord would put VBAT on IN2 and EN on ANGLE's neighbour, so the continuity check matters.

- On the tilter: the **drive housing** ([TiltPod.py](../hardware/mechanical/fusion/TiltPod/TiltPod.py)) continues the
  tilter case's cross-section 30 mm past the lid and holds the N20, the AS5600's back, the DRV8833 and the RJ12 jack.
  It touches only the lid (never the sensor board), held by two M3 × 20 case bolts through 4 mm bosses; its end
  cover carries the jack window and fixes with 3 × M3 × 8 into inserts.
- **Colour:** visible parts are white: white cords, white PLA cases. The solar panel's cells are black (a white
  cell can't absorb light), so it sits in a white printed frame with the cells facing the glass; from inside the
  room only the white back shows.

## Still open
- Free length inside the headrail for the controller (case is ~50 × 30 mm in section; length set by the 18650 holder
  plus boards, ~100–110 mm).
- Which rail face looks at the glass (where the solar panel and its lead go).
- Cable lengths to the other two blinds.
- Bench: N20 torque at VBAT vs. 5 V boost; panel open-circuit voltage behind glass. (The sensor kits' Ø4 × 2
  magnets are confirmed fine by the owner.)
