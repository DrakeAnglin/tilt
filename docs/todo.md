# To-do list

One list for the whole project, in the order I would do it. Updated 2026-11-21.
Older decisions and findings are in [open-questions.md](open-questions.md).

## 1. Now

| # | What | Notes |
|---|---|---|
| 1 | **Commit everything to Git first** | The last commit is tilter v0.5. Everything since is NOT in Git: tilters v0.6 to v0.9, the Apple Home firmware, the whole iPhone app, the tools. Nothing can be safely deleted until this is committed. |
| 2 | **Code cleanup** | Remove old versions so the repo (and the AI's working memory) is smaller. Keep: tilter v0.9 (and v0.8 for now), `firmware/blinds_matter`, the app, controller box V5, PCB v2. Candidates to remove: tilter v0.3 to v0.7 generators, STLs and tools; controller boxes V1 to V4; the old Arduino firmware `firmware/blinds` (its `secrets.h` and web UI are still used by the build: untangle first); bench and test sketches; build folders (about 1.3 GB, should be ignored, not tracked); archived docs. Also split the big firmware files and trim my memory notes. |
| 3 | **Battery life** | Ran 3 to 4 days on a charge. Charged to 100 % and unplugged 2026-11-21: use this run as the baseline. Find what drains it idle. Suspects: (a) sensor look-round every 1 to 3 s for hand-twist following (added 2026-11-16); (b) battery and status polling too often, by the controller itself and by the app, the widget and Apple Home asking it; (c) Wi-Fi kept up for Apple Home; (d) the doze mode, never measured; (e) logging and stats writes. Then cut each one. |
| 4 | **App: opening animation** | Quicker and more polished. Only on a cold start, not when the app comes back. |
| 5 | **App on the new phone** | Developer Mode on, register the phone, install. It joins with a sharing code from the old phone. |
| 6 | **App Store release prep** | Icon without see-through, screenshots, privacy answers, TestFlight first. Remove the Mac test client's owner key before release. |

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

## On hold
- **Controller PCB v3**: not to be ordered until the "must test on the v2 board" list passes (USB brown-out diode test first).
