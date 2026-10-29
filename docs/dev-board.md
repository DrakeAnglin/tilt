# Controller dev board and case

**Current: ControllerV2** (hole-accurate). V1 below is kept for history; its layout could not be wired (breakouts
and the charger under the perfboard, 18 loose port wires).

## ControllerV2
Generator: [ControllerV2.py](../hardware/mechanical/fusion/ControllerV2/ControllerV2.py). Run it with plain Python
for the checks and the hole map ([ctrl-v2-holemap.svg](renders/ctrl-v2-holemap.svg)); run
`tools/fusion_controller_v2.py` through the bridge for the Fusion model, the exact B-rep interference check and the
renders.

![board](renders/ctrl-v2-board-iso.png)
![lid off](renders/ctrl-v2-open.png)

**Part sizes are from the listing photos and drawings** (ESP32-C6 26 × 18 drawing; DRV8833 18.5 × 16; USB-C 22.1 ×
13.05; RJ12 board 19.4 × 19.9 and jack 13.5 × 14.7 scaled from the quarter photo with the 2.54 pin row as the
ruler; charger ≈ 19.6 × 18.3 scaled from its header; 18650 pack 68.1 × 19.05). Still unmeasured: the ESP32's
row-to-row spacing (modelled 15.24, the next grid option 17.78 is kept free) and the RJ12 jack height (13.0).

### Numbers (all checked by the script)
| | |
|---|---|
| Case | **136.4 × 46.0 × 23.0 mm** outer, wall/floor/lid 1.2 |
| Perfboard | one piece cut from the 9 × 15 cm board along hole rows (needs 42 × 16 holes: 107 × 41 mm): ear A 10 × 16 holes, strip 28 × 9, ear B 4 × 9; **448 holes, 100 used** |
| Heights (Z from rail floor) | hung breakouts 2.7–4.3 · perfboard 6.8–8.4 · module PCBs from 10.9 · tallest top part 16.9 (XH plug) · lid underside 21.8, rod groove 19.0 |
| Under the strip | 5.6 mm from the floor to the board's underside for wiring and trimmed pin tails |
| Pins | every pin on a hole of the cut outline, no hole shared |
| Overlaps | none (plain-Python box check and Fusion B-rep check, incl. case, lid, rod sweep, plugs) |
| Tightest top-side joint | 1.19 mm from a joint to the next body (USB-C VBUS ↔ zener): solder the breakouts **first** |
| Module joints over something | 0 (every module pin is soldered underneath with nothing below it) |

### Build order
1. **Breakouts:** file 1 mm off the USB-C board's end (the end away from VBUS). Push straight headers (long side up)
   through the 3 RJ12 boards and the USB-C board, set them under the perfboard at rows 2 / 36 / 41 (hole map), solder
   on top. Trim their pins under the boards to 1.5 mm.
2. **Charger:** stick it down on 1 mm foam tape (top side, rows 21–29). Before that: remove its THERM resistor and
   solder the NTC leads there; tin its PWR / BATT / LOAD pads.
3. **Modules:** DRV8833 ×2 (cut J2 first) and the ESP32-C6 (LEDs removed) on straight headers, soldered underneath.
4. **Passives on top:** RC filters next to each jack, the divider + D3 along col 8, bulk cap, D1/D2/zener upright on
   ear B, 2 header pins for the battery's XH plug (2.5 vs 2.54 pitch: it pushes on).
5. **Wiring:** point-to-point underneath with 30 AWG; the charger's pads to the holes beside it on top. Bench test
   with the battery plugged in.
6. **Case:** board drops into the tray (jacks over their pegs, strip on 4 posts), battery into its saddles and onto
   its pins, solar lead into the open slot, lid snaps on.

### Battery level
The 1 MΩ / 1 MΩ divider from BATT+ to GPIO3 (with 100 nF) reads the cell voltage. Firmware turns it into a percentage
and reports it through Matter's Power Source cluster, so Apple Home and Alexa show the battery level (and can warn
when it's low). The charger's STAT pad can also report "charging" / "charged".

---

# ControllerV1 (superseded)

One controller = one ESP32-C6 SuperMini driving up to 3 tilters. This is the soldered dev-board stage: bought
modules on a perfboard strip, in a printed case that sits on the headrail floor under the tilt rod. The Fusion model
is built by [ControllerV1.py](../hardware/mechanical/fusion/ControllerV1/ControllerV1.py):

```bash
python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v1.py --timeout 600
```

It opens a new document, mocks every part at its listed / measured size, runs an interference check between all
parts (including the tilt rod's sweep) and saves renders to `docs/renders/ctrl-v1-*.png`.

![in the rail](renders/ctrl-v1-in-rail.png)
![lid off](renders/ctrl-v1-open.png)

## Case
- **Outer 118.2 × 46.0 × 23.0 mm.** 46 mm wide drops in between the rail lips (46.5 mm opening) and sits on the rail
  floor, centred. A groove along the lid (|Y| < 4.5 mm, top at Z 20.2) leaves 0.97 mm under the tilt rod's sweep
  (4 mm square rod at Z 24 sweeps down to Z 21.17).
- Two parts: **tray** (floor, walls, all supports) and **lid** (snap skirts with 4 bumps into windows in the long
  walls, plus fingers that hold down the jacks, the battery and the perfboard edge). No screws.
- **End A:** RJ12 #1 (room side) and RJ12 #2 (back side). **End B:** RJ12 #3 (back side), USB-C (room side), solar
  pigtail hole (Ø3.5).
- Cords run along the rail both ways, so blinds on either side plug into the nearest end.

## Layout (X along the rail, Y across, −Y = room side, Z up from the rail floor)
| Part | Where | Height |
|---|---|---|
| RJ12 breakouts ×3 (20.3 × 13.1 board, jack overhangs 12.9) | on 2 pegs + collars, jack face on the end wall | board 4.2–5.8, jack to 17.5 |
| USB-C breakout (≈ 18 × 15) | end B, room side, on two rails | board 4.2–5.8 |
| 18650 (18.6 × 69) | room side, X 28.5–97.5, two saddles | to 20.1 |
| Perfboard strip **24 × 82** | back side, X 18–100, on a wall ledge + 3 posts | 9.0–10.6 |
| DRV8833 ×2, ESP32-C6 | on the perfboard, header spacers 2.5 | to ≈ 17.4 (ESP's USB-C) |
| Electrolytic (Ø8 × 13), 10 µF, 100 nF ×3 | perfboard, X 84–97 | lying down |
| Diodes, zener, resistors, 100 nF | strip along the perfboard's room-side edge | low |
| MCP73871 charger (20 × 19) | **under** the perfboard, X 70–90, on two ribs | 2.2–4.7 |

The perfboard sits over the back halves of the RJ12 boards, so **solder the RJ12 and USB-C wires first**, then
place the perfboard. Cut the strip from the largest board in the kit (24 mm = 9 hole rows).

## Pin plan (header pins only; physical order to confirm against the board)
The SuperMini has 9 pins down each side plus pads on the bottom edge (the "Do not connect USB and battery without a
diode" warning on its 5V pin is handled by D3).

| GPIO | Use |
|---|---|
| 0, 1, 2 | Angle sensor 1/2/3 (ADC, 1 kΩ + 100 nF filter) |
| 3 | Battery voltage (1 MΩ / 1 MΩ divider from BATT+, 100 nF) |
| 4, 5, 6 | Sensor 1/2/3 power (3V3, one on at a time) |
| 18, 19 | Motor 1 (DRV8833 #1 IN1/IN2) |
| 20, 14 | Motor 2 (DRV8833 #1 IN3/IN4) |
| 16, 17 | Motor 3 (DRV8833 #2 IN1/IN2); TX/RX are free because logging goes over USB |
| 15 | DRV8833 sleep (ULT on both; on-board LED removed) |
| 12, 13 | USB D−/D+ (bottom pads), wired to the case's USB-C breakout |
| 7 | Charger STAT (bottom pad, optional) |
| 8 | RGB LED: remove the LED; spare (strapping pin) |
| 9 | Boot button; spare |

## Wiring list
**Power**
- USB-C breakout VBUS → D1 (1N5819) → charger PWR+. GND → PWR−. D+/D− → ESP GPIO13/GPIO12, so the case's USB-C
  both charges and programs / logs the ESP.
- Solar pigtail (ZH socket, + red) → D2 (1N5819) → charger PWR+. **6.2 V zener** across PWR+/PWR− (band to PWR+).
- 18650 → charger BATT+/BATT− (cut the XH plug, splice a JST-PH 2-pin lead, heat-shrink).
- 10 kΩ NTC taped to the cell → charger THERM (remove the board's fixed THERM resistor).
- Charger LOAD+ → D3 (1N5819) → ESP **5V** pin; LOAD+ → both DRV8833 **VCC** (motors run from the battery);
  electrolytic across LOAD+/GND; 10 µF at the ESP 5V pin.

**Each tilter port (RJ12 n = 1, 2, 3)**
| RJ12 pin | Net |
|---|---|
| 1 | Motor + (DRV OUT) |
| 2 | Motor − (DRV OUT) |
| 3 | GND |
| 4 | Angle OUT → 1 kΩ → ADC GPIO (0/1/2), 100 nF to GND |
| 5 | 3V3 sensor power ← GPIO 4/5/6 |
| 6 | GND |

Ports 1 and 2 use DRV8833 #1 (OUT1/2, OUT3/4); port 3 uses DRV8833 #2 OUT1/2. DRV8833 #2's second channel is a
spare (lift later).

## Before soldering (check on arrival)
- **DRV8833:** cut the **J2** pad on the back of each board, or the ULT (sleep) pin does nothing (per the listing).
  Confirm the pin order on the silkscreen.
- **ESP32-C6 SuperMini:** measure the row spacing (assumed 0.6") and confirm which pads are on the bottom edge.
  Remove the RGB LED (GPIO8) and the power LED.
- **Charger:** confirm the pads: PWR, BATT, LOAD, THERM, PROG and the 5-pin header (the photos show no USB or DC
  jack).
- **USB-C breakout:** measure the board (modelled 18 × 15); the case opening and rails follow it.
- **RJ12 cords:** pin 1 → pin 1 continuity on every cord.
- **Solar panel:** open-circuit voltage behind glass.

## Still open
- **Where in the rail:** the case needs 118 mm of rail with nothing on the rod in the way (tilt drums, cord
  spools, spring motors). Need the free length and position in each controller's headrail.
- Solar panel (70 × 69 mm) is taller than the rail face (≈ 38 mm), so it can't go on the rail. It needs its own
  white frame on the glass (suction cup or tape) with the extension lead to the case. To design next.
- The boost module is for the bench comparison only and has no place in the case.
