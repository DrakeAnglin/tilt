# Bonus: motorized raise/lower

Cordless blinds are a good starting point: a **spring motor** in the headrail counterbalances the blind's weight,
so it stays wherever you leave it. That means a motor only has to overcome friction and the spring's brake,
**not lift the whole blind**. Much less torque than a corded lift.

## What's typically inside a cordless headrail
- One or two spring motor units (a clock-type spring on spools)
- Lift cord spools/drums, one per lift cord
- Often a **lift shaft** (square/hex rod) linking the spools and spring units so both sides wind together
- Sometimes a friction brake/clutch

Photos of the headrail internals ([measure-your-blinds.md](measure-your-blinds.md) §3) decide which idea below fits.

## Idea 1: drive the existing lift shaft (best, if there is one)
- A second N20 (or a worm N20 for self-locking) couples to the lift shaft at the headrail end, same mount style as tilt.
- The spring keeps doing the heavy lifting; the motor just "assists" up and down.
- Many turns of travel: e.g. 15 mm spool Ø → ~47 mm/turn → 1.5 m drop ≈ 32 turns ≈ 1 min at 33 RPM. A faster ratio (100–150 RPM) is better here *if* torque allows.
- Limits: stall-detect at the top (bottom rail hits headrail) plus a calibrated bottom count. Slack-cord detection at the bottom is a nice-to-have.

## Idea 2: motorized spool driving a separate cord
If the spring units are self-contained (no shared shaft), add our own thin cord from a printed spool in the headrail
to the bottom rail, alongside the existing cords. The motor pulls down / lets the spring raise. Works without touching
the spring motors, but adds a visible cord. Child-safety rules apply (E-6).

## Idea 3: replace the spring motors with a motorized spool shaft
Most invasive; the motor must lift the full weight (large blinds can be 3–6 kg → several kg·cm even on a small spool),
which is beyond an N20. Would need a larger motor (25 mm gear motor or a worm gear motor at 9–12 V). Last resort.

## Controller impact
- 3 blinds × (tilt + lift) = 6 motors → 3× DRV8833 and 6 encoder counters. ESP32-S3 has 4 hardware counters
  (the rest would use GPIO interrupts, fine at these speeds), or switch to the classic ESP32 (8 counters).
  **Decide before the PCB layout** whether v1 boards get 4 or 6 motor ports. See [open-questions.md](open-questions.md).
- Matter: switch the covering type to `BLIND_LIFT_AND_TILT`.
