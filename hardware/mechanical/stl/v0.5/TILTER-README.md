# Tilter v0.5: swing-arm clutch (print and test)

v0.4 made the wand spin the N20 backward through its gearbox (hard by hand), and the N20 drove the worm through the
same train (too weak for a medium blind). v0.5 adds a printed **swing-arm clutch** in the motor's path:

```
N20 ── 8T pinion ── 9T idler A or B (on a swing arm) ── 12T ── (same shaft) 7T ── worm's 8T ── worm ── rod
```

- **Motor on:** three small flexure pads in the arm's hub grip the pinion's hub, so the arm swings with the pinion
  (14.6°) until one idler meshes the 12T. A printed stop post sets the exact mesh depth. While it drives, the tooth
  forces push the arm *into* the stop, so it stays engaged.
- **End of every move:** the firmware gives a short reverse nudge (about 14° of pinion rotation, slow PWM). That swings
  the arm back to the middle, where neither idler touches the 12T (0.5 mm tip gap).
- **Wand:** turns only the worm and the 7T/12T shaft. The motor never turns. The self-locking worm still holds the
  slats with the power off.
- The 8T:12T adds 1.5:1, so use the stronger N20 (150 RPM). Travel is about 5–6 s end to end.

Generators: [`TiltPartsV5`](../../fusion/TiltPartsV5/TiltPartsV5.py) (clutch, lid, 7T shaft; worm, wheel, sensor gear
and main half come from v0.4's code), [`TiltPodV5`](../../fusion/TiltPodV5/TiltPodV5.py) (sensor module), checked by
[`tools/fusion_tilter_v5.py`](../../../../tools/fusion_tilter_v5.py).

![clutch layout](../../../../docs/renders/clutch-layout.png)

## Files
| File | What | Print |
|---|---|---|
| `clutch_pinion.stl` | 8T (m 0.8), D-bore on the N20's flat, round hub the arm pivots on | **teeth down** (the hub's 45° cone needs it) |
| `clutch_arm.stl` | swing arm: hub with 3 flexure pads, 2 printed Ø3 idler pins, tail with the stop slot | arm plate flat on the bed, pins up |
| `clutch_idler.stl` | 9T idler (**print 2**) | flat |
| `clutch_12t.stl` | 12T, hex bore (pressed onto the shaft) | flat |
| `clutch_shaft.stl` | 7T 45° helical + Ø5 shaft + hex end; turns on a Ø4 pin in the main half | standing on the 7T face (pin hole down) |
| `case_left.stl` | lid: motor socket gone, Ø5.4 bore for the clutch shaft | outer face down |
| `case_right.stl` | main half: Ø4 pin for the 7T | back face down |
| `sensor_module.stl` | 65.7 mm long: N20 tunnel, stop post, AS5600, DRV8833, RJ12 (room side, behind the motor) | end wall down |
| `worm.stl`, `worm_wheel.stl`, `sensor_gear.stl` | unchanged from v0.4 | as v0.4 |

**Settings:** gears and the arm PETG or PLA+, 0.12 mm layers, 4 walls, 40%+ infill. The clutch gears are module 0.8
(the same tooth size class as the 7T). Cases and module 0.16–0.2 mm.

## Hardware
Same as v0.4, minus the M1.6 motor screw. Nothing new to buy.

## Assembly
1. **Main half:** worm wheel, Ø2 dowel and worm as v0.4. Drop the **clutch shaft** onto the Ø4 pin (7T meshing the
   worm's 8T), sensor gear with its magnet onto its pin.
2. **Lid** onto the main half, the shaft through the lid's bore (pegs into sockets).
3. **12T:** press it onto the shaft's hex from the lid side until it stops on the hex's shoulder.
4. **Module, on the bench:** inserts, RJ12 (slides in behind the motor's place, room side), DRV8833 and AS5600 as v0.4.
   Solder the motor leads to the N20 first. Slide the **N20 into its tunnel** from the open face, wires first (out
   of the tunnel's back toward the DRV8833), until its can stops on the two ledges. The D-flat faces any way.
5. **Clutch, in the module:** push the **pinion** onto the N20's shaft (D-flat), hub toward the motor. Grease the two
   idler pins (not the hub), slip the **idlers** onto them, then push the **arm's** hub over the pinion's hub (the pads
   snap round it) with the **stop post through the slot**. Turn the arm to the middle of its slot.
6. **Join:** slide the module onto the lid face. The 12T goes straight in between the two idlers. 3 × M3 × 25 from the
   main half's back face, as v0.4.
7. **Check by hand:** the wand turns the rod smoothly and the motor shaft doesn't move. Spin the motor's pinion by
   hand: the arm swings, one idler meshes and the rod turns; spin it back a little and the arm returns to the middle.

## Firmware rule (the clutch depends on it)
- **Start of a move:** the first ~15° of pinion rotation only swings the arm into mesh (a few tens of ms).
- **End of every move:** brake, then **reverse at low PWM for about 14° of pinion rotation** (time it on the bench: at
  30% PWM roughly 40–60 ms), then coast. The neutral window is about ±5° of arm rotation, so the timing doesn't need to be
  exact. The AS5600 shows an overshoot: if the rod moves backward during the nudge, the other idler engaged, so nudge
  forward by half.
- If a nudge is ever missed, turning the wand in the motor's last direction still knocks the idler out by itself. The
  other direction turns the motor backward (as v0.4) until the next move resets the arm.

## Checked in Fusion
- No interference between any part, with the arm **in the middle and at both stops** (idlers rolled round the pinion as
  they really would be). Only the AS5600 board's locating pin (a press fit by design) and its edge by the rod (file
  ~1 mm off, as v0.4) show up.
- Stop contact exact at both stops; the meshed idler's center distance is 8.50 (standard 8.40 + 0.1 for printed teeth).
- Idler tips 0.5 mm from the 12T in the middle; the idler not in use 2.1 mm away when the other one is driving.
- 7T on the worm's 8T: 6.9° of backlash (contact-free window).
- All STLs closed; the new parts print in their stated orientation with no overhang (the clutch shaft's pin hole has a
  cone tip). The case halves' overhangs are v0.4's (the AS5600 pocket bridges).

## Still to confirm on the real parts
- The flexure pads' grip: enough to swing the arm, not so much that it wastes motor torque. If the arm doesn't swing,
  the hub printed small; if the motor labors with the arm at its stop, it printed big.
- The nudge timing on the real motor and battery voltage.
- Whether the medium blind turns: measure the motor current while it moves.
