# Solar housing

One flat white tray that holds **three 6 V 0.8 W panels** (70 × 70 mm) in a row, wired in parallel, and sticks flat
on the window.

- **Size:** 222.4 × 82.4 × 5.2 mm, about 47 g of PLA.
- **Print:** `hardware/mechanical/stl/solar/solar_housing.stl`, as it lies (back on the bed). No supports.
- **Built by:** `python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_solar.py --timeout 600`
  (measurements are in the `S` table at the top).

## How it goes together

1. **Wire the panels in parallel.** Keep the plug on panel A. Solder B's red to A's + pad and B's black to A's −
   pad, then C to B the same way. Check each panel in the sun first (+6 to 7 V, red on +).
2. **Lay the wires in the channel.** The 10 mm channel runs behind the panels, 10 to 20 mm below their top edge,
   over the solder bumps. A's lead leaves through the notch at the right end.
3. **Glue the panels in, face up.** They sit on a 5 mm ledge round each panel's edge, butted edge to edge, with their
   faces flush with the rim. The back is open inside the ledge to save weight.
4. **Tape the rim to the window.** Put double-sided tape on the 6 mm rim, panel side, and press it flat on the glass.
   Turn it in its own plane to put the wire exit on the side you want.

The plug goes in J8 on the controller board: black on pin 1 (−), red on pin 2 (+).
