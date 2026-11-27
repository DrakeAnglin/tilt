# Tilt parts inventory

Private. Git ignores this file (`/inventory.md` in `.gitignore`), so it is never committed.
Made by the inventory skill from `hardware/BOM.md`. Ask Claude to change it: "ordered the motors", "the jacks
arrived", "bagged a tilter kit", "built a controller", "add a set of 2 blinds".

## Contents
1. [How to use](#how-to-use)
2. [Plan](#plan)
3. [Orders](#orders): [on order](#on-order), [to order](#to-order)
4. [Stock](#stock): [tilter](#tilter-parts), [controller](#controller-parts), [hub](#hub-parts),
   [shared supplies](#shared-supplies), [bench tools](#bench-tools)
5. [Optional parts](#optional-parts)
6. [Notes](#notes)
7. [Log](#log)

## How to use
- **Part names are links.** Click one to buy it.
- **Ordering:** buy everything in [To order](#to-order) in one go: split orders cost extra shipping. Tick ☐ to ☑,
  or tell Claude, and the row moves to [On order](#on-order) with its ETA.
- **Arrived:** the amount goes into **In stock** in the [Stock](#stock) tables, and its On order row goes away.
- **Bagging a kit:** its parts move from **In stock** to **Issued**.
- **Built:** a finished unit moves to **Assembled**. Once it is on a blind it moves to **Used**. From then on it counts
  as one unit in the [Plan](#plan), and its parts are no longer counted one by one.
- **Have** = what is on hand now (In stock + Issued). **Need** = what the plan still uses. **Spare after** = what is
  left once everything on order and to order has come and the plan is built.
- Printed parts aren't counted: print them when you make a kit.

## Plan
One controller runs a set of up to 3 blinds, grouped by cord reach. Each used port needs 1 RJ12 jack and 1 fuse.
Cords: 3.3 ft for the blind beside the controller, 6.6 ft for the next, 10 ft (or 6.6 ft with the controller in the
middle) for a 3rd.

{{plan}}
**Where the units are now:**

| Unit | Used | Assembled | Issued (kits) |
|---|---|---|---|
| Tilter | 0 | 0 | 0 |
| Controller | 0 | 0 | 0 |
| Hub | 0 | 0 | 0 |

## Orders

### On order

| Part | From | Qty | Ordered | ETA |
|---|---|---|---|---|

### To order
One combined purchase for the whole plan.

{{to_order}}
## Stock
Stages: **Used** = on a blind. **Assembled** = finished, not on a blind yet. **Issued** = bagged in a kit.
**In stock** = loose, free to issue. "Where it goes" uses the labels printed on the PCB (J4, C9 …), the same as the
[PCB build guide](docs/pcb-build.md).

{{stock}}
### Bench tools
From [BOM, Tools](hardware/BOM.md#tools).

| Tool | Have |
|---|---|

## Optional parts
Only what the plan chose goes into the order list. Change a choice by asking Claude.

{{optional}}
## Notes

## Log
