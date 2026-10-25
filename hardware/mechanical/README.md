# Mechanical

CAD sources (parametric. Fusion/Onshape/OpenSCAD TBD) and exported 3MF/STL go here.

Design constraints: [headrail cross-section](../../docs/reference/headrail-cross-section.png). Inner ≈ 55.5 mm wide, ≈ 36.5 mm tall,
2 mm walls, inward lips at the top, 10 mm Ø feature centered 24 mm above the floor.

## Parts (planned)
| Part | Material | Notes |
|---|---|---|
| Motor cradle | PETG / PLA | Slides into headrail, holds the motor through isolators, anti-rotation keyed |
| Motor isolator sleeve | TPU 95A (test vs 68D) | Wraps the N20 gearbox. Only soft contact between motor and cradle |
| Headrail pads | TPU 95A | Cradle never touches the aluminum directly |
| Shaft coupler | TPU 68D or PETG + TPU spider | 3 mm D-shaft → tilt rod profile (parametric) |
| Encoder cap / cable strain relief | PETG | Protects the encoder PCB, routes the cable out of the headrail end |
| Controller enclosure | PETG | Sits on the headrail/top of the window frame |
