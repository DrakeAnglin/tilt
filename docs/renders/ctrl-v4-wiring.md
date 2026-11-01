# ControllerV4 dev board: placement and wiring

Step-by-step guide with pictures and which parts have a direction: [dev-board-build.md](../dev-board-build.md).

## Parts: where each one goes

| Part | Holes | Note |
|---|---|---|
| C 10u | j1 (5V), j2 (G) |  |
| R stat 10k | j3, j4 |  |
| D3 1N5819 | j5 (K), j6 (A) |  |
| R div top 1M | j7, j8 |  |
| R div bot 1M | j9, j10 |  |
| C div 100n | g12, g13 |  |
| R ADC1 1k | b12, b13 |  |
| C ADC1 100n | a14, b14 |  |
| R ADC2 1k | d12, d13 |  |
| C ADC2 100n | c14, d14 |  |
| R ADC3 1k | f12, f13 |  |
| C ADC3 100n | e14, f14 |  |
| C bulk | i12 (-), i13 (+) |  |
| D1 1N5819 USB | e23 (A), d23 (K) |  |
| D2 1N5819 solar | h23 (A), g23 (K) |  |
| Z 6.2V | f24 (A), f23 (K) |  |
| Battery pins | b24 (B-), c24 (B+) |  |
| USB leads | d24 (V-), e24 (V+) |  |
| Solar leads | h24 (S+), i24 (S-) |  |

ESP32-C6: chip side up, header pins in its **inner** holes, into **b1-b10** (TX16, RX17, 0, 1, 2, 3, 4, 5, 6, 7) and
**h1-h10** (5V, GND, 3V3, 20, 19, 18, 15, 14, 9, 8), USB-C overhanging row 1 (confirmed against the board).
Leave its inner pads (12, 13, 21, 22, 23) and BAT pad unconnected. Charger: foam tape over **c15-h22**.

D3 (j5-j6) drops ~0.3 V, so the ESP browns out near 3.4-3.5 V on the cell (last ~10-15 %). Optional: 2 header
pins + jumper at j5-j6 instead of D3 (zero drop; pull the jumper before plugging USB into the ESP).

## Port leads (from the RJ12 boards)

| Lead | Hole | Lead | Hole | Lead | Hole |
|---|---|---|---|---|---|
| P1 IN1 | i6 | P2 IN1 | i4 | P3 IN1 | a1 |
| P1 IN2 | i5 | P2 IN2 | i8 | P3 IN2 | a2 |
| P1 EN | a7 | P2 EN | a8 | P3 EN | a9 |
| P1 ANG | b11 | P2 ANG | d11 | P3 ANG | f11 |
| P1 VBAT | j15 | P2 VBAT | j16 | P3 VBAT | j17 |
| P1 GND | a15 | P2 GND | a16 | P3 GND | a17 |

RJ12 pin -> signal: 1 VBAT, 2 IN1, 3 GND, 4 ANG, 5 EN, 6 IN2. Port 1 = room side, port 3 = back side.

## Underside wiring

| From | To | What |
|---|---|---|
| a12 | a24 | GND rail: bare wire down column a, rows 12-24 |
| j11 | j24 | VBAT rail: bare wire down column j, rows 11-24 |
| a1 | b1 | bridge: port 3 IN1 -> GPIO16 |
| a2 | b2 | bridge: port 3 IN2 -> GPIO17 |
| a3 | b3 | bridge: angle 1 -> GPIO0 |
| a4 | b4 | bridge: angle 2 -> GPIO1 |
| a5 | b5 | bridge: angle 3 -> GPIO2 |
| a6 | b6 | bridge: battery divider -> GPIO3 |
| a7 | b7 | bridge: port 1 EN -> GPIO4 |
| a8 | b8 | bridge: port 2 EN -> GPIO5 |
| a9 | b9 | bridge: port 3 EN -> GPIO6 |
| a10 | b10 | bridge: charger STAT -> GPIO7 |
| h1 | j1 | bridge (over i1): ESP 5V -> C 10u |
| h2 | j2 | bridge (over i2): ESP GND -> C 10u |
| h3 | j3 | bridge (over i3): ESP 3V3 -> R stat |
| h4 | i4 | bridge: port 2 IN1 -> GPIO20 |
| h5 | i5 | bridge: port 1 IN2 -> GPIO19 |
| h6 | i6 | bridge: port 1 IN1 -> GPIO18 |
| h8 | i8 | bridge: port 2 IN2 -> GPIO14 |
| j5 | j1 | wire: D3 cathode -> ESP 5V |
| j6 | j11 | wire: D3 anode -> VBAT rail |
| j2 | a12 | wire: ESP GND -> GND rail |
| j4 | a10 | wire: R stat -> STAT / GPIO7 |
| j7 | j11 | wire: R div top -> VBAT rail |
| j8 | j9 | bridge: divider node |
| j8 | g12 | wire: divider node -> C div |
| g12 | a6 | wire: divider node -> GPIO3 |
| j10 | a12 | wire: R div bot -> GND rail |
| g13 | a13 | wire: C div -> GND rail |
| b11 | b12 | bridge: port 1 ANGLE -> R ADC1 |
| d11 | d12 | bridge: port 2 ANGLE -> R ADC2 |
| f11 | f12 | bridge: port 3 ANGLE -> R ADC3 |
| b13 | b14 | bridge: R ADC1 -> C ADC1 |
| d13 | d14 | bridge: R ADC2 -> C ADC2 |
| f13 | f14 | bridge: R ADC3 -> C ADC3 |
| b13 | a3 | wire: filter 1 -> GPIO0 |
| d13 | a4 | wire: filter 2 -> GPIO1 |
| f13 | a5 | wire: filter 3 -> GPIO2 |
| c14 | a14 | wire: C ADC2 -> GND rail |
| e14 | a14 | wire: C ADC3 -> GND rail |
| i13 | j13 | bridge: C bulk + -> VBAT rail |
| i12 | a12 | wire: C bulk - -> GND rail |
| e23 | e24 | bridge: USB V+ -> D1 anode |
| h23 | h24 | bridge: solar + -> D2 anode |
| d23 | f23 | wire: D1 cathode -> PWR node (zener cathode) |
| f23 | g23 | bridge: PWR node -> D2 cathode |
| b24 | a24 | bridge: battery - -> GND rail |
| d24 | a24 | wire: USB V- -> GND rail |
| f24 | a24 | wire: zener anode -> GND rail |
| i24 | a24 | wire: solar - -> GND rail (run it under the board) |

## Charger pads

| Pad | Board hole | Net |
|---|---|---|
| PWR + (input) | g23 | PWR node: D1 + D2 cathodes, zener |
| PWR - / GND | a20 | GND rail |
| BATT + | c24 | battery pin B+ |
| BATT - | a21 | GND rail |
| LOAD + (output) | j20 | VBAT rail |
| LOAD - | a22 | GND rail |
| STAT | a10 | GPIO7 (pulled up by R stat) |
| THERM | (NTC) | remove the board's THERM resistor; NTC from THERM to GND, taped to the cell |
