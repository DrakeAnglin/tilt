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
| D1 | Drive point: tilter input (A) or tilt rod with tilter removed (B)? | B if torque allows (hidden, fast); A fallback | Needs measurements |
| D2 | N20 gear ratio | Choose from measured torque; 40 RPM for A, likely 15 RPM or worm N20 for B on large blinds | Needs measurements |
| D3 | Motor ports per controller: 4 (3 tilt + spare) or 6 (tilt + lift ×3)? | 4 for v1 board unless lift is proven early | Open |
| D4 | MCU | ESP32-S3-WROOM-1-N8 | Proposed |
| D5 | Firmware framework | Arduino-ESP32 3.x (Matter built in), ESP-IDF fallback | Proposed |
| D6 | Smart home protocol | Matter over Wi-Fi | Proposed: verify Alexa tilt handling early |
| D7 | Setup app | Device-hosted web app first, Flutter later | Proposed |
| D8 | Motor connector | RJ12 6P6C | Proposed |
| D9 | Supply | 5 V/3 A USB-C | Proposed |
| D10 | Isolation material | Test 95A TPU vs Bambu TPU for AMS (68D) | Test |
| D11 | Keep the manual wand? | — | Ask |
| D12 | License | CERN-OHL-S / MIT / CC BY-SA | Ask |

## Information needed from the owner
- [ ] Photos of the headrail internals (tilter, tilt rod, spring motors)
- [ ] Tilt rod shape and size. Is the 10 mm circle in the cross-section the tilt rod?
- [ ] Measurements from the largest blind
- [ ] Number of blinds, and how they group into controllers (which windows are within ~3 m of each other)
- [ ] Where outlets are relative to the windows
- [ ] Which hubs are in the house (Echo model? HomePod/Apple TV?)
