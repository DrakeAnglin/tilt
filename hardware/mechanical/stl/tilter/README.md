# Tilter (v0.9)

The motor unit on one blind's tilt rod. A printed worm and worm wheel turn the rod, as the blind's own tilter did, so
the wand still works by hand. An N20 motor drives the worm wheel through one gear cluster and a planetary set. The
AS5600 reads the angle off a sensor sleeve driven by the carrier, so a short rod (the blinds' rods stop about 21 mm
in) still works, and a long rod can slide right through. 68.6 mm long; it sits in the 110 mm pocket between the
headrail's end cap and the first tilt drum.

Built by `python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_tilter.py --timeout 1800`
([`Tilter.py`](../../fusion/Tilter/Tilter.py)), then `tools/fusion_thin.py` for the thin-wall scan. v0.9 has been
printed; what it still has to prove is at the end. Older versions and the reasons for each change are in the Git
history.

## Printed parts
Files here are as designed; `print/` has each part turned to how it sits on the bed (`python3 tools/orient.py`).
Bambu Studio projects for the H2D: `tilter_H2D_PLA_PETG.3mf` (PLA plate + PETG plate), `tilter_H2D_PLA_only.3mf`,
`tilter_H2D_PETG_only.3mf`. All white, 0.4 mm nozzle.

| Part | Plastic | Copies | On the bed |
|---|---|---|---|
| `case_right` (main half) | PLA | 1 | back face down |
| `case_left` (worm case lid) | PLA | 1 | outer face down |
| `bearing_shell` | PLA | 1 | gear-side face down, cup bore up |
| `motor_shell` | PLA | 1 | motor face down, gear room up |
| `tray` | PLA | 1 | floor down, open top up |
| `tray_lid` | PLA | 1 | top face down; **support under the gear shelf** (the only support) |
| `ring_cup` | PLA | 1 | floor down, open end up |
| `sun_27t` | PLA | 1 | 27T down, sun up |
| `worm_wheel` | PLA | 1 | plain barrel end down, hex up |
| `worm` | PLA | 1 | standing on its thread end, with a brim; loop up |
| `motor_pinion` | PLA | 1 | flat |
| `planet` | PLA | 4 | flat |
| `carrier` | PETG | 1 | disc down, hub up |
| `cluster` (20T / 9T) | PETG | 1 | 20T down, 9T up |
| `sensor_sleeve` | PETG | 1 | gear face down, lugs up |
| `magnet_gear` | PETG | 1 | gear face down, magnet hub up |

PETG is for the parts that rub or mesh against PLA all the time.

## Hardware for one tilter
| Part | Qty | Where |
|---|---|---|
| M3 heat-set insert | 6 | bearing shell 4 (2 case bolts, 2 tray bolts), tray 2 (sensor bolt, lid corner) |
| M3 × 25 flat-head | 3 | 2 case bolts, 1 sensor bolt (through the lid's column and the AS5600) |
| M3 × 20 flat-head | 2 | tray bolts; the room-side one is also the cluster gear's axle |
| M3 × 8 flat-head | 1 | lid's corner bolt |
| M1.6 × 4 | 2 | N20 to the motor shell |
| Ø2 × 6 dowel pin | 5 | 4 planet axles in the carrier, 1 worm top pin in the worm case |
| Super Lube 21030 | a little | worm, wheel, every gear, the carrier's hub, the sleeve's nose |

Electronics (N20, AS5600 with magnet, DRV8833, RJ12 breakout, 10 µF): [BOM](../../../BOM.md#one-tilter-8).

## Before you start
1. **Wire the sensor module on the bench:** [tilter wiring](../../../../docs/tilter-wiring.md). The AS5600 is already
   switched to PWM. Leave the two motor leads loose.
2. **Press the inserts** with a soldering iron: 4 in the bearing shell, 2 in the tray.
3. **Press the dowels:** 4 into the carrier, 1 into the worm case for the worm's top end.

## Assembly
Grease every gear as it goes in.

1. **Worm case:** wheel and worm into the main half, lid on. Ring cup onto the wheel's hex. Planets onto the carrier's
   dowels, carrier into the cup.
2. **Bearing shell** over the cup (its two pins find the lid). Sun piece in. Two M3 × 25 from the main half's back,
   snug.
3. **Motor shell:** screw the N20 to its plate with the 2 M1.6 × 4 (the heads sit down in their wells). Drop in the
   motor pinion and the cluster. The motor shell has no bolts of its own: hold it on the bearing shell (two pins); the
   cluster gets its axle when the tray's bolt goes in.
4. **Sensor sleeve:** push its nose through the motor plate from the back and turn it until the lugs drop into the
   carrier (the last 2.4 mm). Its gear now sticks out of the plate.
5. **AS5600 onto its studs in the tray first**, with the tray still off, chip up. It lies under the sleeve's gear, so
   it cannot go in afterwards.
6. **Tray** on from the back (its two pins find the motor shell). Two M3 × 20 through holes in its end wall: the
   room-side one through the cluster gear (turn the gear until the bolt finds its bore), the floor one under the sensor
   board. Snug, not hard: a hard-tightened axle bolt can bow the motor plate onto the cluster.
7. **Solder the motor leads** to the N20's tabs. **DRV8833** down into its slots, then the **RJ12** board, jack up.
8. **Lid:** press the magnet into the magnet gear's hub. Pick the support out of the lid's gear cage, then slide the
   gear in from the rod side until its hub clicks into its seat. Lower the lid straight down over the jack; the gear
   turns itself into mesh. M3 × 25 down through the column and the sensor board, M3 × 8 in the corner. Snug.
9. **Into the rail**, then push the rod through. Turn the wand a little if it stops.

Plug the cord in and set the blind up in the app: [build guide](../../../../docs/build-guide.md).

## Checked in Fusion
- No part touches another, with a rod right through the tilter included.
- Gears turned through their meshes in motor mode, wand mode and at the fast end: no overlap.
- Assembly paths swept in the order above: all clear.
- Sleeve end play: 0.25 mm forward, 0.35 mm back.
- Print files scanned for overhangs: only the lid's gear shelf needs support.
- Thin-wall scan (`tools/fusion_thin.py`): what it still lists is on purpose (the 0.8 mm bearing wall between the gear
  rooms, the 1.0 mm roof over the ring cup, the 0.75 mm tray floor under the motor, the 0.8 mm wall behind the RJ12's
  solder joints).

## Not proven yet
- Module 0.75 planetary teeth on the 0.4 mm nozzle. The sun piece's wall under its teeth and the sleeve's wall at the
  bore's corners are 0.9 mm.
- Both tray bolts are low: nothing clamps the top of the tray to the motor shell.
- The sleeve hangs 14.6 mm out of the motor plate with nothing under its gear but the rod (when the rod reaches).
- Lug fit in the carrier (3.0 mm lugs in 3.1 mm slots) sets the sensor's play against the carrier.
- How the printed worm pair wears.
