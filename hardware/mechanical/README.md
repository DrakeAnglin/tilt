# Mechanical

CAD sources (parametric. Fusion/Onshape/OpenSCAD TBD) and exported 3MF/STL go here.

## Versions
| Version | Drive | Generator | Print files |
|---|---|---|---|
| v0.3 | Factory worm + worm wheel, printed spline adapter, crossed helicals to the N20 | [`fusion/TiltParts`](fusion/TiltParts/TiltParts.py) | [`stl/`](stl/README.md) |
| **v0.4** (first test build) | **All printed**: worm with integrated 8T helical, worm wheel, wand shaft; v0.3's crossed helicals to the N20, flat lid | [`fusion/TiltPartsV4`](fusion/TiltPartsV4/TiltPartsV4.py) | [`stl/v0.4/`](stl/v0.4/README.md) |

## Known dimensions
| What | Value | Source |
|---|---|---|
| Headrail inner width × height | ≈ 55.5 × 36.5 mm, 2 mm plastic walls, inward hooked lips at top | [cross-section](../../docs/reference/headrail-cross-section.png) |
| Tilt rod | **4 mm square steel** | Owner |
| Tilt rod axis height | **24 mm above inner floor**, centered side to side (the 10 mm circle in the sketch marks the rod center) | Owner |
| Free length, end cap → first tilt drum cradle | **110 mm** | Owner |
| Factory wand + tilter gears | **Removed**. The motor drives the rod directly, with nothing self-locking in the chain | Owner |
| Clearance above the headrail when installed | **≈ 6.5 mm** from the top of the cross-section to the window frame. Nothing may stick up more than ~5 mm; cables can't exit the top | Owner |
| Factory tilter location | **In the 110 mm end pocket**; the rod passes through its worm wheel | Owner |
| Tilt travel | **11–12 wand (worm) turns** closed → closed, 5–6 from open (horizontal) to closed = **≈ 250–270° of rod** (16:1 worm). An earlier "≈ 60°" was the slat angle, not the rod | Owner, test print 2026-10-26 |
| Tilt torque | Low: the rod turns easily with fingers (exact kg·cm still to measure) | Owner |
| Lift/holding mechanism | Long perforated module under the rod, separate from tilt | Owner, [photo](../../docs/reference/headrail-square-tilt-rod.jpg) |

## Layout in the 110 mm end pocket (draft)
```
 end cap                                                          first tilt cradle
 |<--3-->|<----20---->|<-------- ~35 -------->|<---- ~20 ---->|<--5+-->|
 | gap   | RJ12 jack  | N20: encoder|motor|gbx | TPU coupler   | spare  |
 |       | + strain   | in TPU sleeve, held   | 3 mm D-bore → |        |
 |       |   relief   | by PETG sled          | 4 mm sq socket|        |
                                                ═══════ 4 mm square rod ═══════►
```
Total ≈ 83 mm of 110 mm, so ~25 mm margin. That's enough for a longer 1:1000 gearbox, or a right-angle worm N20 if torque requires it.

- **Sled:** PETG, slides in from the end and keys under the top lips like the factory cradles (no screws into the thin plastic). It touches the headrail only through TPU pads.
- **Coupler:** one-piece TPU (68D) or PETG hub + TPU spider. A 4 mm square socket ≥ 8 mm deep slides over the rod end; the motor end is a 3 mm D-bore (N20 shaft, 2.5 mm across the flat). Takes up small misalignment so the gearbox doesn't bind.
- **Rod engagement:** the rod must reach ≥ 8 mm into the coupler. If it stops short, a 4 mm square steel rod is cheap to replace, or the coupler gets a longer socket.
- **Holding:** with the worm tilter gone, the N20 gearbox friction plus the driver's brake mode hold the slats. Tilt loads are mostly balanced; verify on the largest blind.


## Parts (planned)
| Part | Material | Notes |
|---|---|---|
| Motor cradle | PETG / PLA | Slides into headrail, holds the motor through isolators, anti-rotation keyed |
| Motor isolator sleeve | TPU 95A (test vs 68D) | Wraps the N20 gearbox. Only soft contact between motor and cradle |
| Headrail pads | TPU 95A | Cradle never touches the plastic headrail directly |
| Shaft coupler | TPU 68D or PETG + TPU spider | 3 mm D-shaft → tilt rod profile (parametric) |
| Encoder cap / cable strain relief | PETG | Protects the encoder PCB, routes the cable out of the headrail end |
| Controller enclosure | PETG | Sits on the headrail/top of the window frame |
