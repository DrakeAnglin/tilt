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

## Still needed (open the tilter, photograph with ruler)
- Worm: OD, length, shaft diameter at each end, number of starts (1 or 2 threads)
- Worm wheel: OD, tooth count, face width, how it's keyed to the square bore
- How the wand loop attaches to the worm shaft (molded in one piece, or pinned?)
