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

## Internals (measured with calipers, 2026-10-25)
Photos: [overview](../../docs/reference/tilter-opened-overview.jpg), [gear](../../docs/reference/tilter-opened-gear.jpg),
[worm](../../docs/reference/tilter-opened-worm.jpg).

### Worm wheel
| Feature | Value |
|---|---|
| Teeth | **16** |
| Outside diameter | **15.8 mm** |
| Tooth face width | **7.5 mm** |
| Hub ("barrel") length along the rod | **16.66 mm** (≈ housing thickness 16.5) |
| Barrel diameter | **12.5 mm** |
| Bore | 4 mm square |
| Derived module | 15.8 / (16 + 2) ≈ **0.88** → pitch diameter ≈ 14.0 mm |

### Worm (total length 31.15 mm), from top (gear end) to bottom (wand end)
| Section | Ø | Length |
|---|---|---|
| Upper journal pin | 5.0 | ≈ 2.5 |
| Threads (**single start**, confirmed) | **11.0** OD | **9.0** (≈ 3¼ crests visible) |
| Gap | shaft | ≈ 2.5 |
| Upper flange | 9.5 | 1.6 |
| Shaft between flanges (bearing in shell) | 5.6 | 8.4 |
| Lower flange | 9.5 | 1.77 |
| Splined drive to the wand-loop connector: **8 ridges**, ≈ 6.0 OD / ≈ 5.0 root | 5.6 nominal | ≈ 5 |
| **Sum** | | ≈ 30.8 (measured 31.15) |

Axial pitch: "≈ 7 mm across 3 teeth" (≈ 2 pitches + one crest width) and 9 mm of thread holding 3–4 crests → **≈ 2.75 mm**,
which matches module 0.88 (π × 0.88 = 2.76). The worm and wheel are a matched module ≈ 0.88 pair.

**Derived:**
- **Worm ratio = 16 : 1** (single start). 60° of rod = **2.67 worm turns**.
- Worm pitch diameter ≈ 11.0 − 2 × 0.88 ≈ 9.24 mm → **center distance ≈ (9.24 + 14.0) / 2 ≈ 11.6 mm**.
- Lead angle ≈ atan(2.76 / (π × 9.24)) ≈ 5.4°: **self-locking**.
- The wand loop connector engages only the bottom ~5 mm splined section (5.6 mm Ø).

## Chosen concept (v0.2): crossed helical at the factory 56° angle
The headrail has a **corner notch** (12 tall × 10.5 into the floor × 12 wide along the rod) where the factory tilter's
tube exits. A printed block fills it, and the housing presses between the rail walls. The adapter must exit through
that notch, which pins the worm angle near the factory 56°: only 66–67° would also allow a motor parallel to the worm,
and there the motor has ~0 mm clearance. Decision (owner, 2026-10-25): crossed helical at 56°.

| Item | Value |
|---|---|
| Worm angle | 56° (factory), adapter exits through the existing notch |
| Adapter | 8T 45° RH helical, mn 1.0 (PD 11.31, OD 13.0), 5 mm face, spline socket, Ø8.13 × 19 mm body, teardrop loop |
| Motor pinion | 7T 45° RH helical, mn 1.0 (PD 9.90, OD 11.6), 6 mm face, D-bore, Ø6.5 hub |
| Centers | 10.71 mm (incl. 0.1 extra). Not self-locking, so the wand back-drives the motor |
| Motor | N20 without encoder, axis swung 5° from the rod direction, in the lower front of the rail. ~1.9 mm clearances |
| Case | Full-width slab (55.4 mm press fit) + notch block + motor pod; split at the tilter mid-plane; 3× M2 |
| Verified in Fusion | Interference analysis: no contacts. Gear mesh: zero overlap at the right phase, ~6° backlash |

The spur/parallel v0.1 is in git history (commit 466ac59).

### Wand-loop connector (factory)
| Feature | Value |
|---|---|
| Socket depth on the spline | **5.3 mm** |
| Outer diameter | **8.13 mm** |
| Socket | 8-ridge internal spline matching the worm's drive end |
| Retention | Two flexible tabs. It snaps in through the housing after the shell is closed and locks against it, so the connector is replaceable |

## Still needed
- [ ] Optional check: center distance (square-bore center → worm axis in the shell), predicted ≈ 11.6 mm
