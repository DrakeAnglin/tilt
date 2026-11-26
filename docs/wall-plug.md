# Wall plug

**Optional.** If a cord has to pass through a wall or trim, for example between two windows, drill a hole for it and
cover each side of the hole with a white printed plug. The plug hides the rough edge of the hole and leaves a U slot
for the cords.

## What you need
- A **5/8 in (16 mm)** drill bit. A spade bit is fine in drywall and wood.
- One printed plug for each side of the hole: `hardware/mechanical/stl/plug/wall_plug.stl`.

## Fitting
1. Drill the 5/8 in hole straight through.
2. Run the cords through the hole with their RJ12 plugs on. An RJ12 plug fits through a 5/8 in hole.
3. Lay the cords flat at the bottom of the hole. Slide a plug over them from the side, so the cords sit in its U slot
   with the slot at the bottom.
4. Push the plug into the hole until its cap sits flat on the wall. Then do the other side.

The slot holds **two flat RJ12 cords** (about 6.6 × 3.3 mm each), one on top of the other. The shank is only 6 mm
long, so a plug fits on each side of a single sheet of 1/2 in drywall. To take a plug out, pull it out by the cap.

## Size
- Cap: 22 mm across and 1.2 mm thick, with a 45 degree bevel round the face. It still covers a hole that came out
  17 mm across.
- Shank: 15.8 mm across (the drill's size), hollow, with 10 pointed ribs (12 drawn, the slot cuts 2 away). The rib
  tips reach 18 mm across, so they dig into the gypsum even where the bit left the hole loose and ragged.
- U slot: 7.2 mm wide, the whole height of the plug.

## Print
- White PLA (or very light gray), cap face down on the bed. No supports: the face bevel is 45 degrees.
- About 1.1 g each.

## Built by
`python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_plug.py`. It checks that two flat cords fit in the
slot without touching the plug, that the ribs grip both a true 5/8 in hole and a loose 17 mm one, and that the plug
is one piece, then exports the STL. Sizes are in the `S` table at the top of the script.
