# ControllerV4 dev board: placement and wiring

Step-by-step guide with pictures and which parts have a direction: [dev-board-build.md](../dev-board-build.md).

## Parts: where each one goes

| Part | Holes | Note |
|---|---|---|
| C 10u | j1 (5V), i2 (G) |  |
| D3 1N5819 | j4 (A), j3 (K) |  |
| R div top 1M | d15, d16 |  |
| R div bot 1M | d17, d18 |  |
| C div 100n | e16, e18 |  |
| R ADC1 1k | b12, c12 |  |
| C ADC1 100n | a14, c14 |  |
| R ADC2 1k | d12, d13 |  |
| C ADC2 100n | d14, f14 |  |
| R ADC3 1k | f12, g12 |  |
| C ADC3 100n | g14, i14 |  |
| R pwr top 1M | g22, g21 |  |
| R pwr bot 1M | g20, g19 |  |
| D1 1N5819 USB | e23 (A), e22 (K) |  |
| D2 1N5819 solar | h23 (A), g23 (K) |  |
| Z 6.2V | d22 (K), d23 (A) |  |
| Battery pins | a24 (B-), b24 (B+) |  |
| USB leads | d24 (V-), e24 (V+) |  |
| Solar leads | h24 (S+), i24 (S-) |  |

Ceramic capacitors have legs 3 holes apart: the middle hole stays empty. The 10 u goes corner to corner (j1-i2) with its legs pulled in slightly.
The bulk electrolytic that comes with the charger is soldered onto the charger board itself (+ to its LOAD side).

ESP32-C6: chip side up, header pins in its **inner** holes, into **b1-b10** (TX16, RX17, 0, 1, 2, 3, 4, 5, 6, 7) and
**h1-h10** (5V, GND, 3V3, 20, 19, 18, 15, 14, 9, 8), USB-C overhanging row 1 (confirmed against the board).
Leave its inner pads (12, 13, 21, 22, 23) and BAT pad unconnected. Charger: off the board, wired in (see the charger table).

D3 (j3-j4) drops ~0.3 V, so the ESP browns out near 3.4-3.5 V on the cell (last ~10-15 %). Optional: 2 header
pins + jumper at j3-j4 instead of D3 (zero drop; pull the jumper before plugging USB into the ESP).

## Port leads (from the RJ12 boards)

| Lead | Hole | Lead | Hole | Lead | Hole |
|---|---|---|---|---|---|
| P1 IN1 | i6 | P2 IN1 | i4 | P3 IN1 | a1 |
| P1 IN2 | i5 | P2 IN2 | i8 | P3 IN2 | a2 |
| P1 EN | a7 | P2 EN | a8 | P3 EN | a10 |
| P1 ANG | b11 | P2 ANG | d11 | P3 ANG | f11 |
| P1 VBAT | j15 | P2 VBAT | j16 | P3 VBAT | j17 |
| P1 GND | a15 | P2 GND | a16 | P3 GND | a17 |

RJ12 pin -> signal: 1 VBAT, 2 IN1, 3 GND, 4 ANG, 5 EN, 6 IN2. Port 1 = room side, port 3 = back side.

## Underside wiring

| From | To | What |
|---|---|---|
| a12 | a24 | GND rail: bare wire down column a, rows 12-24 |
| j4 | j24 | VBAT rail: bare wire down column j, rows 4-24 |
| a1 | b1 | bridge: port 3 IN1 -> GPIO16 |
| a2 | b2 | bridge: port 3 IN2 -> GPIO17 |
| a3 | b3 | bridge: angle 1 -> GPIO0 |
| a4 | b4 | bridge: angle 2 -> GPIO1 |
| a5 | b5 | bridge: angle 3 -> GPIO2 |
| a6 | b6 | bridge: battery divider -> GPIO3 |
| a7 | b7 | bridge: port 1 EN -> GPIO4 |
| a8 | b8 | bridge: port 2 EN -> GPIO5 |
| a9 | b9 | bridge: input-power sense -> GPIO6 |
| a10 | b10 | bridge: port 3 EN -> GPIO7 |
| h1 | i1 | bridge: ESP 5V |
| i1 | j1 | bridge: ESP 5V -> C 10u |
| h2 | j2 | bridge (over i2): ESP GND -> C 10u |
| h4 | i4 | bridge: port 2 IN1 -> GPIO20 |
| h5 | i5 | bridge: port 1 IN2 -> GPIO19 |
| h6 | i6 | bridge: port 1 IN1 -> GPIO18 |
| h8 | i8 | bridge: port 2 IN2 -> GPIO14 |
| j3 | i3 | bridge: D3 cathode (5V) |
| i3 | i1 | wire: D3 cathode -> ESP 5V (straight along column i) |
| j2 | a12 | wire: ESP GND -> GND rail |
| d15 | e15 | bridge: R div top (VBAT) |
| e15 | j18 | wire: R div top -> VBAT rail |
| d16 | d17 | bridge: divider node |
| d16 | e16 | bridge: divider node -> C div |
| d17 | c17 | bridge: divider node |
| c17 | a6 | wire: divider node -> GPIO3 |
| d18 | e18 | bridge: C div GND |
| d18 | c18 | bridge: divider GND |
| c18 | b18 | bridge: divider GND |
| b18 | a18 | bridge: divider GND -> GND rail |
| b11 | b12 | bridge: port 1 ANGLE -> R ADC1 |
| d11 | d12 | bridge: port 2 ANGLE -> R ADC2 |
| f11 | f12 | bridge: port 3 ANGLE -> R ADC3 |
| c12 | c13 | bridge: R ADC1 -> filter 1 node |
| c13 | c14 | bridge: filter 1 node -> C ADC1 |
| d13 | d14 | bridge: R ADC2 -> C ADC2 |
| d13 | e13 | bridge: filter 2 node |
| g12 | g13 | bridge: R ADC3 -> filter 3 node |
| g13 | g14 | bridge: filter 3 node -> C ADC3 |
| c13 | a3 | wire: filter 1 -> GPIO0 |
| e13 | a4 | wire: filter 2 -> GPIO1 |
| g13 | a5 | wire: filter 3 -> GPIO2 |
| f14 | f15 | bridge: C ADC2 GND |
| f15 | a13 | wire: C ADC2 -> GND rail |
| i14 | i15 | bridge: C ADC3 GND |
| i15 | b16 | wire: C ADC3 -> GND |
| b16 | a16 | bridge: C ADC3 GND -> GND rail |
| g22 | g23 | bridge: PWR node -> R pwr top |
| g21 | g20 | bridge: input-power sense node |
| g21 | f21 | bridge: input-power sense node |
| f21 | a9 | wire: input-power sense -> GPIO6 |
| g19 | f19 | bridge: R pwr bot GND |
| f19 | a19 | wire: R pwr bot -> GND rail |
| e24 | e23 | bridge: USB V+ -> D1 anode |
| h24 | h23 | bridge: solar + -> D2 anode |
| d22 | e22 | bridge: PWR node (zener cathode, D1 cathode) |
| e22 | f22 | bridge: PWR node |
| f22 | g22 | bridge: PWR node -> R pwr top |
| g23 | g24 | bridge: PWR node -> charger PWR + hole |
| d24 | d23 | bridge: USB V- -> zener anode (GND) |
| d23 | c23 | bridge: GND link |
| c23 | b23 | bridge: GND link |
| b23 | a23 | bridge: GND link -> GND rail |
| b24 | c24 | bridge: battery + -> charger BATT + hole |
| i24 | i23 | bridge: solar - (GND) |
| i23 | a18 | wire: solar - -> GND rail |

## Charger pads

| Pad | Board hole | Net |
|---|---|---|
| PWR + (input) | g24 | PWR node: D1 + D2 cathodes, zener (22 AWG pair with PWR -) |
| PWR - / GND | a20 | GND rail |
| BATT + | c24 | battery pin B+ (bridged from b24), 22 AWG pair with BATT - (the cell reaches the VBAT rail only through the charger) |
| BATT - | a21 | GND rail |
| LOAD + (output) | j20 | VBAT rail (22 AWG pair with LOAD -) |
| LOAD - | a22 | GND rail |
| THERM | (NTC) | remove the 103 (10 k) resistor beside the THERM label; NTC across its two pads, taped to the cell |
| CE, TE, PROG2, SEL (edge pads) | - | leave unconnected (board defaults); the board has no STAT pad, status is on its LEDs |
