# Controller PCB (v2, carrier board)

Replaces the hand-wired perfboard. Same core circuit as the dev board, on a 2-layer PCB: the **ESP32-C6 SuperMini** and
the **USB-C breakout** plug into female header sockets; the **18650**, the **MCP73871 charger module** and the optional
**solar panel** plug into three *different* JST headers; the **three RJ12 jacks** sit on the board edge with a fuse and
protection resistors behind each. Everything is through-hole and hand-soldered; there is no hand wiring.

![top, 3D](controller/render-top.png)

| | |
|---|---|
| Size | 47 × 125 mm, T-shaped: a 47 mm strip at the port end carries the jacks and their fuses / resistors, the 27 mm body runs alongside the 18650 |
| Layers | 2, GND poured on both and stitched with ~80 vias; 1 mm motor-return GND track from the jacks to the battery / charger GND |
| Tracks | 0.3 mm signals, 0.6–0.8 mm power; 0.2 mm clearance; vias 0.7 / 0.35 mm |
| Checks | KiCad 10: **DRC 0 violations, 0 unconnected; ERC 0 violations; schematic ↔ board parity 0 differences** |
| Files | [schematic (PDF)](controller/controller-schematic.pdf), [controller.kicad_pro](controller/controller.kicad_pro) (open in KiCad), [parts list (CSV)](controller/controller-bom.csv), [controller-pcbway.zip](controller/controller-pcbway.zip) (Gerbers + drill: upload this) |

Generated, not drawn: [netlist.py](netlist.py) holds the parts and connections; [schematic.py](schematic.py) writes the
schematic from it; [board.py](board.py) places the parts, routes the copper with [router.py](router.py), pours and
stitches GND and adds the silkscreen. Rebuild:

```bash
python3 hardware/pcb/schematic.py
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 hardware/pcb/board.py
```

## What changed from v1 (after the peer review)
| Review item | v2 |
|---|---|
| Battery plug fits the wrong 2-pin header (could short the cell) | Three different connectors: battery JST-XH 2, charger JST-XH **6**, solar JST-**ZH** 2. The charger header is pinned **GND, BATT+, –, LOAD+, –, PWR+** so the battery's 2-pin plug, pushed into it at any offset, either lands correctly or touches one live pin: never a short |
| EN floating at boot | 100 kΩ pull-down on each EN |
| Cable lines straight into ESP pins | 220 Ω series on IN1 / IN2; **10 Ω** on EN (EN also powers the tilter's AS5600, ~6.5 mA: 220 Ω would starve it) |
| No per-port overcurrent protection | 0.75 A resettable fuse (Bel Fuse 0ZRE0075FF) on each port's battery + |
| No bulk capacitance near the jacks | 470 µF on battery + |
| Angle shifts while a motor runs | Firmware note ([firmware/README.md](../../firmware/README.md)): final reading with the motor stopped |
| Zener heat in sun | 5 W zener (1N5341B, 6.2 V) |
| Input-power divider unfiltered | 100 nF added |
| GND pour in islands | ~80 stitching vias; filter-cap GND pads solid to the pour |
| Motor return through the analog ground | Dedicated 1 mm GND track: jacks → bulk cap → battery / charger GND |
| No test points | Pads for BAT+, 5V, 3V3, PWR, GND |
| ESP USB unreachable | ESP turned: its USB faces end B over low parts, so a cable fits with the ESP plugged in |
| No schematic | Real KiCad schematic, ERC clean, parity-checked against the board |
| Brown-out ~15 % early (Schottky to the ESP's 5V) | **Kept.** The real fix is an ideal-diode IC or a P-MOSFET with a gate driver, which are surface-mount; planned for the integrated v3 |

## Order from PCBWay
1. pcbway.com → PCB Instant Quote → **Quick-order PCB** → upload [controller-pcbway.zip](controller/controller-pcbway.zip).
2. **2 layers, FR-4, 1.6 mm, 1 oz copper, HASL lead-free**, min track / spacing **6/6 mil**, min hole **0.3 mm**,
   solder mask green (or white to match the build), silkscreen white, **quantity 5**.
3. Check the quote before paying (roughly $5–20 for 5 plus shipping). Bring one board up fully before building three.

## Parts for one board
| Part | Qty | Have it? |
|---|---|---|
| This PCB | 1 | order |
| ESP32-C6 SuperMini (male pins on) / USB-C breakout (Cermant, male pins on) | 1 / 1 | yes |
| Female header socket 10-way / 6-way | 2 / 1 | yes (kit) |
| **RJ12 PCB jack, Amphenol 54601-906WPLF** (or another with this footprint) | 3 | **buy** |
| **Resettable fuse 0.75 A hold, radial, Bel Fuse 0ZRE0075FF** (5.1 mm pin spacing) | 3 | **buy** |
| **Electrolytic 470 µF 10 V+, 8 mm dia, 3.5 mm pitch** | 1 | **buy** |
| **Zener 1N5341B (6.2 V 5 W)** | 1 | **buy** |
| **JST-XH header 2-pin (B2B-XH-A) / 6-pin (B6B-XH-A), vertical**, + 6-pin housing and 4 crimp pins | 1 / 1 | **buy** (XH kit) |
| **JST-ZH header 2-pin (B2B-ZR), vertical** (matches the solar extension plugs) | 1 | **buy** |
| Resistors: 1 MΩ ×4, 1 kΩ ×3, 220 Ω ×6, 10 Ω ×3, 100 kΩ ×3 | 19 | yes (kit) |
| Ceramic capacitors: 100 nF ×5, 10 µF ×1 | 6 | yes (kit) |
| 1N5819 | 3 | yes |
| M3 screws (3 mounting holes) | 3 | yes |

## Charger harness (one 6-pin JST-XH plug)
| Header pin | Charger pad | Wire |
|---|---|---|
| 1 | GND (any of PWR−, BATT−, LOAD−: they're common on the module) | black 22 AWG |
| 2 | BATT + | red 22 AWG |
| 3 | – (leave empty) | |
| 4 | LOAD + | red 22 AWG |
| 5 | – (leave empty) | |
| 6 | PWR + | red 22 AWG |

## Soldering order (lowest parts first)
1. Resistors (19, flat, any way round). The four behind each jack stand in a row: 220, 10, 100k, 220 (see the silkscreen).
2. Diodes: the band on the side marked **K**. 1N5819 ×3, zener (big one, "6V2 5W Z").
3. Ceramic capacitors (6), then the 470 µF (**+** marked; the long leg is +).
4. Fuses (3, any way round), test pads.
5. Sockets: 2 × 10-way for the ESP (push onto the ESP's pins, set it in, solder, lift it out), 6-way for the USB-C board.
6. JST headers (3), RJ12 jacks (3).
7. Meter checks, nothing plugged in: GND to BAT+, 5V, 3V3 and PWR pads: no beep.
8. Plug in the ESP (**chip up, USB toward the bottom edge**, 5V row on the left), the USB-C board (socket out past the
   bottom edge), the charger harness, the battery. 5V and 3V3 test pads should read about 3.7–4.0 V and 3.3 V.

## Pin plan (v2)
| Port | IN1 | IN2 | EN | Angle (ADC) |
|---|---|---|---|---|
| 1 | GPIO14 | GPIO18 | GPIO7 | GPIO6 |
| 2 | GPIO19 | GPIO20 | GPIO5 | GPIO4 |
| 3 | GPIO16 (TX) | GPIO17 (RX) | GPIO1 | GPIO2 |

Battery voltage GPIO3, input-power voltage GPIO0. RJ12 pinout (both ends): 1 battery +, 2 IN1, 3 GND, 4 angle, 5 EN, 6 IN2.

## Check before ordering
- ESP32-C6 SuperMini pin rows 15.24 mm apart, pin 1 (5V / TX) at the USB end.
- USB-C breakout pins VBUS, GND, CC1, D−, D+, CC2 at 2.54 mm.
- The RJ12 jack and the PTC you buy match their footprints (RJ12: Amphenol 54601; PTC: 5.1 mm pin spacing).
- The box (ControllerV4) still has to be redrawn around this board.

## Rebuild the files
```bash
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K sch erc hardware/pcb/controller/controller.kicad_sch
$K pcb drc --schematic-parity hardware/pcb/controller/controller.kicad_pcb
$K pcb export gerbers --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts --subtract-soldermask -o hardware/pcb/controller/gerbers/ hardware/pcb/controller/controller.kicad_pcb
$K pcb export drill --format excellon --excellon-separate-th -o hardware/pcb/controller/gerbers/ hardware/pcb/controller/controller.kicad_pcb
```

## Later (v3)
- Fully integrated: charger chip, USB-C, ESP32-C6 module and an ideal-diode supply on the board (PCBWay assembly).
- Tilter board: AS5600 + DRV8833 + RJ12 jack on one small board.
