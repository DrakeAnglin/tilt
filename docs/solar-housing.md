# Solar housing

White tray sections and an end cap that hold **1 to 6 panels** (6 V 0.8 W, 70 × 70 mm) in a row, wired in parallel,
and stick flat on the window. Use more panels where the window gets little light: in a window with no direct sun one
panel gives only about 1 mA (direct sun: about 106 mA, measured 2026-11-26).

## Pieces for each count

Every set is 86.2 mm wide and 7.0 mm thick. A section holds at most 3 panels (about 232 mm, so it fits the bed); more
panels take a second section that locks onto the first.

| Panels | Length | Print |
|---|---|---|
| 1 | 101 mm | `start_1` + `cap` |
| 2 | 171 mm | `start_2` + `cap` |
| 3 | 242 mm | `start_3` + `cap` |
| 4 | 312 mm | `start_2` + `add_2` + `cap` |
| 5 | 383 mm | `start_3` + `add_2` + `cap` |
| 6 | 453 mm | `start_3` + `add_3` + `cap` |

The files are `hardware/mechanical/stl/solar/solar_<piece>.stl` (wires out the right end) and
`solar_<piece>_wires_left.stl` (the mirror image: wires out the left end). A set must be all one side.

- **Print:** each piece as it lies, back on the bed. No supports: the lips are 45 degrees, and nothing bridges. Keep
  the slicer's elephant-foot compensation on (Bambu's default), or the puzzle tabs bind at the bottom. About 0.42 g
  of PLA per mm of section if printed solid; less with normal infill.
- **Bambu Studio:** `python3 tools/bambu_solar.py <panels> [--left]` packs one set on a plate (H2D 0.4 nozzle,
  0.20 mm Standard, white PLA, no supports) as `solar_housing_<panels>[_wires_left]_H2D.3mf`. The 3- and 6-panel
  projects are in the folder.
- **Built by:** `python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_solar.py --timeout 1500`. It builds
  and checks every count (panels slide in across every joint, joints lock, lips hold, nothing pokes out) and exports
  every piece. Measurements are in the `S` table; `PIECES` sets the sections per count.
- **Fit:** 70.5 mm of slot per panel along the row (real panels run about 70.3: three came out 0.9 mm over 210),
  0.2 mm in all from top to bottom across the panels, and 0.05 mm front to back under the lips, so the
  panels can't rock. Sockets have 0.15 mm a side. Every section's slot has a small 45 degree lead-in at its right end,
  so a panel can't catch on a joint that prints a little high or low.

## How it goes together

1. **Wire the panels in parallel.** Solder each panel's red to the next one's + pad and its black to the − pad.
   Check each panel in the sun first (+6 to 7 V, red on +). The panel with the plug goes in last (at the cap end).
2. **Join the sections.** Press the `add` section down onto the `start` section's two round tabs.
3. **Slide the panels in from the cap end**, face up, under the 45 degree lips along the top and bottom. Push each one
   all the way along. Lay the wires in the 10 mm channel behind them (10 to 20 mm below the panels' top edge, over
   the solder bumps).
4. **Drop the cap on.** Lay the two wires in the small slot on the cap's back, then press the cap down onto the last
   section's tabs. It locks the panels in.
5. **Tape it to the window.** Double-sided tape on the window face of the left end and of the cap (15 mm pads; the
   8 mm rails take tape too), then press it flat on the glass. The panels sit 1.8 mm behind the window face.

The plug goes in J8 on the controller board: black on pin 1 (−), red on pin 2 (+).
