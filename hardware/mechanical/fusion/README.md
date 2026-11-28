# Fusion 360 scripts

| Generator | Builds | Run |
|---|---|---|
| [`Tilter/Tilter.py`](Tilter/Tilter.py) | The tilter: every printed part, with collision, gear-mesh and assembly checks | `tools/fusion_tilter.py`, `tools/fusion_thin.py` |
| [`Controller/Controller.py`](Controller/Controller.py) | Controller box for the PCB | `tools/fusion_controller.py` |
| [`ControllerV3/ControllerV3.py`](ControllerV3/ControllerV3.py) | Fit study for the PCB v3 box (mock-up board with every part; no print files yet) | `tools/fusion_controller_v3.py` |
| [`Hub/Hub.py`](Hub/Hub.py) | Tilt Hub box | `tools/fusion_hub.py` |
| [`Hub/Hub.py`](Hub/Hub.py) | Tilt Hub box, printed round the ESP | `tools/fusion_hub.py` |

Run through the bridge: `python3 hardware/mechanical/fusion/fusion.py exec tools/<script>.py --timeout 1800`.

Shared pieces:
- [`fits.py`](fits.py): fastener and fit sizes (M3, inserts, pegs, rod, rail) used by both generators.
- [`Tilter/gear_geom.py`](Tilter/gear_geom.py): the tilter's dimensions and pure geometry (no Fusion);
  [`Tilter/tilt_base.py`](Tilter/tilt_base.py): its Fusion helpers and the worm builder.
- [`fusion_kit.py`](fusion_kit.py): fresh document, hide sketches and planes (used by the drivers in `tools/`).
- `python3 -m unittest hardware/mechanical/fusion/test_geometry.py` checks the gear train and fits without Fusion.

`fusion.py exec FILE` gives the code `__file__` and `REPO` (the repo root). Every build's result has `ok` and
`failures`.

## Review after every change
A change to a printed part is not done until its build comes back `ok`. Every build runs these two:

- **Collision check:** no two parts overlap.
- **Stays-inside check** (`fusion_kit.stays_inside`): nothing reaches outside the outside shape the part was designed
  to. Each generator states that shape (the box's `outline`; for the tilter, the housing's cross-section). It catches
  what a collision check can't: a boss, saddle or screw that comes out through a wall or the floor, or a feature added
  after a bevel was cut. Only things meant to stick out (a plug, a cable) are on its skip list.

A new enclosure gets both checks before its first print file is written.

## FusionBridge: lets Claude Code drive Fusion
An add-in that listens on **127.0.0.1:7655 only** and requires a random token, rewritten each time the add-in starts
(`~/.fusion_bridge/token`, readable only by you).

```bash
python3 hardware/mechanical/fusion/fusion.py ping
python3 hardware/mechanical/fusion/fusion.py shot /tmp/view.png --view iso
python3 hardware/mechanical/fusion/fusion.py exec -c "result = [o.name for o in root.occurrences]"
```

Install once: Fusion, **Shift+S → Add-Ins → +** → *Script or add-in from device* → select the `FusionBridge` folder → **Run**
(check **Run on Startup** if wanted). It runs whatever code it is sent with your Fusion session's permissions, so only run
it while you want Claude driving Fusion. A modal dialog open in Fusion blocks requests until it is closed.
