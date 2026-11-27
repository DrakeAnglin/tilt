---
name: inventory
description: Plan a Tilt build and keep its parts list in a private inventory.md. Use when a builder asks what to buy for their blinds, wants a stock check, or says they ordered, received, bagged or built something.
---

The builder's `inventory.md` sits at the repo root. Git ignores it (`/inventory.md` in `.gitignore`); it holds their
counts, orders and dates, so it stays out of every commit, issue and pull request.

**The parts lists are the source of truth.** `tools/inventory.py` reads `hardware/BOM.md` and `docs/pcb-build.md`
on every run, so counts, pack sizes and links are always current. Run it for every number you write: never type a
count, a pack size or a link from memory. `python3 tools/inventory.py --help` lists the options; `parts` lists each
part's KEY for `--have` and `--on-order`.

Talk to the builder in plain American English, one question at a time.

## 1. Plan

No `inventory.md` yet? Ask, one at a time:

1. **The blinds, in sets.** One controller runs up to 3 blinds within cord reach (3 m), so a set is the blinds one
   controller can reach. For each 3-blind set: does the controller sit in the middle (both other blinds 6.6 ft away)
   or at one end (the far blind needs 10 ft)?
2. **Solar: yes or no.** Yes: how many panels per controller (1 to 6).
3. **A JST-XH crimper: yes or no.** No: pre-crimped leads replace the crimp pins.
4. **A Tilt Hub already?** One per home, so a second build usually has one. No hub yet: is there a spare 5 V USB plug
   in the house for it (a phone charger)? No: `--hub-plug` buys one.
5. **Extras, only if they come up:** a cord through a wall (a printed wall plug each side, a drill and a 5/8 in bit).

Then show the plan from `python3 tools/inventory.py order --set 3 --set 3:middle ...` and the plan table from `new`.
Done when the builder agrees with the sets, the cord lengths and the unit counts.

## 2. Stock check

Walk the parts the plan uses, one at a time, in the order `new` lists them (tilter, controller, hub, shared, then the
[BOM tools](../../../hardware/BOM.md#tools)). For each: "How many <part> do you have?" Count only what is
physically on hand. A kit they own covers its parts: a resistor kit, a ceramic capacitor kit, a JST-XH kit (headers,
housings, crimp pins), a 2.54 mm female header strip (the ESP sockets) → `--have KEY=kit`.

Parts they own that the plan does not use (an older motor, a part from another project): note them under **Notes**
as "not used by this build" and leave them out of the tables.

Done when every part the plan uses has a count, "kit" or "plenty".

## 3. Create the file

```
python3 tools/inventory.py new --set ... [--hub 0] [--hub-plug] [--solar N] [--no-crimper] --have KEY=N ... --out inventory.md
```

Then fill in by hand: the stage columns from the stock check (loose counts in **In stock**), the bench tools
table (Have: yes or no), Notes, and the first Log line. Make sure `/inventory.md` is in `.gitignore`. Done when
the file has every section (Contents, How to use, Plan, Orders, Stock, Optional parts, Notes, Log) and the To order
table matches a fresh `order` run.

## 4. Keep it current

Each change: edit the file, then add one Log line, `- YYYY-MM-DD: what changed`, newest last.

| Builder says | Do |
|---|---|
| "ordered X" | Move X's row from To order to **On order**: part link, store, quantity (packs × pack), order date, ETA (ask). |
| "X arrived" | Add the quantity to X's **In stock**; remove its On order row. Check-on-arrival steps: [BOM](../../../hardware/BOM.md#check-on-arrival). |
| "bagged a kit" | Move one unit's parts from **In stock** to **Issued**; Issued kits +1 in the Plan's unit table. |
| "built one" | Its parts leave Issued; the unit's **Assembled** +1. |
| "it's on the blind" | The unit moves from Assembled to **Used**. |
| A plan change (a set added or removed, solar, crimper, hub plug) | Update the Plan, then rerun `order`. |

Rerun `order` whenever the plan, Have or On order changes, and replace the whole To order table with its output.
Pass `--have` as In stock + Issued, `--on-order` from the On order rows, and plan only the units still to be built:
a finished unit counts as one unit, so its parts are no longer needed.

## Rules for the order list

- **One combined purchase.** Every part the plan still needs, from every store, in one table. Never split it into
  phases: each extra order costs shipping.
- **Have** is only what is on hand. **Need** is one plain number. Rows the builder can cover drop out.
- **Optional parts** (solar, pre-crimped leads, the hub's USB wall plug, the printed wall plug for a cord through a wall, the M3 × 16 helper screws from
  [tilter assembly, C5](../../../docs/tilter-assembly.md)) appear only when the plan chose them. The M3 × 16 come
  from the M3 kit.
- A wrong number from the helper is a bug in `tools/inventory.py` or a change in the BOM's layout: say so to the
  builder, then fix the helper (with a test) rather than hand-editing the table.
