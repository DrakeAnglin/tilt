# Fusion 360 scripts

## TiltLayout: motorized tilter fit study
Builds reference geometry in the active design: headrail end pocket (with the window-frame limit above it), tilt rod,
factory worm wheel, worm and wand connector, a helical gear on the worm shaft, and an N20 + helical pinion. Then it shows a
fit report (clearances to walls, floor, worm flanges and worm-wheel barrel).

### Run it
1. Fusion: **Utilities → Add-Ins → Scripts and Add-Ins** (Shift+S).
2. Click the **+** next to "My Scripts" → *Script or add-in from device* → select this `TiltLayout` folder.
3. Open a new design, select **TiltLayout**, click **Run**.

### Change it
All sizes are User Parameters starting with `tl_` (**Modify → Change Parameters**). Edit them and run the script again: it
deletes and rebuilds its own `TL …` components. The bodies are reference envelopes (not parametric features). Design the
printed housing around them in your own components. They won't be touched on re-run.

Axes: **X** along the rod (0 = tilter mid-plane, +X toward the first tilt drum), **Y** across the rail (−Y = room side, where
the wand hangs), **Z** up from the rail's inner floor.

Most useful knobs: `tl_worm_angle`, `tl_gear_s` (gear position on the worm), `tl_motor_rot` (swing the motor about the
worm axis), `tl_hg_d`/`tl_hp_d` (helical pitch diameters), `tl_pinion_gap`, and the `tl_n20_*` sizes once the motors arrive.

Checked outside Fusion against a mock API (geometry and report). Not yet run inside Fusion itself.
