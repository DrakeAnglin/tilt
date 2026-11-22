# Controller box

The box for the controller PCB ([hardware/pcb](../hardware/pcb/README.md)), the 18650 cell and the **Adafruit 6092**
charger. The charger's own USB-C is the charge port. The box slides into the headrail, with the tilt rod running in the
round groove in the lid.

Built by [Controller.py](../hardware/mechanical/fusion/Controller/Controller.py), checked in Fusion by
`python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller.py --timeout 1800`.

| | |
|---|---|
| Size | **157.4 × 51.8 × 23.0 mm**, plus 2 bumpers on the back wall that center it in the rail |
| Prints | `hardware/mechanical/stl/controller/controller_tray.stl` (floor down) and `controller_lid.stl` (top face down). White PLA, no supports. **Print `controller_end_a_coupon.stl` first** (end wall A only, about 10 min) and check the fit against a board with its jacks soldered |
| Hardware | 3 × M3 heat-set inserts, 3 × M3 × 10 flat-head screws, 2 × M2 × 6 self-tapping screws (charger), 4 × clear stick-on bumpers about 8 × 2 mm ([BOM](../hardware/BOM.md#box)) |
| Check | Interference check of every part against the tray, the lid and each other: none |

End A has the three RJ12 jacks. End B has the charger's USB-C and the solar slot.

## Tight spots
| Where | Room |
|---|---|
| ESP32-C6 header pin tips | 1.5 to 2.0 mm under the groove. Clip the tips if yours stand more than 1.9 mm above the board |
| Under the PCB | 2.4 mm. **Trim every lead on the underside to 1.8 mm or less** |
| Fuses | Fold all three over toward the ESP, bent about 1.6 mm below the body (not at the body), so each disc lies flat over its resistors |
| Battery plug wires (J4) | 1.5 mm under the groove: bend them over as they leave the plug |

## Assembly
Solder the PCB first: [PCB build guide](pcb-build.md). The charger harness and battery splice are its step 11.

1. Press the 3 inserts into the lid's 3 posts (lid upside down, soldering iron).
2. v2.1 boards only: cut 3 to 4 mm off the PCB's jack edge (v2.2 boards come already cut).
3. PCB into the tray, jacks first through their openings in end wall A.
4. Cell into its two saddles along the back wall, lead at end B. Plug it into J4.
5. Charger: USB-C end first into the slot in end wall B, lower the other end onto the two studs, then the 2 small
   screws. Plug its harness into J5.
6. Solar lead (if used): through the slot in end wall B, along the floor on the room side, into J8.
7. Lid on. Turn the box over and drive the 3 M3 × 10 screws up through the floor, snug only.
8. **Feet.** With the box still upside down, wipe the floor clean and stick on **4 bumpers**, one in each corner,
   about 10 mm in from the ends and the sides. Keep them off the three screw heads. The middle of the floor stays
   clear, so the blind's lift cord can pass under the box.

The top has no screw heads and the heads underneath sit flush, so the box slides into the rail.

**Check in the rail:** the box must not pinch the lift cord, and the tilt rod must still turn freely in the lid's
groove. The groove has only about 0.5 mm under the rod's corners in the CAD, and the feet lift the box. If the rod
rubs, use lower bumpers.
