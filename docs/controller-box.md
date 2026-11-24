# Controller box

The box for the controller PCB ([hardware/pcb](../hardware/pcb/README.md)), the 18650 cell and the **Adafruit 6092**
charger. The charger's own USB-C is the charge port. The box tilts into the headrail past its lips, with the tilt rod
running in the round groove down the middle of the lid.

Built by [Controller.py](../hardware/mechanical/fusion/Controller/Controller.py), checked in Fusion by
`python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller.py --timeout 1800`.

| | |
|---|---|
| Size | **157.4 × 51.8 × 23.0 mm**. Both long sides have 45° bevels, top and bottom. Nothing on the sides: the box is narrower than the rail and the rod in its groove keeps it in place, so the same box fits rails of other widths |
| Prints | `hardware/mechanical/stl/controller/controller_tray.stl` and `controller_lid.stl`. Both files already lie the way they print (tray floor down, lid top face down): drop them on the plate as they are. White PLA, no supports |
| Hardware | 3 × M3 heat-set inserts, 3 × M3 × 10 flat-head screws, 2 × M2 × 6 self-tapping screws (charger), 4 × stick-on felt pads about 8 mm across and 1.5 to 2 mm tall ([BOM](../hardware/BOM.md#box)) |
| Check | Collision check of every part against the tray, the lid and each other, and the stays-inside check (nothing comes out through a wall or the floor): both clean |

End A has the three RJ12 jacks. End B has the charger's USB-C and the solar opening.

## Tight spots
| Where | Room |
|---|---|
| ESP32-C6 header pin tips | The row nearer the middle has 0.2 mm under the groove's channel. Clip the tips if yours stand more than 1.9 mm above the board |
| Under the PCB | 2.4 mm. **Trim every lead on the underside to 1.8 mm or less** |
| Fuses | Fold all three over toward the ESP, bent about 1.6 mm below the body (not at the body), so each disc lies flat over its resistors |
| Fuse F2 | 0.45 mm under the groove's channel once folded flat. If the lid won't seat, press F2 down a little |
| Battery wires (J4) | Lay them low along the PCB's back edge and bring one round each end of the plug. Don't cross them over the top of the fuses or the plug's middle: the groove's channel is right above |

## Assembly
Solder the PCB first: [PCB build guide](pcb-build.md). The charger harness and battery splice are its step 11.

1. Press the 3 inserts into the lid's 3 posts (lid upside down, soldering iron).
2. v2.1 boards only: cut 3 to 4 mm off the PCB's jack edge (v2.2 boards come already cut).
3. PCB into the tray, jacks first through their openings in end wall A.
4. Cell into its two saddles along the back wall, lead at end B. Plug it into J4.
5. Charger: USB-C end first into the slot in end wall B, lower the other end onto the two studs, then the 2 small
   screws. Plug its harness into J5.
6. Solar lead (if used): plug first through the opening in end wall B (6 × 4.7 mm, the plug fits through), along
   the floor on the room side, into J8.
7. Lid on. Turn the box over and drive the 3 M3 × 10 screws up through the floor, snug only.
8. **Feet.** With the box still upside down, wipe the floor clean and stick on **4 felt pads**, one in each
   corner, about 10 mm in from the ends and the sides. Keep them off the three screw heads. The pads lift the box off
   the rail floor. **Leave the middle of the floor clear from end to end:** the blind's lift cord runs down the middle
   of the rail, under the box.

The top has no screw heads and the heads underneath sit flush.

**Into the rail:** lift the tilt rod a little. Tilt the box, put one long edge in under a lip of the rail,
then push the other side down. The bevels guide it past the lips. No prying: in the CAD the rail's walls give
0.2 mm (the old square box with its side bumpers needed 3.6 mm). Check it with
`python3 hardware/mechanical/fusion/Controller/tilt_in.py`.

**Check in the rail:** the box must not pinch the lift cord, and the tilt rod must still turn freely in the lid's
groove. The groove leaves 1.8 mm under the rod's corners in the CAD, and the feet lift the box by their own height.
If the rod rubs, use thinner pads. The box has about 1.85 mm of play each side in a 55.5 mm rail; the groove is wide
enough that the rod can't touch its sides wherever the box sits. In a wider rail, stick a felt pad on each side wall
if the box wanders.
