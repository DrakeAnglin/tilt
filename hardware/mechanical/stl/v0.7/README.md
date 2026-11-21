# Tilter v0.7: same planetary rig, 4 times the motor torque

v0.6 moved the medium blind a little, then stalled. v0.7 keeps the planetary set and the wand side exactly as they
are and puts two more gear steps between the motor and the sun.

```
Motor ── 9T ── P1 (20T/9T) ── R1 (27T/15T) ── P2 (21T/9T) ── 27T + sun ── planets ── carrier ── rod
```

| | v0.6 | v0.7 |
|---|---|---|
| N20 shaft to rod | 21 : 1 | **88 : 1** |
| Rod torque (calculated, at the stall point, on the battery) | about 0.45 N·m | **about 1.5 N·m** |
| End to end on the battery, no load | under 10 s | 20 to 40 s |
| Wand | 17 turns | the same |

- P1 and P2 both turn free on **one M3 × 25 bolt** (they turn at different speeds).
- R1 turns on a **tube that is part of the motor plate**. The rod passes through the tube.
- The wand side is untouched. The motor now holds even better when you use the wand.

## Print (7 parts)
`tilter_v07_H2D_PLA_PETG.3mf`: one plate, PLA left, PETG right. Make it again with
`python3 tools/orient_v07.py && python3 tools/bambu_v07.py`.

| File | What | Material |
|---|---|---|
| `gear_r1.stl` | 27T + 15T, big bore | PLA |
| `motor_pinion.stl` | 9T, thinner than v0.6's | PLA |
| `carrier.stl` | dowel holes now go right through (stronger seat). Optional, but do it if the planets ever tilt | PLA |
| `cluster_p1.stl` | 20T + 9T (motor side) | PETG |
| `cluster_p2.stl` | 21T + 9T (sun side) | PETG |
| `bearing_plate.stl` | bolt places moved | PETG |
| `motor_plate.stl` | taller, with the tube | PETG |

**Keep from v0.6:** ring cup, 4 planets, sun + 27T, worm wheel, lid, main half, worm. The old cluster is not used.

## Hardware
Same as v0.6: 5 × M3 × 25 bolts, 5 inserts (2 in the bearing plate's lid-side bosses, 3 in its flat face),
2 × M1.6 screws, 4 dowels.

## Assembly (from the bearing plate on)
1. Press 3 inserts into the bearing plate's flat face and 2 into the long bosses' ends. Bolt it to the case (2 bolts
   from the main half's back). Sun piece in, as before.
2. Screw the N20 to the motor plate. Press the pinion on.
3. Slide **R1** onto the tube, 27T first.
4. Push the axle bolt through the motor plate's hole next to the motor. Slide **P1** on (20T first), then **P2**
   (21T first).
5. Bring the motor plate up to the bearing plate. Wiggle the gears until P2's small gear drops into the sun's 27T.
6. Tighten the axle bolt and the 2 plate bolts. Stop when snug: the gears must still spin.
7. Rod through everything.

## Test
1. No rod: run the motor. The carrier's square hole turns very slowly (about 1 turn a minute). The worm stays still.
2. On the blind: wand first, then motor.
3. **Stop the motor by hand before the end stops.** With this much gearing a stalled motor can break teeth or tilt the
   planet pins. A current or time limit in the firmware comes next.

## Checked in Fusion
- No part touches another, standing still or turning (motor mode, wand mode, and the fast gears in fine steps).
- Gear play 2.4° to 5°. Everything is inside the headrail. STLs are closed and print without supports.

## Not proven
- The real torque. And the weak point is now the planet pins in the carrier: about 1 to 1.5 N·m at the rod.
- P1 and P2 rub face to face on the bolt (both PETG). Grease there.
