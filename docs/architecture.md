# System architecture (v0.4: cordless, Matter over Thread)

Decided 2026-10-28 with the owner: **ESP32-C6 SuperMini, Matter over Thread, controller inside a headrail, one 18650
cell charged from USB-C or a small solar panel facing the window.** One controller drives up to 3 blinds.

**Path to hardware:** breakout boards on a breadboard first, then everything soldered onto a perfboard dev board,
then a custom PCB once that works. Everything is modular: every device plugs in, nothing is hard-wired between units.

```
 6 V solar panel ──┐                                   (facing the glass)
 USB-C 5 V ────────┤
                   ▼
            ┌──────────────┐   VBAT 3.0–4.2 V   ┌──────────────────────────────────────────────┐
            │ Li-ion charger│──────────────────►│ ESP32-C6 SuperMini (5V pin; on-board 3.3 V LDO)│
            │ (MCP73871,    │   ▲  18650 cell    │  Matter over Thread, sleepy end device        │
            │  power-path)  │───┘  (protected)   └──┬───────────┬───────────┬────────────┬───────┘
            └──────────────┘                       │ PWM ×6     │ ADC ×3     │ EN lines   │ ADC
                   │ VBAT                           ▼            ▲           ▼            ▼
                   ├──► 5 V boost (EN, motors only)─► 2 × DRV8833 (nSLEEP) ─► M1 M2 M3   VBAT/2 divider
                   └──► (sensor 3V3 from a GPIO) ──► the three AS5600 boards
                                                        │
                       RJ12 6P6C per blind ─────────────┘  (motor +, motor −, 3V3, GND, angle OUT, GND)
```

## Why these choices
- **Thread, not Wi-Fi.** On battery the radio dominates. A Wi-Fi ESP32 in power-save mode averages ~3–6 mA
  (~70–150 mAh/day); an ESP32-C6 as a Thread *sleepy end device* averages well under 1 mA. The owner has a Thread
  border router, and Matter over Thread works with both Apple Home and Alexa.
- **ESP32-C6 SuperMini.** Small (≈ 22.5 × 18 mm), Wi-Fi 6 + Thread + BLE (BLE for commissioning), enough GPIO
  including the 4 ADC inputs needed. The S3 (Wi-Fi only) would cost weeks of battery instead of months.
- **AS5600 analog OUT, not I²C.** All AS5600s share one I²C address; three analog inputs avoid a multiplexer. The
  sensors are absolute, so they are **powered only while a motor moves** (3 × 6.5 mA would otherwise drain
  ~470 mAh/day). A wand move while they're off is still read correctly next time.
- **Motors on a switched 5 V boost.** The N20s are 6 V parts; at 5 V they run ~250 RPM. The boost is enabled only
  while moving, so its idle draw is zero. The DRV8833s sleep (≈ 2 µA) between moves.
- **Charger with power-path (MCP73871).** Takes 5 V from a USB-C breakout or a 5–6 V solar panel, charges the
  cell, and powers the load at the same time.
- **Sensors powered from a GPIO.** Three AS5600s draw ≈ 20 mA together, within one GPIO's drive, so no MOSFET.

## Power budget (estimates, 3 blinds, ~4 moves each per day)
| Load | mAh / day |
|---|---|
| ESP32-C6, Thread sleepy end device + LDO + charger quiescent | ~15–25 |
| Motors: 12 moves × ~3 s × ~250 mA from the cell (5 V boost) | ~3–5 |
| AS5600 ×3, only during moves | < 1 |
| **Total** | **~20–30** |

18650 at ~3000 mAh usable → **~3–4 months with no sun**. A 6 V 0.8 W panel (70 × 69 mm) behind glass gives maybe 80–250 mAh on a
sunny day, so in a window it should stay charged. To verify on the bench with a USB power meter.

## Pin plan (ESP32-C6 SuperMini, to confirm against the board's printed pinout)
| Function | Pins |
|---|---|
| Motor 1 / 2 / 3 (DRV8833 IN1/IN2, 20 kHz PWM) | GPIO18+19, GPIO20+21, GPIO22+23 |
| Angle sensors 1 / 2 / 3 (AS5600 OUT, ADC) | GPIO0, GPIO1, GPIO2 |
| Battery voltage (VBAT/2 divider, 2 × 1 MΩ, ADC) | GPIO3 |
| DRV8833 nSLEEP (both) | GPIO4 |
| 5 V boost EN | GPIO5 |
| Sensor power (GPIO drives the 3V3 line directly) | GPIO6 |
| Charger status (CHG, PGOOD) | GPIO7, GPIO14 |
| Boot button / on-board LED | GPIO9 / GPIO15 (LED: remove or leave off to save power) |

## Connectors (everything modular)
| Link | Connector |
|---|---|
| Tilter ↔ controller | **RJ12 6P6C** jack on the tilter's plug cover and 3 on the controller; white straight-wired phone cords |
| Solar panel ↔ controller | 2-pin ZH 1.5 mm (comes on the panel's lead); matching socket on the controller |
| Battery ↔ controller | JST-XH 2-pin (comes on the cell) |
| Charging | USB-C on the controller end |

**RJ12 pinout** (cords must be *straight-wired*, pin 1 to pin 1; ordinary phone cords are reversed):
1 motor +, 2 motor −, 3 3V3 (sensor), 4 angle OUT, 5 GND, 6 GND.

- On the tilter: a printed cover on the lid holds the RJ12 jack and covers the motor tabs and the AS5600's solder
  joints, so tilter + motor + sensor + plug are one closed unit. Short JST-PH or soldered leads inside the cover.
- **Colour:** visible parts are white: white cords, white PLA cases. The solar panel's cells are black (a white
  cell can't absorb light), so it sits in a white printed frame with the cells facing the glass; from inside the
  room only the white back shows.

## Still open
- Free length inside the headrail for the controller (case is ~50 × 30 mm in section; length set by the 18650 holder
  plus boards, ~100–110 mm).
- Which rail face looks at the glass (where the solar panel and its lead go).
- Cable lengths to the other two blinds.
