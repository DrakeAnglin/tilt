# Motorized tilter: build & test guide (v0.3)

![closed housing](../../docs/renders/v03-closed-iso.png)

One unit per blind replaces the factory tilter. It keeps the factory **worm** and **worm wheel**, adds a small N20 gear
motor, keeps the wand working by hand, and has an **AS5600 magnetic sensor** built in. A small gear on the back of the
worm wheel turns a magnet, so the controller always knows the slat angle, even right after power-up or after someone
used the wand. The ESP32 + motor drivers are a separate **controller unit** (one per 3 blinds) at the end of a
5-wire cable from each blind.

```
 TILTER   tilt rod ── worm wheel (factory 16T) ◄── worm (factory, 16:1, self-locking)
                                                     │ 8-ridge spline
                                           ADAPTER (printed): 8T 45° helical gear + teardrop wand loop
                                                     │ crossed helical, not self-locking → wand back-drives the motor
                                           PINION (printed, 7T) on the N20 motor
 SENSOR   worm wheel (back side) ── SENSOR GEAR (20T) ── magnet ··· AS5600 board on standoffs on the lid
          60° of slat travel = 48° at the magnet (absolute, single turn)
```

## Parts

### Printed (files in [stl/](stl/), settings there)
`case_right`, `case_left`, `adapter`, `motor_pinion`, `sensor_gear`

### Hardware
| Item | Qty | Notes |
|---|---|---|
| Factory worm + worm wheel | 1 each | From the blind's tilter (drill out the 3 rivets) |
| N20 gear motor, **no encoder**, 3 mm D-shaft ≥ 9.5 mm | 1 | 5–6 V, **1:30–1:50 recommended** so the wand can back-drive it. Full 60° ≈ 3 motor turns |
| M1.6 × 4 screw | 2 | N20 gearbox face (heads sink into counterbores in the pinion pocket) |
| M2 × 16 screw | 3 | Tilter halves (heads sit flush in the lid) |
| M2 heat-set insert | 2 | Lid, for the AS5600 standoffs (you have these) |
| M2 × 5 mm standoff (male-female) + M2 × 4 screw | 2 + 2 | AS5600 board |
| AS5600 breakout, ≤ 23.4 × 23.4 mm, chip centred | 1 | I²C to the controller |
| 6 × 2.5 mm diametric neodymium magnet | 1 | Often sold with AS5600 boards |
| Wire | — | 2-core motor lead, 4-core sensor lead (3V3, GND, SDA, SCL) |

## Tilter assembly
1. **Strip the factory tilter:** drill out the 3 rivets and keep the worm and worm wheel.
2. **Motor:** push the N20's gearbox into the rectangular socket in the back face of `case_right` until its face seats
   against the wall. Fit 2 × M1.6 × 4 from inside the pinion pocket. The rest of the motor sticks out the back.
3. **Pinion:** press `motor_pinion` onto the shaft, hub toward the motor, until the hub touches the wall (CA on the flat
   if loose).
4. **Worm wheel:** drop it into its pocket, barrel through the bearing hole.
5. **Worm + adapter:** slide `adapter` onto the worm's splined end. Lay the worm in its groove with both flanges in their
   pockets. The adapter gear meshes with the pinion, and the loop hangs out through the notch block.
6. **Hand check:** turn the loop. The worm wheel should turn smoothly, and so should the motor shaft. Nothing should rub.
7. **Lid:** fit `case_left`. Its 2 pegs drop into the sockets in `case_right`. Then 3 × M2 × 16.

## Sensor (part of the tilter)
1. Before closing the case: press the magnet into the head of `sensor_gear`, then drop the gear into its pocket in
   `case_right` (shaft end into the blind hole) so it meshes with the back of the worm wheel. Close the lid as above.
   The magnet head pokes ~2 mm out of the lid face.
2. Press 2 × M2 heat-set inserts into the holes in the lid's outer face (soldering iron, ~220 °C for PETG).
3. Screw 2 × M2 × 5 mm standoffs into the inserts, then the AS5600 board onto them **chip facing the magnet**
   (2 × M2 × 4 screws). Chip-to-magnet gap = standoff − chip height − 2 mm protrusion ≈ 1.5 mm.
4. Solder the 5-wire lead: motor + and − to the N20 tabs; 3V3, GND and OUT to the AS5600 header (tie GPO to VCC
   for the analog output). Secure the lead with a zip tie to the case before it leaves the unit.

## Install in the headrail
1. Take the rod out and thread it through the tilter's worm wheel.
2. Press the tilter down between the rail walls with the block in the corner notch. The small dome over the worm sits
   in the rail's open top slot.
3. Re-seat the rod through the tilt drums, hook the wand onto the teardrop loop, and run the wires to the controller.

## First power-on test (bench)
- Motor at low PWM first: the slats should tilt through the full ~60° in about a second.
- Read the AS5600 angle while tilting by hand. It should change by about 103° end to end, with no jumps.
- Listen: any ticking means something rubs. Note where. Every clearance is a parameter in `TiltParts.py`.
