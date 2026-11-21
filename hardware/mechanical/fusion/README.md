# Fusion 360 scripts

| Generator | Builds | Run |
|---|---|---|
| [`Tilter/Tilter.py`](Tilter/Tilter.py) | The tilter: every printed part, with collision, gear-mesh and assembly checks | `tools/fusion_tilter.py`, `tools/fusion_thin.py` |
| [`ControllerV5`](ControllerV5/ControllerV5.py) | Controller box for the PCB | `tools/fusion_controller.py` |

Run through the bridge: `python3 hardware/mechanical/fusion/fusion.py exec tools/<script>.py --timeout 1800`.

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
