# Open questions & things the original list missed

## Things to add to the requirements (now in requirements.md)
1. **Calibration & homing:** encoders are relative; the blind's position must be learned and re-learned (F-4, F-7).
2. **Stall/jam protection:** the gearbox is the weak point. Hardware current limit + firmware stall stop (F-5).
3. **Power-loss memory:** position survives outages (F-3).
4. **What "closed" means:** slats down or up; "open" for tilt is the *middle* of travel, not an end (F-4).
5. **Manual use:** what happens if someone grabs the wand? With Option B the wand is removed; with Option A, hand-turning would back-drive the N20 (bad). Decide whether wands stay.
6. **OTA updates** (C-6) and **local control without cloud** (C-5).
7. **Physical button** for when Wi-Fi is down or for guests (F-8).
8. **Schedules / sunrise-sunset** (F-10). Can also live in Apple Home/Alexa routines.
9. **Cable routing** from one controller to 3 windows: lengths, connector, how it looks (E-5).
10. **Where the controller lives** and how the USB-C cable reaches the outlet without looking messy (M-7).
11. **Reversible install** so renters / MakerWorld users can try it (M-3).
12. **Variety of blinds** for MakerWorld: parametric mounts for different headrail sizes and tilt rod shapes (M-5).
13. **Child safety** for the lift bonus (E-6).
14. **License** before publishing.
15. **Measuring torque before committing to a motor:** see [measure-your-blinds.md](measure-your-blinds.md).

## Decisions needed

| # | Question | Recommendation | Status |
|---|---|---|---|
| D1 | Drive point: tilter input (A) or tilt rod with tilter removed (B)? | **C: motorized tilter** (keep worm + wand, N20 on the worm input). B fallback | Reopened: C recommended |
| D2 | N20 gear ratio | Choose from measured torque; 40 RPM for A, likely 15 RPM or worm N20 for B on large blinds | Needs measurements |
| D3 | Motor ports per controller: 4 (3 tilt + spare) or 6 (tilt + lift ×3)? | 4 for v1 board unless lift is proven early | Open |
| D4 | MCU | ESP32-S3-WROOM-1-N8 | Proposed |
| D5 | Firmware framework | Arduino-ESP32 3.x (Matter built in), ESP-IDF fallback | Proposed |
| D6 | Smart home protocol | Matter over Wi-Fi | Proposed: verify Alexa tilt handling early |
| D7 | Setup app | Device-hosted web app first, Flutter later | Proposed |
| D8 | Motor connector | RJ12 6P6C | Proposed |
| D9 | Supply | 5 V/3 A USB-C | Proposed |
| D10 | Isolation material | Test 95A TPU vs Bambu TPU for AMS (68D) | Test |
| D11 | Keep the manual wand? | Yes, with Option C | Owner prefers keeping it |
| D12 | License | CERN-OHL-S / MIT / CC BY-SA | Ask |

## Information needed from the owner
- [ ] Photos of the headrail internals (tilter, tilt rod, spring motors)
- [ ] Tilt rod shape and size. Is the 10 mm circle in the cross-section the tilt rod?
- [ ] Measurements from the largest blind
- [ ] Number of blinds, and how they group into controllers (which windows are within ~3 m of each other)
- [ ] Where outlets are relative to the windows
- [ ] Which hubs are in the house (Echo model? HomePod/Apple TV?)

## Findings from headrail photos (2026-10-25)

| Photo | What it shows |
|---|---|
| [top view](reference/headrail-top-view.jpg) | Cordless **lift module**: two lift-cord spools with gear rims, brass-colored constant-force **spring drums** between them. Self-contained, held by two screws |
| [end, tilt drum](reference/headrail-end-tilt-drum.jpg) | **Tilt drum** (owner's printed copy) in its white cradle, on the **square steel tilt rod** |
| [end profile](reference/headrail-end-profile.jpg) | U-channel profile (matches the cross-section sketch). Tilt rod sticks out past the last cradle: **free space at the end of the headrail** |
| [square rod](reference/headrail-square-tilt-rod.jpg) | Square tilt rod runs the full length above a long perforated plastic part |
| [ladder cords](reference/tilt-drum-ladder-cords.jpg) | Factory tilt drum with ladder cords tied on |
| [printed drum](reference/printed-tilt-drum-front.jpg), [angle](reference/printed-tilt-drum-angle.jpg) | Owner's printed tilt drum: square bore, two cord slots |

Conclusions:
- Headrail and all internals are **plastic** (not aluminum). Mount by sliding/snapping into the channel like the factory cradles. No clamping of thin walls.
- The tilt rod is **square**, so a printed square-socket coupler is trivial and can't slip.
- The tilt drums only need **about a half turn** of the rod for full range. Driving the rod directly (Option B) means short, fast moves.
- There's room at the **end of the headrail**, past the last cradle, for a motor sled coupled to the rod end. This is the leading design.
- **Lift is a separate, self-contained module** (spools geared to the spring drums), not connected to the tilt rod. Motorizing lift means meshing with the spool gear rim or the spring drum. Possible, but it's its own sub-project (see lift-bonus.md).
- The owner already has CAD for the tilt drum, which gives the exact square size and drum geometry.

Still unknown:
- [x] Square rod size: **4 mm square**
- [x] Wand + tilter gears: **removed**. Motor drives the rod directly (decision D1 = Option B, D11 = no wand)
- [x] Long perforated part = the **lift/holding mechanism**
- [x] Free length end cap → first tilt cradle: **110 mm**
- [x] Rod axis: **24 mm above the inner floor**, centered
- [ ] How far the rod sticks out past the first cradle
- [ ] **Wand turns** for full travel, closed → closed (gives the worm ratio)
- [x] Torque: low, finger-twistable. N20 strength is not a concern (exact number still nice to have)
- [x] Tilter sits in the 110 mm pocket, rod passes through the worm wheel
- [x] Clearance above the installed headrail: ~6.5 mm
- [x] Tilt travel: **11–12 wand turns** closed → closed (5–6 open → closed) ≈ 250–270° of rod. (Earlier "60°" was the slat angle)
- [x] Tilter housing: 16.5 mm thick, worm at ~67°, worm back end enclosed (see hardware/mechanical/tilter-analysis.md)
- [ ] Open the tilter (3 screws): worm + wheel sizes, tooth count, worm starts, how the wand loop attaches
- [ ] Exact wand turns closed → closed (when reassembled)
- [ ] Torque at the rod end with the tilter disengaged ([measure-your-blinds.md](measure-your-blinds.md))
