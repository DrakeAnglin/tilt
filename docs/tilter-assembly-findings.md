# Findings from the first photo build (fix before merge, then delete this file)

Things the build showed that the docs or the design have wrong. Fixed together at the end.

1. **Case bolts are M3 × 20, not M3 × 25.** The 25s are too long. Owner used 20s; the guide already says 20.
   Fix: tilter README hardware table and assembly step 2, BOM (counts: M3 × 25 drops from 3 to 1, M3 × 20 from 2
   to 4), and the bolt length in `Tilter.py` (`case_bolts` comment, `h['bolt']`), then rerun the Fusion check.
2. **Worm top pin:** in the photo it sits in the worm; the design presses it into the case. Waiting on the owner:
   loose or tight in the worm?
3. **Sun piece goes in the motor shell** (with the pinion and cluster, guide C2), not into the bearing shell (README
   step 2). Move it in README steps 2 and 3.
4. **Planets bed side up** (away from the carrier): add to README step 1.
5. **Magnet:** push with a plastic tool; flush or a little below, never sticking out. Add to README step 8.
6. **Grease:** thin film, spread with a finger, wipe off the extra; too much gives a felt drag. Add to README.
7. **M1.6 motor screws: snug only**, they strip plastic. Add to README step 3.
8. **Motor pinion has a D-flat**: line it up with the shaft's flat. Add to README step 3.
9. **Temporary M3 × 16** hold the motor shell on if the sensor module is not ready (guide C5). M3 × 16 is not in
   the BOM yet. Decide: add it, or say "use the tray bolts without the tray" if they fit.
10. **Sensor board order:** README step 5 says the AS5600 must go on its studs before the tray, and "cannot go in
   afterwards". The build puts the tray on empty and pushes all boards in after (guide D3). Fix README steps 5 to 7.
11. **Motor leads before the tray:** solder them with only the motor in the way (guide D1). README step 7 has it after.
12. **Tray screws go through the tray before it goes on** (guide D2). Add to README step 6.
13. **Tray bolts tightened down,** not "snug only". README step 6 warns that a hard-tightened axle bolt bows the motor
   plate onto the cluster. Owner tightens fully and it turns fine; check and drop the warning if it holds.
14. **Motor lead colors:** the build uses a red/black pair to the motor; the sensor module page says a white pair.
   Fix on the sensor module page when we do that guide.
