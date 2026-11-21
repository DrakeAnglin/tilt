# To-do list

One list for the whole project, in the order I would do it. Updated 2026-11-21.
Older decisions and findings are in [open-questions.md](open-questions.md).

## 1. Now

| # | What | Notes |
|---|---|---|
| 3 | **Battery life** | Ran 3 to 4 days on a charge. Charged to 100 % and unplugged 2026-11-21: use this run as the baseline. Find what drains it idle. Suspects: (a) sensor look-round every 1 to 3 s for hand-twist following (added 2026-11-16); (b) battery and status polling too often, by the controller itself and by the app, the widget and Apple Home asking it; (c) Wi-Fi kept up for Apple Home; (d) the doze mode, never measured; (e) logging and stats writes. Then cut each one. |
| 5 | **App on the new phone** | Developer Mode on, register the phone, install. It joins with a sharing code from the old phone. |
| 6 | **App Store release prep** | Icon without see-through, screenshots, privacy answers, TestFlight first. Remove the Mac test client's owner key before release. |
| 7a | **Docs refresh** | `architecture.md`, `tilter-wiring.md`, `BOM.md` and `requirements.md` still describe older parts in places. Bring them up to the current tilter, firmware and app. |

## 2. Next

| # | What | Notes |
|---|---|---|
| 7 | **Solar panel** | Not installed yet. After battery life, so we know how much it has to make up. Do not plug the charger's USB-C and the panel in together (unverified). |
| 8 | **Controller box feet** | The box pinches the lift cord under its middle. Stick-on rubber feet (owner handles the lift); add to the box's README. |
| 9 | **Lift mechanism: start the design** | Cordless, spring-assisted blinds. First step: open a rail, photograph and measure the lift module. See [lift-bonus.md](lift-bonus.md). |
| 10 | **Stall timing** | Still tuned for the old slow gearing. Retune for about 19 deg/s. |

## 3. Later

| # | What | Notes |
|---|---|---|
| 11 | Noise | TPU pads between the tilter and the rail; soft start and stop. |
| 12 | Alexa | Pair through the controller's Home pairing mode; check tilt. |
| 13 | Three blinds moving at once | Untested (only two so far). |
| 14 | Hand-crank setup screen and "Set Up Now" button | Not confirmed on a blind that has never been set up. |
| 15 | Controller hardware reset | No button resets ownership; a locked-out controller needs USB. |
| 16 | Build the other tilters | 8 blinds, 3 controllers planned. |
| 17 | Publish | GitHub, MakerWorld, license (ask before publishing). |

## Done
- Home Screen widget and Control Center buttons: confirmed working by the owner (2026-11-21).
- Tilter v0.9 printed, looks good (owner, 2026-11-21). Full assembly of that unit still to come.
- Everything committed to Git (2026-11-21).
- Repo cleaned out (2026-11-21): one version of each thing; old tilters, boxes, Arduino firmware and test sketches removed (still in the Git history).
- App opening animation: faster, cords and rails, cold start only.

## On hold
- **Controller PCB v3**: not to be ordered until the "must test on the v2 board" list passes (USB brown-out diode test first).
