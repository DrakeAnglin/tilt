# Controller PCB (v1, carrier board)

Replaces the hand-wired perfboard. Same circuit as the dev board (all its nets were checked there), on a 2-layer PCB:
the **ESP32-C6 SuperMini** and the **USB-C breakout** plug into female header sockets, the **MCP73871 charger module**,
the **18650** and the optional **solar panel** plug into JST-XH headers, and the **three RJ12 jacks** sit on the board
edge. Everything is through-hole and hand-soldered; there is no hand wiring.

![top, 3D](controller/render-top.png)

| | |
|---|---|
| Size | 47 × 113 mm, T-shaped: a 47 mm strip across the port end carries the three jacks, the 27 mm body runs alongside the 18650 |
| Layers | 2 (signals and power on both, GND copper fill on both) |
| Tracks | 0.3 mm signals, 0.6–0.8 mm power; 0.2 mm clearance; 18 vias (0.7 / 0.35 mm) |
| Checks | KiCad 10 DRC: **0 violations, 0 unconnected** |
| Files | [controller.kicad_pcb](controller/controller.kicad_pcb) (open in KiCad), [controller-pcbway.zip](controller/controller-pcbway.zip) (Gerbers + drill: upload this) |

The board is generated, not drawn: [netlist.py](netlist.py) holds the parts and connections, [board.py](board.py) places
them, routes the copper with [router.py](router.py), pours GND, adds the silkscreen and saves the board. To rebuild:

```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 hardware/pcb/board.py
```

Then re-run the DRC and re-export the Gerbers (the commands are in "Rebuild the files" below).

## Order from PCBWay
1. pcbway.com → PCB Instant Quote → **Quick-order PCB** → upload [controller-pcbway.zip](controller/controller-pcbway.zip).
   It reads the size (47 × 113 mm) and layer count from the files.
2. Settings: **2 layers, FR-4, 1.6 mm, 1 oz copper, HASL lead-free**, min track / spacing **6/6 mil** (the board
   uses 0.3 mm / 0.2 mm, well above that), min hole **0.3 mm** (smallest is 0.35 mm), solder mask green (or white to
   match the rest of the build), silkscreen white, quantity 5 (enough for 3 controllers + spares).
3. Leave "different designs" at 1. The T-shape is just the board outline; no extra charge for it.
4. Expect roughly $5–15 for 5 boards plus shipping; check the quote before paying.

## Parts for one board
| Part | Qty | Have it? |
|---|---|---|
| This PCB | 1 | order |
| ESP32-C6 SuperMini (male pins soldered on) | 1 | yes |
| USB-C breakout (Cermant, its 6 male pins soldered on) | 1 | yes |
| 10-way female header socket ("pin stand") | 2 | yes (kit) |
| 6-way female header socket (cut from a strip) | 1 | yes (kit) |
| **RJ12 6P6C PCB jack, Amphenol 54601-906WPLF** (tab down; or another jack with the same footprint) | 3 | **buy** (DigiKey / Mouser) |
| **JST-XH header, 2-pin vertical (B2B-XH-A)**: battery, charger +, charger LOAD +, solar | 4 | **buy** (JST-XH kit) |
| **JST-XH header, 3-pin vertical (B3B-XH-A)**: charger GND | 1 | **buy** (JST-XH kit) |
| Resistor 1 kΩ / 1 MΩ | 3 / 4 | yes (kit) |
| Ceramic capacitor 100 nF (104) / 10 µF (106) | 4 / 1 | yes (kit) |
| 1N5819 diode / 6.2 V zener | 3 / 1 | yes |
| M3 screws for the 3 mounting holes | 3 | yes |

The RJ12 breakout boards are no longer needed on the controller side; they stay in the tilters. The cheap Amazon RJ12
jacks often have different pin spacing: check a jack against the footprint (pins on a 1.27 mm stagger, two 3.25 mm
plastic posts 10.16 mm apart) before buying a different one.

## Soldering order (lowest parts first)
1. **Resistors** (7, lying flat, any way round): 1 kΩ at R5–R7 (under the ESP outline), 1 MΩ at R1–R4.
2. **Diodes** (4): the silver band goes on the side marked **K** on the silkscreen. 1N5819 at D1–D3, zener at D4 ("6V2 Z").
3. **Capacitors** (5, any way round): 100 nF ×4, 10 µF at the top of the ESP outline.
4. **Sockets**: the two 10-way strips for the ESP (push them onto the ESP's pins, set it in, solder, lift the ESP out),
   the 6-way strip for the USB-C board at the bottom edge.
5. **JST headers** (5), **RJ12 jacks** (3, their posts click into the board).
6. Meter checks with nothing plugged in: GND to battery +, to 5V and to the charger + pins: no beep.
7. Plug in the ESP (**chip up, USB toward the ports**, TX row on the left), the USB-C board (its socket out past the
   bottom edge), the charger's three plugs, the battery.

## Pin plan
The motor IN pins differ from the dev board: each port's traces stay on its own side of the ESP.

| Port | IN1 | IN2 | EN | Angle (ADC) |
|---|---|---|---|---|
| 1 | GPIO16 (TX) | GPIO17 (RX) | GPIO1 | GPIO0 |
| 2 | GPIO20 | GPIO19 | GPIO5 | GPIO2 |
| 3 | GPIO18 | GPIO14 | GPIO7 | GPIO4 |

Battery voltage on GPIO3 (1 MΩ / 1 MΩ + 100 nF), input-power (USB / solar) voltage on GPIO6 (1 MΩ / 1 MΩ). RJ12
pinout, both ends: 1 battery +, 2 IN1, 3 GND, 4 angle, 5 EN, 6 IN2.

## Check before ordering
- **ESP32-C6 SuperMini pin rows 15.24 mm apart** (the inner holes, as on the dev board) and pin 1 = 5V / TX at the USB end.
- **USB-C breakout pin order** VBUS, GND, CC1, D−, D+, CC2 at 2.54 mm: matches the Cermant board's printing.
- **The RJ12 jack** you buy matches the Amphenol footprint.
- **Charger plugs**: J5 is BATT + (pin 1) / PWR + (pin 2); J7 is PWR − / BATT − / LOAD −; J6 both pins LOAD +.
- The box (ControllerV4) still has to be redrawn around this board.

## Rebuild the files
```bash
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K pcb drc hardware/pcb/controller/controller.kicad_pcb
$K pcb export gerbers --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts --subtract-soldermask -o hardware/pcb/controller/gerbers/ hardware/pcb/controller/controller.kicad_pcb
$K pcb export drill --format excellon --excellon-separate-th -o hardware/pcb/controller/gerbers/ hardware/pcb/controller/controller.kicad_pcb
```

## Later
- Fully integrated version: charger chip, USB-C and the ESP32-C6 module on the board (PCBWay assembly).
- Tilter board: AS5600 + DRV8833 + RJ12 jack on one small board, replacing three breakouts and their wiring.
