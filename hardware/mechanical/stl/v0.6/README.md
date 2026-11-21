# Tilter v0.6: planetary test rig (no clutch)

A bare test rig. It only has to prove the motor can turn the blind and the wand still works. No sensor, no cover.

## How it works
One planetary gear set sits on the rod. It has two inputs and one output:

```
Wand  ── worm ── worm wheel ── ring cup (30T inside) ─┐
                                                      ├─ 4 planets ── carrier ── rod
Motor ── 9T ── 20T/9T cluster ── 27T + sun (14T) ─────┘
```

- **Motor on:** the worm can't be turned backward, so the ring stands still. The sun turns the planets, the carrier
  turns the rod.
- **Wand:** the ring turns. The N20's own gearbox holds the sun still. The carrier turns the rod.
- Nothing engages or lets go. No clutch, no reverse nudge. The two inputs can never fight each other.

| | v0.4 | v0.6 |
|---|---|---|
| N20 shaft to rod ratio | much lower | **20.95 : 1** |
| Rod torque (estimate) | about 0.10 N·m | **about 0.77 N·m** |
| Rod speed | faster | 5–7 RPM, about 9 s end to end |
| Wand turns, end to end | about 11.5 | about 17 |

## Print list
Print-ready files are in `print/` (already turned the right way, no supports). Make them again with
`python3 tools/orient_v06.py`.

| File | What | Print |
|---|---|---|
| `ring_cup.stl` | 30T inside ring, hex socket in its floor | floor down |
| `carrier.stl` | square bore for the rod, 4 holes for Ø2 dowels | disc down |
| `planet.stl` | 8T planet, **print 4** | flat |
| `sun_27t.stl` | 27T gear + 14T sun, hollow (rod passes through) | 27T down |
| `cluster.stl` | 20T + 9T on one hub | 20T down |
| `motor_pinion.stl` | 9T, D-bore for the N20 shaft | flat |
| `bearing_plate.stl` | holds the sun, bolts to the case | flat face down |
| `motor_plate.stl` | holds the N20 and the cluster's axle bolt | motor face down |
| `worm_wheel.stl` | new: round bore (free on the rod), hex drives the ring cup | plain end down |
| `case_left.stl` | new lid: bigger bore, no motor socket | outer face down |
| `case_right.stl`, `worm.stl` | **same as v0.4/v0.5: reuse the ones already printed** | |

**One-plate Bambu Studio project:** `tilter_v06_H2D_PLA_PETG.3mf` (make it again with
`python3 tools/orient_v06.py && python3 tools/bambu_v06.py`). H2D 0.4 nozzle, 0.12 mm layers, 4 walls, 40% infill.

Two materials, so every pair that rubs is PLA against PETG:

| PLA (filament 1) | PETG (filament 2, shown gray in the slicer) |
|---|---|
| ring cup, sun + 27T, carrier, motor pinion, motor plate, lid | 4 planets, cluster, worm wheel, bearing plate |

The worm and main half you already printed are PLA, which is why the worm wheel is PETG.

## Hardware
- N20 150 RPM (the one you have) + DRV8833
- 4 × Ø2 × 5.9 mm steel dowels (planet axles) + 1 for the worm's top pin as before
- 5 × M3 × 25 flat-head bolts, 5 × M3 heat-set inserts
- 2 × M1.6 × 4 screws (motor to motor plate)

## Assembly
1. **Main half:** worm wheel and worm in, as before. Lid on. The wheel's hex pokes out of the lid.
2. **Ring cup** onto the hex, open end out.
3. **Carrier:** press the 4 dowels into the disc. Slide the carrier's hub into the wheel. Put the 4 planets on the dowels.
4. **Bearing plate:** press in its inserts first. Set it over the cup. 2 bolts from the main half's back face.
5. **Sun piece** through the bearing plate's hole, sun end first, until the sun sits between the planets.
6. **Motor plate:** screw the N20 on (2 × M1.6), then press the pinion onto the shaft.
7. **Cluster** onto the bearing plate's axle boss, 9T side toward the 27T.
8. **Motor plate** on: 3 bolts (2 plate bolts + the cluster's axle bolt).
9. Slide the rod through the whole stack.

## Bench test (one at a time)
1. **By hand, no rod:** turn the worm. The carrier's square hole should turn, the motor should not.
2. **Motor, no rod:** run the motor from `pcb_test`. The carrier turns slowly, the worm stays still.
3. **On the blind:** wand first. Then motor. Watch if the slats go fully both ways.
4. **Stop the motor at the end stops by hand for now** (no stall cut-off yet). Don't let it push against the stop.

## Checked in Fusion
- No part touches another, standing still or through two full tooth steps, in motor mode and in wand mode.
- Gear play: sun/planet 3.2°, ring/planet 1.2°, cluster/27T 4.0°, pinion/20T 5.0°.
- All parts fit inside the headrail. All STLs are closed and print without supports.

## Not proven yet (the print will tell)
- The real torque at the rod. 0.77 N·m is a calculation.
- That the N20's gearbox holds still when the wand turns. If it slips, the wand will feel soft; a slower N20 fixes it.
- The cluster runs on the bolt's threads. Fine for a test; a plain pin later.
- No angle sensor in this rig. Moves are timed.
