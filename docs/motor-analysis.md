# Motor analysis: will the N20 work?

> **Historical.** Written before the design settled, about an encoder N20 driving the rod directly. The build uses a
> 6 V 300 RPM N20 (no encoder) through a printed worm, with an AS5600 for position: see the [README](../README.md).

**Candidate:** MECCANIXITY N20, 6 V, 40 RPM, metal gearbox, Hall encoder (Amazon B0F8NGRYGS, 2-pack).

**Short answer:** it's a good *fit* and a sensible first buy (cheap, tiny, encoder included, can't burn out the
way the servos did). Whether it's *strong enough* for the large blinds depends on **how** it drives
the blind (see "Where the motor connects"). That needs a measurement, not a guess. Buy a pair and measure
before designing around it.

## Why it fixes the v1 servo problems

| v1 problem | Why it happened | Why the N20 + encoder fixes it |
|---|---|---|
| Loud | Large servo gear train, often running constantly to hold position, rigidly coupled to a hard mount and the long hollow plastic headrail (a sounding board) | Small motor, only runs during moves; TPU isolation; 20+ kHz PWM so the drive itself doesn't whine |
| 180° limit | Hobby servos have a potentiometer with a hard stop | DC gear motor turns continuously; the encoder counts any number of turns |
| Burnout | The servo was always powered and fighting load to hold position. Heat built up for years | Motor is **off** when idle. A high-ratio gearbox holds position by friction. Firmware stall detection plus driver current limit stop it before damage |

## Specs (typical for this class. The listing doesn't publish a datasheet)

| Parameter | Typical value | Notes |
|---|---|---|
| Size | 12 × 10 mm body, ~35–40 mm long incl. encoder, 3 mm D-shaft | Fits the 55.5 × 36 mm headrail easily |
| Gear ratio | ~1:298–1:380 for 40 RPM | Exact ratio matters for encoder math. Check on arrival |
| Encoder | Magnetic, 2 Hall sensors, ~7 pulses/motor rev per channel (14–28 counts with quadrature) | × gear ratio = **thousands of counts per output turn**. Far more resolution than needed |
| Running current | ~0.1 A | |
| Stall current | ~0.2–0.7 A at 6 V | Measure. Sets the power supply and driver current limit |
| Stall torque (marketing) | ~2–4 kg·cm | Treat with suspicion |
| **Safe continuous torque** | **~0.5–1 kg·cm** | The number that matters. The last gear stage of N20 gearboxes is the weak point: high ratios can produce more torque than the gears survive |
| Speed at 5 V | ~33 RPM (≈ 5/6 of 6 V speed) | Running a 6 V motor at 5 V is fine. It's also slightly quieter |

> Rule of thumb for this project: **design to the motor's safe continuous torque, ≥ 2× the measured
> worst-case load.** Never rely on stall torque.

## Where the motor connects (this decides the torque you need)

Standard horizontal blinds work like this:

```
 wand (you twist it) ──► tilter (worm gear, in headrail) ──► tilt rod (runs the length of the headrail)
                                                               │
                                                               └─► tilt drums/cradles ──► ladder tapes ──► slats
```

The **tilter is a worm gear**: it reduces speed (many wand turns = one partial rod turn) and it is
**self-locking**: the rod can't drive it backwards. That's why your servo needed more than 180°: it was
on the wand/tilter-input side.

### Option A: drive the tilter input (where the wand attaches)
- Load torque is **low** (it's what your fingers apply to the wand), usually well under 1 kg·cm even on big blinds.
- Needs **many turns** (often 5–15 wand turns end to end). At ~33 RPM that's roughly 10–30 s. Slow but quiet.
- Position holding is free (worm self-locks).
- Downside: the tilter input is at the front/bottom of the headrail. The mount sits outside or at the end of the headrail, so it's more visible.
- **N20 verdict: very likely strong enough**, even at 40 RPM. Could even use a faster ratio (60–100 RPM) to shorten travel time.

### Option B: replace the tilter, drive the tilt rod directly (inside the headrail)
- The motor takes the tilter's place inside the headrail and couples to the tilt rod. Fully hidden, the cleanest result. This is how the commercial retrofit kits (e.g. MySmartBlinds) did it.
- The rod only needs **~180° or less** for full range, so travel is ~1 s at 40 RPM. Fast; we could choose a slower, stronger ratio.
- Load torque is **much higher**. The worm gear's reduction is gone, so the motor feels the full ladder/slat friction. On a very large blind this could reach several kg·cm.
- Holding relies on the N20 gearbox friction (spur gears, not self-locking). Should be fine because tilt loads are mostly balanced, but must be tested.
- Reversible: the tilter just unclips and goes in a bag.
- **N20 verdict: maybe.** Likely needs a **higher ratio (1:1000, ~15 RPM)** or a **worm-gear N20** for the largest blinds. Measure first.

### Option C: motorized tilter (keep the worm gear and the wand). **Now recommended**
Photos: [tilter side](reference/tilter-side.jpg), [tilter gears](reference/tilter-worm-gear.jpg). The factory tilter is a clear
plastic housing: worm wheel with a 4 mm square bore on the rod, worm on an angled input shaft that exits at the wand hook.

Idea: a printed tilter housing that reuses the factory worm + worm wheel (or printed copies) and adds an N20 coupled to
the **back end of the worm shaft**. Wand and motor both sit on the worm (input) side.

**Important:** the motor can only go on the *worm* side. A motor on the rod side would have to back-drive the worm,
which is self-locking, so it can't. That rules out "Option B + keep the wand in place".

Why this is better than B:
- **Manual use still works.** The wand stays.
- **Holding is free.** The self-locking worm holds the slats with zero power, even on the heaviest blind.
- **Torque need drops** by the worm ratio, so the N20 is comfortably strong enough. Strength stops being a risk.
- **Use a low-ratio N20 (≈1:30–1:50)** so turning the wand by hand can back-drive the motor easily. The driver idles in
  *coast* mode (not brake), and **the encoder still counts manual wand turns**, so position stays correct.
- Travel stays quick: e.g. 10 worm turns at ~300 RPM output (1:50 at 5 V) ≈ 2 s, ramped and PWM'd slower for quiet.
- For **MakerWorld** this is the most universal product: "a drop-in motorized tilter for 4 mm square rods" (adapters for other rod sizes).

Costs / risks:
- New housing design around an **angled worm shaft** in a 36 mm tall rail. The N20 (12 × 10 mm) must fit on the worm axis behind the worm.
- If the controller is unpowered while someone turns the wand, those turns are missed. Optional fix: an **AS5600 magnetic
  absolute angle sensor** reading a magnet on the tilt rod (the rod turns < 360° over full range), which also removes the need for homing.
- Worm meshes make a little noise. The factory molded worm is quieter than a printed one, so reuse it where possible.

**Recommendation:** Option C. Option B remains the fallback if the motorized tilter can't be packaged in the headrail.
Needed: wand turns for full travel (gives the worm ratio), torque at the wand hook with the tilter installed, tilter dimensions,
and which end of the headrail the tilter sits at.

## Alternatives if the N20 is too weak or too noisy

| Motor | Size | Pros | Cons |
|---|---|---|---|
| **N20 1:1000 (~15 RPM)** with encoder | Same as above | Drop-in, ~2.5× the torque | Gearbox strength still limits it. Slower |
| **N20 worm-gear motor** (e.g. "GW12-N20"/"N20 worm") with encoder | ~12 × 25 × 35 mm, right-angle shaft | **Self-locking** (holds a heavy blind with zero power), higher torque, right angle can simplify headrail layout | Bulkier. Worm gears can be a bit louder; find one with an encoder |
| **GA12-N20 / JGA12** (larger gearbox, same motor) | 12 mm, slightly longer | Stronger gearbox options | Few with encoders |
| **28BYJ-48 stepper** (5 V) | 28 mm Ø | Very cheap, no encoder needed, ~1:64 gearbox holds position. Can run near-silent if converted to bipolar and driven by a TMC2209 | 28 mm is tight in a 36 mm headrail, lower torque than a high-ratio N20, open loop (can miss steps) |
| **Commercial tubular/tilt motor** | — | Proven | Defeats the purpose |

## Noise plan (requirement P-1)

1. **20–25 kHz PWM**: kHz-range PWM makes the windings sing audibly. Above 20 kHz it's inaudible. (DRV8833 handles up to ~50 kHz.)
2. **Soft start / soft stop** ramps (~200–300 ms): removes the "clunk" at start and stop and reduces gear impact.
3. **Run slower than max** when time allows: noise rises sharply with motor RPM. 5 V instead of 6 V already helps.
4. **Decouple, don't just soften:** a rigid printed cradle (PETG) holds the motor through a **soft TPU sleeve/grommets**, and the cradle touches the headrail only through TPU pads. The headrail is a long, thin-walled hollow plastic channel: an acoustic box that **amplifies** vibration (plastic rings less than metal, but the thin walls act like a speaker cone). That was probably a big part of v1's noise.
5. **TPU hardness:** Bambu "TPU for AMS" is **Shore 68D**: quite stiff, close to a hard plastic for damping. Fine for flexible couplers and structural clips, but for **isolation** a softer TPU (95A, or 85A/90A) damps far better. Plan: print the isolators in 95A or softer and test 68D against them.
6. **Torsionally stiff, axially/radially compliant coupler** between motor shaft and tilt rod (e.g. TPU "jaw/spider" coupler) so misalignment doesn't make the gearbox grind.
7. Use brake mode (both driver outputs low) when idle. It adds damping without consuming power.

## Test plan when the motors arrive

1. Measure no-load RPM and current at 5 V; count encoder pulses per output revolution (derives the real gear ratio).
2. Measure stall current (briefly!) → sets the DRV8833 current limit resistor.
3. Torque test: lever arm + luggage/kitchen scale on the output shaft at a slowly increasing load; note where speed collapses and where it stalls.
4. Compare with the blind measurements from [measure-your-blinds.md](measure-your-blinds.md).
5. Noise: phone SPL meter at 1 m, motor free vs. in a rigid mount vs. a TPU-isolated mount, PWM at 1 kHz vs. 20 kHz.
