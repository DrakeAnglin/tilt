# Factory tilter: measurements & motorization layout

Photos: [face with ruler](../../docs/reference/tilter-face-ruler.jpg), [top with ruler](../../docs/reference/tilter-top-ruler.jpg),
[gears](../../docs/reference/tilter-worm-gear.jpg), [side](../../docs/reference/tilter-side.jpg).

## Measured / estimated from photos (±2 mm unless noted)
Face photo scale: ruler 0–100 mm ≈ 10.4 px/mm. The face shown is the headrail cross-section plane (rod goes into the page).

| Feature | Value | How |
|---|---|---|
| Thickness along the rod | **16.5 mm** | Owner, calipers |
| Overall face envelope | ≈ 61 × 45 mm (excl. wand loop) | Photo. Spans the full rail cross-section; top hook clips over the rear lip |
| Square bore → bottom of frame | ≈ 23.5 mm | Photo. Matches the 24 mm rod axis, so the frame bottom sits on the rail floor |
| Worm wheel OD | ≈ 15 mm | Photo |
| Worm axis | ≈ **55–65°** from horizontal (back-face photo reads ~56°), sloping down to the front-bottom corner where the wand loop exits | Photos |
| Worm assembly length along its axis | ≈ 44 mm from the upper end cap (≈ 6 mm Ø) to the base of the wand loop | [back face](../../docs/reference/tilter-back-face-ruler.jpg) |
| Worm housing tube OD | ≈ 10 mm (worm itself ≈ 6–7 mm) | Photo |
| Housing | Two-half clear shell held by **3 rivets** (owner drilled them out). A printed housing would use M2 screws | Owner |
| Worm back end | **Enclosed**, ends close to the top of the rail. No room for a coaxial motor | Owner + photo |
| Wand travel | "A few full turns" closed → closed | Owner |
| Rod travel | ≈ 60° closed → closed | Owner |
| **Implied worm ratio** | (3–5 turns × 360°) / 60° ≈ **18–30 : 1** | Consistent with a single-start worm on a ~20-tooth, 15 mm wheel |

## Packaging problem
The worm's upper end runs almost into the top of the rail, so an N20 can't go coaxially behind it, and the lower end exits the
rail to the wand. The factory housing can't take a motor as-is.

## Layout options (motor must drive the worm shaft; see motor-analysis Option C)

### L1: new printed housing, motor beside the worm, spur-gear drive (recommended)
- Open the factory tilter (3 screws) and reuse its **worm + worm wheel** in a new printed housing.
- Housing grows along the rod (16.5 → ~35 mm) into the 110 mm pocket.
- The N20 sits **parallel to the worm** (same ~67° slope), offset along the rod by ~12 mm, and drives the worm shaft through a
  **small spur gear pair** (also a chance to add 2–3 : 1 reduction).
- Keeps the exact wand angle and exit hole: no change to the rail, wand works as before.
- 35 mm N20 at 67° ≈ 32 mm tall: fits the 36.5 mm rail height, but tightly. Placement needs CAD.

### L2: horizontal worm across the rail, coaxial motor, U-joint to the wand
- Worm runs front-to-back under the wheel (axis ≈ 13 mm above the floor), N20 coaxial at the rear: ~50 mm of 55.5 mm width.
- The wand stub needs a **printed universal joint** to exit at the factory angle.
- Simpler motor mounting, more moving parts at the wand.

### L3: Option B fallback (drive the rod, no wand)

## Motor ratio for Option C
Worm input needs only ~3–5 turns for full travel, so speed isn't a constraint. The constraint is **hand back-drivability**
(the wand must spin the motor):
- 1:30–1:50 (~200–300 RPM at 5 V): easy to back-drive. Full travel < 1 s at full speed, so run it slower with PWM.
- 1:100 (~130 RPM at 5 V): ~2 s travel. Back-drive by hand is likely stiff. **Test before choosing.**
- 1:298/1:380 (the 40 RPM motors): too stiff to back-drive through a wand. Fine for bench and noise tests only.

## Internals (tilter opened, 2026-10-25)
Photos: [overview](../../docs/reference/tilter-opened-overview.jpg), [gear](../../docs/reference/tilter-opened-gear.jpg),
[worm](../../docs/reference/tilter-opened-worm.jpg). Scale checked against the 4 mm square bore (reads 3.8–4.0 mm).
Values are photo estimates (±0.5–1 mm) until confirmed with calipers.

| Part | Feature | Estimate |
|---|---|---|
| Worm wheel | Teeth | **15** (count to confirm) |
| | Outside diameter | ≈ 18.5 mm → **module ≈ 1.0–1.1** |
| | Bore | 4 mm square, molded |
| Worm | Threaded section | ≈ 11–13 mm long, ~3.5 crests, **single start** (to confirm) |
| | Thread OD | ≈ 12 mm (pitch dia ≈ 10 mm) |
| | Axial pitch | ≈ 3.2–3.3 mm (consistent with module 1: π × 1 = 3.14) |
| | Upper journal (pin) | ≈ 4.5 mm Ø, runs in a molded seat |
| | Thrust collar | ≈ 10 mm Ø flange, located in shell slots |
| | Output shaft | **Splined**, ≈ 5 mm Ø × ≈ 15 mm, exits through the tube |
| Wand loop | Attachment | Separate part: sleeve with snap barbs that slides onto the worm's splined shaft |
| Mesh | Center distance | ≈ (10 + 15) / 2 ≈ **12.5 mm** |

**Derived:**
- **Worm ratio = 15 : 1** (single start, 15 teeth). 60° of rod = **2.5 worm turns**, which matches "a few turns".
- Lead angle ≈ atan(3.14 / (π × 10)) ≈ 5.7°. Below the friction angle of plastic on plastic, so it **self-locks**, as expected.

## Chosen concept: drive sleeve on the splined shaft (layout L1, refined)
The wand already drives the worm through the **splined output shaft**. The motor can drive the same shaft:

```
   worm (factory) ──spline──► [printed DRIVE SLEEVE: internal spline + spur gear + external spline] ──► wand loop (factory, snaps on)
                                         ▲
                                  spur pinion on N20 (motor parallel to the worm axis, offset ~11 mm)
```

- Reuse the factory **worm, worm wheel, and wand loop** unchanged (molded parts are smoother and quieter than printed ones).
- New printed **housing halves** (the original shape plus a pod for the N20 beside the worm tube), joined with M2 screws in place of the rivets.
- **Drive sleeve:** slides over the factory spline, carries a spur gear, and repeats the spline on its outer end so the factory
  wand loop snaps onto it. If the spline is too fine to print, use a printed hex/D interface and a printed wand loop.
- **Spur stage 1 : 1** (e.g. module 0.8, 14 T / 14 T, 11.2 mm centers) keeps the wand easy to back-drive. Reduction lives in the N20 + worm.
- **Total ratio:** N20 (1:30–1:50) × 1 × 15 worm. Full 60° travel = 2.5 worm turns ≈ 0.4–0.6 s at full speed, so run it slow for quiet.
- **Encoder:** 14 counts/motor rev × 30 × 15 ≈ 6,300 counts per rod turn → ~1,050 counts across the 60° travel. Plenty.
- Motor pod is parallel to the worm (~56° slope), offset along the rod into the 110 mm pocket. Fit inside the 36.5 mm rail height is checked in CAD.

## Still needed (calipers)
- [ ] Worm wheel: tooth count, OD, face width
- [ ] Worm: thread OD, root diameter, axial pitch (measure over 3 crests ÷ 3), single or double start
- [ ] Spline shaft: OD, number of splines, length from housing exit to tip
- [ ] Wand loop socket: depth on the spline, how the barbs latch (groove on the shaft?)
- [ ] Worm upper journal Ø, collar Ø and thickness
- [ ] Center distance worm axis ↔ wheel axis (or measure in the shell: bore center to worm seat center)
