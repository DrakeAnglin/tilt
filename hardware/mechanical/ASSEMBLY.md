# Motorized tilter: build & test guide (v0.3)

This replaces the blind's factory tilter with a printed housing that keeps the factory **worm** and **worm wheel**,
adds a small N20 gear motor, and keeps the wand working by hand. An AS5600 magnetic sensor reads the tilt rod's angle.

```
 tilt rod ─── worm wheel (factory, 16 T) ◄── worm (factory, 16:1, self-locking)
                                               │ 8-ridge spline
                                     ADAPTER (printed): 8 T helical gear + teardrop wand loop
                                               │ 45° crossed helical, 1 : 1.14
                                     PINION (printed, 7 T) on the N20 motor
 rod end ── MAGNET CAP (printed) ── 6×2.5 mm magnet ··· AS5600 board in the SENSOR HOLDER (printed)
```

## Parts

### Printed (files in [stl/](stl/))
| File | Qty | Material | Orientation | Notes |
|---|---|---|---|---|
| `case_right.stl` | 1 | PETG | split face down | Main half, holds everything |
| `case_left.stl` | 1 | PETG | split face down | Lid |
| `adapter.stl` | 1 | PETG or PLA+ | gear down, loop up | 0.12 mm layers |
| `motor_pinion.stl` | 1 | PETG or PLA+ | gear down, hub up | 0.12 mm layers |
| `magnet_cap.stl` | 1 | PETG / PLA | magnet pocket up | |
| `sensor_holder.stl` | 1 | PETG / PLA | back plate down | |

Suggested: 0.4 mm nozzle, 4 walls, 30–40 % infill, no supports needed.

### Hardware
| Item | Qty | Notes |
|---|---|---|
| Factory worm, worm wheel | 1 each | From the blind's tilter (drill out the 3 rivets) |
| N20 gear motor, **no encoder**, 3 mm D-shaft | 1 | 5–6 V. ~1:30–1:100 so the wand can still turn it by hand |
| M2 × 16 screw (self-tapping or machine) | 3 | Case halves |
| M2 × 10 screw | 2 | Sensor holder to the lid |
| M1.6 × 4 screw | 2 | N20 gearbox face (counterbored inside the case) |
| AS5600 breakout board, ≤ 23.4 × 23.4 mm, chip centered | 1 | I²C to the controller |
| 6 × 2.5 mm diametric neodymium magnet | 1 | Often sold with AS5600 boards |
| 2-wire motor lead + 4-wire sensor lead | — | To the controller |

## Assembly
1. **Strip the factory tilter:** drill out the 3 rivets, keep the worm and the worm wheel. The factory wand connector and
   shell aren't used.
2. **Motor:** push the N20 into the motor pod of `case_right` from the open end until the gearbox face seats against the
   wall. Fit the 2 × M1.6 × 4 screws from inside the pinion pocket (the heads sink into counterbores).
3. **Pinion:** press `motor_pinion` onto the shaft, hub toward the motor, until the hub touches the wall. If it's loose,
   one drop of CA on the shaft's flat.
4. **Worm wheel:** drop it into its pocket with the barrel through the bearing hole.
5. **Worm + adapter:** slide `adapter` onto the worm's splined end (socket clearance is 0.10 mm, the fit you chose).
   Lay the worm in its groove with the flanges in their pockets. The adapter's gear sits next to the lower flange
   and meshes with the pinion. The loop hangs out through the notch block.
6. **Check by hand:** turn the adapter loop. The worm wheel should turn smoothly, and so should the motor (it back-drives
   through the gears). Nothing should rub.
7. **Lid:** fit `case_left`, 3 × M2 × 16.
8. **Sensor:** push the magnet into `magnet_cap` (any orientation, diametric magnets are symmetric for this). Push the
   cap onto the rod end until it touches the worm wheel's barrel. Slide the AS5600 board into `sensor_holder` from the
   top, chip facing the magnet, then screw the holder to the lid (2 × M2 × 10).
9. **Install:** slide the rod through the worm wheel, hook the housing under the rail's lips and press it down between
   the walls until the block drops into the corner notch. Hook the wand onto the teardrop loop.

## First power-on test (bench)
- 5 V through the motor driver, low PWM first. Slats should tilt smoothly through the full ~60° in about a second.
- Read the AS5600 angle while tilting by hand: it should change by about 60° end to end, with no jumps.
- Listen: any ticking means a gear rubs. Note where and report it, since each clearance is a parameter.
