# Solar housing

A white tray and an end cap that hold **three 6 V 0.8 W panels** (70 × 70 mm) in a row, wired in parallel, and stick
flat on the window.

- **Size:** 240.1 × 82.2 × 7.0 mm together. Tray about 90 g, cap about 10 g of PLA if solid (less with normal infill). The back is solid, so the panel backs and their labels do not show.
- **Print:** `hardware/mechanical/stl/solar/solar_tray.stl` and `solar_cap.stl` (wires out the right end), or
  `solar_tray_wires_left.stl` and `solar_cap_wires_left.stl` (the mirror image: wires out the left end). Each as it
  lies, back on the bed. No supports: the lips are 45 degrees, and nothing bridges. Keep the slicer's elephant-foot
  compensation on (Bambu's default), or the puzzle tabs bind at the bottom.
- **Fit:** 0.2 mm in all from top to bottom across the panels, and 0.05 mm front to back under the lips, so the
  panels can't rock. The cap's sockets have 0.15 mm a side.
- **Built by:** `python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_solar.py --timeout 600`
  (measurements are in the `S` table at the top).

## How it goes together

1. **Wire the panels in parallel.** Solder B's red to A's + pad and B's black to A's − pad, then C to B the same way.
   Check each panel in the sun first (+6 to 7 V, red on +). The panel with the plug goes in last (right end).
2. **Slide the panels in from the right end**, face up, under the 45 degree lips along the top and bottom. Push each
   one to the left. Lay the wires in the 10 mm channel behind them (10 to 20 mm below the panels' top edge, over the
   solder bumps).
3. **Drop the cap on.** Lay the two wires in the small slot on the cap's back, then press the cap down onto the two
   round puzzle tabs at the tray's end. It locks the panels in.
4. **Tape it to the window.** Double-sided tape on the window face of the left end and of the cap (15 mm pads; the
   rails take tape too), then press it flat on the glass. The panels sit 1.8 mm behind the window face.

For the wire exit on the other side, print the `wires_left` set. The plug goes in J8 on the controller board: black on
pin 1 (−), red on pin 2 (+).
