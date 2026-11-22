# Lift: raising and lowering (not built yet)

Lift is part of the product plan and high on the list, but nothing is built. Today Tilt only tilts. This page keeps
the ideas so far. Words: **Lift**, **Lifter**, **Lift position** in [CONTEXT.md](../CONTEXT.md).

## What the headrail has
The owner's blinds are cordless. A spring in the headrail balances the blind's weight, so it stays where it is left.
A motor only has to beat friction and the spring's brake, not lift the whole blind.

In the owner's headrail the lift is a **separate, self-contained module**: two cord spools with gear rims and
constant-force spring drums. It is not connected to the tilt rod, and there is no shared lift shaft
([headrail notes](../hardware/mechanical/README.md#the-headrail)). Other blinds may differ:
[measure your blinds](measure-your-blinds.md).

## Ideas
1. **Drive the lift module's spools** (best fit for the owner's headrail): a second motor geared to one spool's gear
   rim. The spring still carries the weight. Many turns of travel: a 15 mm spool winds about 47 mm a turn, so a 1.5 m
   drop is about 32 turns.
2. **Drive a lift shaft**, on blinds that have one linking the spools: same mount style as the tilter.
3. **A motorized spool with its own cord** to the bottom rail. Works without touching the spring, but adds a visible
   cord. Child-safety rules apply (requirement E-6).
4. **Replace the spring with a motor.** The motor must then lift the full weight (several kg on big blinds), beyond an
   N20. Last resort.

Limits: stall-detect at the top (bottom rail meets the headrail) and the user's lowered Mark at the bottom. The
Lift position runs 0–100% between the two Marks, from the turn count.

## What it needs from the rest of the system
- **Controller:** the v3 concept reserves a fourth port, an RJ45 with doubled power wires, for a lifter
  ([pcb-v3-concept.md](pcb-v3-concept.md#the-lifter-port)).
- **Matter:** a blind becomes one window covering with two axes. Today the firmware sends tilt on Matter's lift
  channel; with real Lift, tilt moves to the tilt channel ([CONTEXT.md](../CONTEXT.md), "Window covering").
- **Power:** lifting draws peaks of several amps from the cell for a few seconds; the daily energy is small.
