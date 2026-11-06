# Building the controller dev board, step by step

For the kit's **3 × 7 cm perfboard (columns a–j, rows 1–24)**. Everything here (pictures, tables, counts) is generated
from the layout in [DevBoardR.py](../hardware/mechanical/fusion/ControllerV4/DevBoardR.py) (ESP turned across the
board, resistors and diodes lying flat) by [`tools/devboard_guide.py`](../tools/devboard_guide.py);
[`tools/devboard_check.py`](../tools/devboard_check.py) checks every connection, no shorts, no parts touching, and that
every hole holds exactly one thing (a part leg, a lead or a wire end).

**Totals:** 87 parts and leads on top, 4 insulated wires, 61 bare bridges, 3 rails.

**Order:** parts, sockets and the board's own wires first, then the RJ12 and solar leads (steps 1–9), while every hole
is still open; then the rails (10) and the bare bridges (11–15: every board, then one step per port, then solar), which land on those
holes' pads; then the charger, which only plugs in (16); the ESP and USB-C board plug in last (17). **Ports 2 and 3 and
the solar lead are optional:** skip a port's lead step and its bridge step together. Each
step does one kind of part, and in its picture that step is in color while everything already done is gray.

## Parts for one board

| Part | Count | Step | From (BOM) |
|---|---|---|---|
| ESP32-C6 SuperMini, with its male pins soldered on | 1 | plugs in at the end | ESP32-C6 SuperMini 5-pack |
| Female header sockets ("pin stands") | 2 × 10 + 1 × 6 | 4: ESP and USB-C sockets | perfboard kit headers |
| JST-XH header, 2-pin top entry | 3 | 4: battery, charger +, charger LOAD + | JST-XH kit (to buy) |
| JST-XH header, 3-pin right angle | 1 | 4: charger GND | JST-XH kit (to buy) |
| JST-XH housings (2-pin × 2, 3-pin × 1) + 6 crimp pins | 1 | 5: charger plugs | JST-XH kit (to buy) |
| Resistor 1 kΩ | 3 | 2 | resistor kit |
| Resistor 1 MΩ | 4 | 2: battery and input-power dividers | resistor kit |
| Diode 1N5819 | 3 | 3 | 1N5819 150-pack |
| Zener 6.2 V | 1 | 3 | zener kit |
| Ceramic capacitor 100 nF (104) | 4 | 4 | ceramic capacitor kit |
| Ceramic capacitor 10 µF (106) | 1 | 4 | ceramic capacitor kit |
| MCP73871 charger board, 30.5 × 31.5 mm, off the board (+ its 16 × 26 mm bulk capacitor) | 1 | 6 | Comimark MCP73871 |
| NTC thermistor 10 kΩ | 1 | 6 | NTC 10-pack |
| 22 AWG stranded insulated wire (the white two-conductor, split) | 6 × 6-8 cm + 6 × 5-8 cm | 5 (charger power), 6 (RJ12 battery + / GND) | white 2-conductor 22 AWG |
| RJ12 breakout board | 3 | 7 (18 leads) | RJ11/RJ12 breakout 4-pack |
| USB-C breakout (Cermant), with its 6 male pins | 1 | plugs in at the end | USB-C breakout 10-pack |
| Solar lead (optional) | 1 | 7 (2 leads, optional) | solar panel + extension |
| 30 AWG silicone stranded insulated wire | 4 + 12 pieces | 8 (board wires), 6 (RJ12 signals) | 30 AWG silicone wire |
| Bare wire or trimmed resistor legs | 61 bridges + 3 rails | 9, 10 | 22 AWG solid tinned bus wire (to buy, ~0.4 m per board) + leg offcuts |
| Perfboard 3 × 7 cm (a–j × 1–24) | 1 | all | perfboard kit |
| 18650 cell with JST-XH plug | 1 | 11 | 18650 cell |

For all 3 controllers, triple every count. Links and prices: [BOM](../hardware/BOM.md).

## Which parts have a direction?

![which way round](renders/build-polarity.png)

| Part | Direction matters? | How to tell |
|---|---|---|
| Resistors | **No** | either way round |
| Ceramic capacitors | **No** | either way round; legs 3 holes apart, the middle hole stays empty |
| **1N5819 diodes, 6.2 V zener** | **YES** | the silver/white **band is the cathode (K)** |
| **ESP32-C6** | **YES** | chip side up, 5V in a3, TX in a9 |
| **Battery JST header** | **YES** | keyed, but check before soldering it: the cell's red wire must land on **b19 (+)** |
| **Charger bulk capacitor** (on the charger board) | **YES** | stripe = −, long leg = + |
| USB-C and solar leads, charger pads | **YES** | follow the tables |

A reversed diode just won't conduct; a reversed electrolytic or battery can damage parts. Check those twice.

## Tools and tips
- Soldering iron (~330 °C), thin solder, flush cutters, tweezers, multimeter (beep / continuity mode), marker.
- Place parts on the **top**, solder **underneath**, trim leads to ~1 mm.
- Use just enough solder for a small cone on the pad. Too much spreads to the next pad or fills holes.
- If a hole fills by accident, heat it and clear it with a desoldering pump or wick before going on.

## Step 1: Resistors (7)

**You need:** 4 × 1 MΩ resistor, 3 × 1 kΩ resistor.

![step 1](renders/build-step-01.png)

First mark the board: **row 1 = the end toward the phone jacks**, **column a = the edge with the row numbers printed on
it** (toward the battery).

Resistors have no direction. Bend both legs down 90° right at the body so they drop into holes 4 apart (3 spaces), push
them through so the body lies flat on the board, splay the legs slightly underneath, solder, and **trim to ~1 mm**. Keep
the trimmed legs: they make good bridges later. The holes under each body stay empty.

| Resistor | Holes | How |
|---|---|---|
| R div top 1M | h23, h20 | flat, legs in h23 and h20 |
| R div bot 1M | g15, g18 | flat, legs in g15 and g18 |
| R pwr top 1M | e15, e18 | flat, legs in e15 and e18 |
| R pwr bot 1M | c15, c18 | flat, legs in c15 and c18 |
| R ADC1 1k | b11, b14 | flat, legs in b11 and b14 |
| R ADC2 1k | d11, d14 | flat, legs in d11 and d14 |
| R ADC3 1k | h11, h14 | flat, legs in h11 and h14 |

## Step 2: Diodes (3 × 1N5819, 1 × 6.2 V zener)

**You need:** 3 × 1N5819 diode, 1 × 6.2 V zener.

![step 2](renders/build-step-02.png)

These **only work one way round**; the band end is the cathode (K). Bend the legs like the resistors (4 holes)
and lay each one flat with its **band at the K hole** in the table and the picture. Check each one before soldering.

| Diode | Holes | Direction |
|---|---|---|
| D3 1N5819 | i15, i18 | flat, **band (K) at i18**, other end (A) at i15 |
| D1 1N5819 USB | b23, b20 | flat, **band (K) at b20**, other end (A) at b23 |
| D2 1N5819 solar | f23, f20 | flat, **band (K) at f20**, other end (A) at f23 (for the solar input; fit it anyway) |
| Z 6.2V | d20, d23 | flat, **band (K) at d20**, other end (A) at d23 (for the solar input; fit it anyway) |

## Step 3: Ceramic capacitors (4 × 100 nF, 1 × 10 µF)

**You need:** 1 × 10 µF (106) ceramic capacitor, 4 × 100 nF (104) ceramic capacitor.

![step 3](renders/build-step-03.png)

No direction. Push them straight down so the body sits low; don't bend the legs at the body.

| Capacitor | Holes | Note |
|---|---|---|
| C 10u | a1, c1 | middle hole b1 stays empty |
| C div 100n | f11, f13 | middle hole f12 stays empty |
| C ADC1 100n | c10, c12 | middle hole c11 stays empty |
| C ADC2 100n | e10, e12 | middle hole e11 stays empty |
| C ADC3 100n | g10, g12 | middle hole g11 stays empty |

## Step 4: Sockets and connectors: ESP (2 × 10), USB-C (1 × 6), JST: battery, charger (3)

**You need:** 2 × 10-way female header socket (pin stand), 1 × 6-way female header socket (cut from a strip), 3 × JST-XH 2-pin top-entry header, 1 × JST-XH 3-pin right-angle header.

![step 4](renders/build-step-04.png)

All the header parts at once:

1. **ESP socket:** two 10-way female socket strips in **a3–j3** and **a9–j9**. To get them straight, push the strips onto the
   ESP's own pins, set ESP + sockets on the board (chip side up, USB-C over the column-a edge), solder one end pin of each
   strip, check they sit flat, solder the rest, then lift the ESP back out.
2. **USB-C socket:** one 6-way socket strip in **b24–g24**, the same way with the breakout: its USB-C socket points **out past
   the row-24 end**, pins VBUS, GND, CC1, D−, D+, CC2 from column b. Solder, then lift it out.
3. **JST-XH headers** (2.5 mm pitch, fits the holes; they're keyed, so plugs only go in one way). It's tight around
   a19–a23 but they fit:
   - **Battery:** 2-pin top-entry header in **a19 (−) / b19 (+)**. Before soldering, hold the cell's plug against it: its
     **red wire must land on b19**. Turn the header round if it doesn't.
   - **Charger +:** 2-pin top-entry header in **d19 (BATT +) / e19 (PWR +)**.
   - **Charger LOAD +:** 2-pin top-entry header in **j20–j21** (both pins are on the battery + rail).
   - **Charger GND:** 3-pin **right-angle** header in **a21 / a22 / a23** (PWR −, BATT −, LOAD −), opening outward over the
     column-a edge.

| Part | Holes | Note |
|---|---|---|
| ESP socket | a3–j3, a9–j9 | ESP plugs in chip side up, USB-C over the column-a edge |
| USB-C socket | b24–g24 | VBUS, GND, CC1, D−, D+, CC2; its socket points past row 24 |
| JST battery (2-pin) | a19 (−), b19 (+) | red wire of the cell's plug on b19 |
| JST charger + (2-pin) | d19 (BATT +), e19 (PWR +) | top entry |
| JST charger LOAD + (2-pin) | j20, j21 | top entry, both pins battery + |
| JST charger GND (3-pin) | a21 (PWR −), a22 (BATT −), a23 (LOAD −) | right angle, opening over the column-a edge |

## Step 5: Insulated wires underneath (4)

**You need:** 4 × 30 AWG silicone stranded insulated wire: 1 black, 1 red, 2 white.

![step 5](renders/build-step-05.png)

All of these are **30 AWG silicone stranded insulated wire**. They go in **before** the bridges and rails, while their
holes are still open. For each wire: cut it a little long,
strip ~2 mm at each end, push the ends into the two holes **from underneath**, solder, trim. Beep each wire out with the
meter as you go.

| From | To | What |
|---|---|---|
| b2 | a13 | **black**: ESP GND -> GND rail (under the ESP) |
| i19 | a2 | **red**: D3 cathode -> ESP 5V (under the ESP) |
| h19 | f10 | **white**: divider node -> GPIO3 |
| d16 | i10 | **white**: input-power sense -> GPIO6 |

## Step 6: RJ12 port 1 (6 leads)

**You need:** 1 × RJ12 breakout board, 22 AWG stranded, 5–8 cm: 1 red (battery +), 1 black (GND), 30 AWG silicone, 5–8 cm: 1 each green (IN1), yellow (IN2), blue (EN), white (angle).

![step 6](renders/build-step-06.png)

Solder 6 leads, 5–8 cm long, to port 1's RJ12 board: **22 AWG stranded insulated wire** (the white two-conductor
wire, split) for **battery + and GND**, which carry the motor current, and **30 AWG silicone stranded wire** for the four
signals. **Colors, the same on every port and on the tilter end:** pin 1 battery + **red**, 2 IN1 **green**, 3 GND
**black**, 4 angle **white**, 5 EN **blue**, 6 IN2 **yellow**. Then push each lead into its hole from the top (table), solder
underneath, trim to ~1 mm.

| RJ12 pin | Wire | Hole |
|---|---|---|
| 1 battery + | **red**, 22 AWG stranded | j16 |
| 2 IN1 | **green**, 30 AWG silicone | f2 |
| 3 GND | **black**, 22 AWG stranded | a14 |
| 4 angle | **white**, 30 AWG silicone | b15 |
| 5 EN | **blue**, 30 AWG silicone | d10 |
| 6 IN2 | **yellow**, 30 AWG silicone | e2 |

## Step 7: RJ12 port 2 (6 leads): optional, for 2 or more blinds

**You need:** 1 × RJ12 breakout board, 22 AWG stranded, 5–8 cm: 1 red (battery +), 1 black (GND), 30 AWG silicone, 5–8 cm: 1 each green (IN1), yellow (IN2), blue (EN), white (angle).

![step 7](renders/build-step-07.png)

**Optional:** skip it on a controller that drives only 1 blind; the holes stay free for later. Solder 6 leads, 5–8 cm long, to port 2's RJ12 board: **22 AWG stranded insulated wire** (the white two-conductor
wire, split) for **battery + and GND**, which carry the motor current, and **30 AWG silicone stranded wire** for the four
signals. **Colors, the same on every port and on the tilter end:** pin 1 battery + **red**, 2 IN1 **green**, 3 GND
**black**, 4 angle **white**, 5 EN **blue**, 6 IN2 **yellow**. Then push each lead into its hole from the top (table), solder
underneath, trim to ~1 mm.

| RJ12 pin | Wire | Hole |
|---|---|---|
| 1 battery + | **red**, 22 AWG stranded | j17 |
| 2 IN1 | **green**, 30 AWG silicone | d2 |
| 3 GND | **black**, 22 AWG stranded | a15 |
| 4 angle | **white**, 30 AWG silicone | e14 |
| 5 EN | **blue**, 30 AWG silicone | h10 |
| 6 IN2 | **yellow**, 30 AWG silicone | h2 |

## Step 8: RJ12 port 3 (6 leads): optional, for 3 blinds

**You need:** 1 × RJ12 breakout board, 22 AWG stranded, 5–8 cm: 1 red (battery +), 1 black (GND), 30 AWG silicone, 5–8 cm: 1 each green (IN1), yellow (IN2), blue (EN), white (angle).

![step 8](renders/build-step-08.png)

**Optional:** skip it on the controller that drives only 2 blinds; the holes stay free for later. Solder 6 leads, 5–8 cm long, to port 3's RJ12 board: **22 AWG stranded insulated wire** (the white two-conductor
wire, split) for **battery + and GND**, which carry the motor current, and **30 AWG silicone stranded wire** for the four
signals. **Colors, the same on every port and on the tilter end:** pin 1 battery + **red**, 2 IN1 **green**, 3 GND
**black**, 4 angle **white**, 5 EN **blue**, 6 IN2 **yellow**. Then push each lead into its hole from the top (table), solder
underneath, trim to ~1 mm.

| RJ12 pin | Wire | Hole |
|---|---|---|
| 1 battery + | **red**, 22 AWG stranded | j18 |
| 2 IN1 | **green**, 30 AWG silicone | a10 |
| 3 GND | **black**, 22 AWG stranded | a16 |
| 4 angle | **white**, 30 AWG silicone | h15 |
| 5 EN | **blue**, 30 AWG silicone | j10 |
| 6 IN2 | **yellow**, 30 AWG silicone | b10 |

## Step 9: Solar lead (optional)

**You need:** 1 × 22 AWG two-conductor lead to the panel, + red / − black (mark the white wire): optional.

![step 9](renders/build-step-09.png)

**Optional.** Only if this controller gets a solar panel. The lead is the **white 22 AWG two-conductor wire** (the
solar extension, cut to length): band the + conductor **red** and the − **black** with heat-shrink at both ends. Solder its
**+ (red) → g23** and **− (black) → a17**
(a17 is on the GND rail). Trim underneath.

Without solar, skip it: the board charges over USB-C alone. D2 and the zener from step 2 are only there for the
solar input, but fit them anyway so a panel can be added later without re-soldering.

| Lead | Hole | Goes to |
|---|---|---|
| Solar + | g23 | to D2's anode (bridge in step 15) |
| Solar − | a17 | GND rail |

## Step 10: Rails (3)

**You need:** 3 × 22 AWG solid tinned bus wire: GND a13–i13 ~30 mm; GND a13–a24 ~37 mm; battery + j11–j24 ~43 mm.

![step 10](renders/build-step-10.png)

Lay a straight piece of **22 AWG solid tinned copper (bus) wire** for each rail (GND a13–i13, GND a13–a24, battery + j11–j24), soldering it at every hole
it passes. The rails go in before the bridges, so every bridge that goes to GND or battery + ends on a rail that's already
there. Where two GND rails
meet at a corner, solder them together there. Next come the bridges (step 11).

| From | To | What |
|---|---|---|
| a13 | i13 | bare wire across row 13, a-i |
| a13 | a24 | bare wire down column a, rows 13-24 |
| j11 | j24 | bare wire down column j, rows 11-24 |

## Step 11: Bare bridges: every board (21 pieces of wire)

**You need:** 21 pieces of bare wire: leg offcuts saved from steps 1-3 for the short ones, 22 AWG solid tinned bus wire for runs of 3+ holes.

![step 11](renders/build-step-11.png)

A bridge is **bare solid wire** (a trimmed leg, or **22 AWG solid tinned copper bus wire**) laid flat on the pads and
soldered at **every hole it crosses**. Each row in the table is **one piece of wire**: "b20 → f20, 5 holes" means one
straight piece from b20 to f20, soldered at b20, c20, d20, e20 and f20. Where two runs meet at a corner you can bend one
piece round the corner instead of using two.

Some runs cross **empty holes**. That's on purpose: a bridge can only join holes that are next to each other, so to get
round a part a connection steps through free holes on the way (on row 20, c20 and e20 are just stepping stones between
D1, the zener and D2). The meter check: each run's two ends beep, and it doesn't beep to the holes beside it.

The bridges that only serve one RJ12 port, and the solar one, come in the next steps, so a port you don't use leaves no
bridges to nowhere.

| One piece of wire | Length | What it joins |
|---|---|---|
| a1 → a3 | 3 holes | C 10u 5V (a1), wire end (a2), ESP 5V (a3) |
| b1 → b3 | 3 holes | wire end (b2), ESP GND (b3), meets the next run at b1 |
| b1 → c1 | 2 holes | C 10u G (c1), meets the next run at b1 |
| f9 → f11 | 3 holes | ESP 3 (f9), wire end (f10), C div 100n (f11) |
| i9 → i10 | 2 holes | ESP 6 (i9), wire end (i10) |
| g13 → g15 | 3 holes | GND rail (g13), R div bot 1M (g15), steps over empty g14 |
| c15 → e15 | 3 holes | R pwr bot 1M (c15), R pwr top 1M (e15), meets the next run at d15 |
| d15 → d16 | 2 holes | wire end (d16), meets the next run at d15 |
| i15 → j15 | 2 holes | D3 A (i15), battery + rail (j15) |
| a18 → c18 | 3 holes | GND rail (a18), R pwr bot 1M (c18), steps over empty b18 |
| e18 → e20 | 3 holes | R pwr top 1M (e18), JST PWR+ (e19), meets the next run at e20 |
| g18 → h18 | 2 holes | R div bot 1M (g18), meets the next run at h18 |
| h18 → h20 | 3 holes | wire end (h19), R div top 1M (h20), meets the next run at h18 |
| i18 → i19 | 2 holes | D3 K (i18), wire end (i19) |
| b19 → d19 | 3 holes | battery B+ (b19), JST BATT+ (d19), steps over empty c19 |
| b20 → f20 | 5 holes | D1 K (b20), zener K (d20), D2 K (f20), meets the next run at e20, steps over empty c20 |
| a22 → c22 | 3 holes | JST BATT- / GND rail (a22), meets the next run at c22, steps over empty b22 |
| c22 → c24 | 3 holes | USB-C breakout GND (c24), meets the next run at c22, c23 |
| b23 → b24 | 2 holes | D1 A (b23), USB-C breakout VBUS (b24) |
| c23 → d23 | 2 holes | zener A (d23), meets the next run at c23 |
| h23 → j23 | 3 holes | R div top 1M (h23), battery + rail (j23), steps over empty i23 |

## Step 12: Bare bridges: port 1 (7 pieces)

**You need:** 7 pieces of bare wire (leg offcuts or 22 AWG solid tinned).

![step 12](renders/build-step-12.png)

Port 1's bridges: its four signal leads to their ESP pins, and its angle filter (the 1 kΩ and 100 nF) to the
ESP and the GND rail. Same method as the step before: each row is one piece of wire.

| One piece of wire | Length | What it joins |
|---|---|---|
| e2 → e3 | 2 holes | lead P1 IN2 (e2), ESP 19 (e3) |
| f2 → f3 | 2 holes | lead P1 IN1 (f2), ESP 18 (f3) |
| c9 → c11 | 3 holes | ESP 0 (c9), C ADC1 100n (c10), meets the next run at c11 |
| d9 → d10 | 2 holes | ESP 1 (d9), lead P1 EN (d10) |
| b11 → c11 | 2 holes | R ADC1 1k (b11), meets the next run at c11 |
| c12 → c13 | 2 holes | C ADC1 100n (c12), GND rail (c13) |
| b14 → b15 | 2 holes | R ADC1 1k (b14), lead P1 ANG (b15) |

## Step 13: Bare bridges: port 2 (7 pieces): optional

**You need:** 7 pieces of bare wire (leg offcuts or 22 AWG solid tinned).

![step 13](renders/build-step-13.png)

Port 2's bridges: its four signal leads to their ESP pins, and its angle filter (the 1 kΩ and 100 nF) to the
ESP and the GND rail. Same method as the step before: each row is one piece of wire.

**Optional:** only if this controller drives 2 or more blinds. Skipped, the port's holes stay open for later; its 1 kΩ and
100 nF can stay on the board unconnected.

| One piece of wire | Length | What it joins |
|---|---|---|
| d2 → d3 | 2 holes | lead P2 IN1 (d2), ESP 20 (d3) |
| h2 → h3 | 2 holes | lead P2 IN2 (h2), ESP 14 (h3) |
| e9 → e11 | 3 holes | ESP 2 (e9), C ADC2 100n (e10), meets the next run at e11 |
| h9 → h10 | 2 holes | ESP 5 (h9), lead P2 EN (h10) |
| d11 → e11 | 2 holes | R ADC2 1k (d11), meets the next run at e11 |
| e12 → e13 | 2 holes | C ADC2 100n (e12), GND rail (e13) |
| d14 → e14 | 2 holes | R ADC2 1k (d14), lead P2 ANG (e14) |

## Step 14: Bare bridges: port 3 (7 pieces): optional

**You need:** 7 pieces of bare wire (leg offcuts or 22 AWG solid tinned).

![step 14](renders/build-step-14.png)

Port 3's bridges: its four signal leads to their ESP pins, and its angle filter (the 1 kΩ and 100 nF) to the
ESP and the GND rail. Same method as the step before: each row is one piece of wire.

**Optional:** only if this controller drives 3 blinds. Skipped, the port's holes stay open for later; its 1 kΩ and
100 nF can stay on the board unconnected.

| One piece of wire | Length | What it joins |
|---|---|---|
| a9 → a10 | 2 holes | ESP TX16 (a9), lead P3 IN1 (a10) |
| b9 → b10 | 2 holes | ESP RX17 (b9), lead P3 IN2 (b10) |
| g9 → g11 | 3 holes | ESP 4 (g9), C ADC3 100n (g10), meets the next run at g11 |
| j9 → j10 | 2 holes | ESP 7 (j9), lead P3 EN (j10) |
| g11 → h11 | 2 holes | R ADC3 1k (h11), meets the next run at g11 |
| g12 → g13 | 2 holes | C ADC3 100n (g12), GND rail (g13) |
| h14 → h15 | 2 holes | R ADC3 1k (h14), lead P3 ANG (h15) |

## Step 15: Bare bridge: solar (1 piece): optional

**You need:** 1 short bare wire.

![step 15](renders/build-step-15.png)

**Optional:** only if you fitted the solar lead. One short bridge joins the lead's + hole to D2's anode.

| One piece of wire | Length | What it joins |
|---|---|---|
| f23 → g23 | 2 holes | D2 A (f23), Solar leads S+ (g23) |

## Step 16: Charger: prepare it, put JST plugs on its wires (3 plugs)

**You need:** 1 × MCP73871 charger board (+ its bulk capacitor), 1 × 10 kΩ NTC thermistor, 22 AWG stranded, 6–8 cm: 3 red (+), 3 black (−), 1 × JST-XH 3-pin housing, 2 × JST-XH 2-pin housing, 6 × JST-XH crimp pins.

![step 16](renders/build-step-16.png)

The charger board (30.5 × 31.5 mm) is wider than the perfboard, and its bulk capacitor is 16 mm across and 26 mm tall,
so it sits **off the board**, beside the row-24 end, on wires about 6–8 cm long.

![charger board](renders/build-charger.png)

1. On the bench first: remove the small **103** (10 kΩ) resistor beside the **THERM** label and solder the 10 kΩ NTC's
   two leads to its pads (the NTC gets taped to the cell later). If its leads don't reach the cell, extend them with
   **30 AWG silicone stranded wire** and heat-shrink each joint.
2. The bulk capacitor has its own footprint on the charger, at the top right (the outline with **+** on one side):
   **long leg into the + hole**, stripe side into the other. To make it lie on its side, bend both leads 90° about 2 mm
   from the body first (hold the lead with pliers at the body so the bend doesn't strain it).
3. **Power wires (they carry the battery and motor current): 6 pieces of 22 AWG stranded insulated wire**, 6–8 cm each:
   **red for the three + wires, black for the three − wires** (or the white two-conductor wire with a red / black
   heat-shrink band at both ends). Solder one end of each to the charger's PWR +, PWR −, BATT +, BATT −, LOAD + and LOAD − holes. Mark the +
   wires before you start.
4. **Crimp JST-XH pins** on the other ends and push them into the housings, matching the headers from step 4:
   - **3-pin housing (GND):** PWR − / BATT − / LOAD −, in that order, to match a21 / a22 / a23.
   - **2-pin housing (charger +):** BATT + on the d19 side, PWR + on the e19 side.
   - **2-pin housing (LOAD +):** LOAD + in either position (both pins of that header are battery +).
   Check each one with the meter against the board before plugging in: a swapped + and − here can damage parts.
5. Leave the small edge pads (CE, TE, PROG2, SEL) unconnected. The board has no STAT pad; the ESP watches the input
   voltage instead (the input-power 1 MΩ pair from step 1).

(Pad names assumed from the Adafruit-style board: check them against the real board before wiring.)

| Charger pad | Board hole | Net |
|---|---|---|
| PWR + (input) | e19 | PWR node: D1 + D2 cathodes, zener; plugs into the 2-pin JST d19-e19 |
| PWR - / GND | a21 | GND rail; plugs into the 3-pin angled JST a21-a23 |
| BATT + | d19 | battery pin B+ (bridged from b19) (the cell reaches the VBAT rail only through the charger); plugs into the 2-pin JST d19-e19 |
| BATT - | a22 | GND rail; plugs into the 3-pin angled JST a21-a23 |
| LOAD + (output) | j20 | VBAT rail; plugs into the 2-pin JST j20-j21 |
| LOAD - | a23 | GND rail; plugs into the 3-pin angled JST a21-a23 |
| THERM | (NTC) | remove the 103 (10 k) resistor beside the THERM label; NTC across its two pads, taped to the cell |
| CE, TE, PROG2, SEL (edge pads) | - | leave unconnected (board defaults); the board has no STAT pad, status is on its LEDs |

## Step 17: checks, then plug in the ESP and the USB-C board

**You need:** multimeter, 1 × ESP32-C6 SuperMini (its male pins soldered on), 1 × USB-C breakout (its 6 male pins soldered on), 1 × 18650 cell with JST-XH plug.

![finished top](renders/build-done-top.png)

![finished underside](renders/build-done-under.png)

The battery + rail (battery + j11–j24) gets most of its connections from the top: the three port leads and the charger's LOAD +
wire (j20). The cell never connects to the rail directly: battery + (b19) goes to the charger's BATT + pad and the
charger feeds the rail from LOAD +.

With the ESP and the USB-C board still **out** of their sockets:

1. Meter, beep mode, no power: GND (a13) to battery + (j11): **no beep**. GND to 5V (a3): no beep. GND to 3V3 (c3):
   no beep. GND to the battery + pin (b19): no beep. GND to the PWR node (e19): no beep.
2. Plug the ESP into its socket (chip side up, USB-C over the column-a edge) and the USB-C board into its socket
   (its USB-C pointing out past row 24). Then plug USB into the **ESP's own** USB-C only (battery unplugged): its LED
   should light; upload the test sketch.
3. Unplug USB, then push the cell's plug onto a19/b19 (**red on b19**). Measure j11 to a13: about the cell voltage
   (3.0–4.2 V).
4. Never plug USB into the ESP and the battery at the same time unless D3 is fitted.
