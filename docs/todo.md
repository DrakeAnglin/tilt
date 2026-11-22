# To-do list

One list for the whole project, most important first. Updated 2026-11-21.
Check a box when it is done and tested. Older decisions are in [open-questions.md](open-questions.md).

## Now: finish the app for release
- [x] **Firmware updates from the app:** signed files; the controller refuses unsigned or altered files; Update in a room's About; beta channel and Install from File in developer builds (tested end to end with a local server)
- [x] **Demo mode:** "Try the Demo" room for App Review and screenshots
- [x] **Privacy:** privacy manifests (app and widget), [privacy-policy.md](privacy-policy.md), App Privacy answers in [app-store.md](app-store.md)
- [x] **Developer Mode** only in developer builds, never in an App Store build
- [x] **Older iOS:** now iOS 26 and later (builds clean; not run on an iOS 26 device)
- [x] **iPad:** layouts checked with the demo; App Store screenshots made for iPhone 6.9" and iPad 13"
- [x] **Tests:** `tools/app_tests.sh` (version check, join code, removal proof, pairing check, commands, demo room)
- [ ] **Owner steps (Apple account):** App Store Connect record, CloudKit schema to Production, export-compliance answer (see [app-store.md](app-store.md))
- [ ] **GitHub:** push the repo, make it public, set the firmware list address in the app, upload firmware with each release
- [ ] **Test on real devices:** wand-turn recovery, Add to Apple Home button, iCloud push between two accounts, Duo swipes, an update on your phone
- [ ] **Release-day clean-up:** remove the "Duo Test" user and, once the app does every update, the "Mac owner" key
- [ ] **TestFlight** with a few people, then the App Store

## Next
- [ ] **Battery life** (pinned): restart the baseline with the simulators closed; back off the app's 1.2 s reading when idle; then measure
- [ ] **Docs refresh:** `architecture.md`, `tilter-wiring.md`, `BOM.md`, `requirements.md` still describe older parts
- [ ] **Solar panel:** after battery life. Do not plug the charger's USB-C and the panel in together (unverified)
- [ ] **Controller box feet:** the box pinches the lift cord; add stick-on feet and note it in the box doc
- [ ] **Lift mechanism:** open a rail, photograph and measure the lift module ([lift-bonus.md](lift-bonus.md))
- [ ] **Stall timing:** retune for the faster gearing

## Backlog
- [ ] Scenes shared between devices (today they stay on the phone that made them)
- [ ] Quiet motor mode (gentle moves are small steps; each step is as loud as a normal move)
- [ ] Profile photo or initials for people
- [ ] Real reset button on PCB v3
- [ ] Trim `tilt_base.py` (old v0.4 code the tilter script still leans on)
- [ ] Noise: TPU pads between the tilter and the rail
- [ ] Alexa
- [ ] Three blinds moving at once (untested)
- [ ] Setup screen on a blind that has never been set up (unconfirmed)
- [ ] Build the other tilters (8 blinds, 3 controllers)
- [ ] Publish: GitHub, MakerWorld, license

## On hold
- **Controller PCB v3:** not to be ordered until the "must test on the v2 board" list passes (USB brown-out diode test first)

## Done
- [x] Everything committed to Git; repo cleaned out to one version of each thing (2026-11-21)
- [x] Tilter v0.9 printed (full assembly of that unit still to come)
- [x] App on the new phone
- [x] Widget and Control Center buttons
- [x] Opening animation
- [x] Sharing: ask to join, approve as Owner or User, remove people, auto-remove on the removed phone
- [x] iCloud notices built (push when someone asks to join; removal reaches a phone away from home)
- [x] Display name from Sign in with Apple
- [x] Layouts for wide screens: rooms and settings side by side, swipes, Blinds-tab shortcut
- [x] Schedules: whole row opens, Run Now, all blinds by default
- [x] Gentle open and close, Move to Position, one Stop button while moving
- [x] Open All / Close All and Scenes on the home page
- [x] Add to Apple Home page: in-app add, copy code, open Home
- [x] Code cleanup: Blinds file split by component, one command layer, duplicates and leftovers removed
- [x] Role-aware screens: users no longer see owner-only settings, setup or schedule editing
- [x] Firmware version check: the app warns when a controller's firmware is too old
- [x] Recover access by turning a blind's wand (built; real-hand test still open, see "Now")
