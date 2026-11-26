# Findings from the first photo build (fix before merge, then delete this file)

Things the build showed that the docs or the design have wrong. Fixed together at the end.

1. **Case bolts are M3 × 20, not M3 × 25.** The 25s are too long. Owner used 20s; the guide already says 20.
   Fix: tilter README hardware table and assembly step 2, BOM (counts: M3 × 25 drops from 3 to 1, M3 × 20 from 2
   to 4), and the bolt length in `Tilter.py` (`case_bolts` comment, `h['bolt']`), then rerun the Fusion check.
2. **Worm top pin:** in the photo it sits in the worm; the design presses it into the case. Waiting on the owner:
   loose or tight in the worm?
3. **Sun piece goes in after the bearing shell bolts**, not before (README step 2 has it before). Guide has it as B5.
4. **Planets bed side up** (away from the carrier): add to README step 1.
5. **Magnet:** push with a plastic tool; flush or a little below, never sticking out. Add to README step 8.
6. **Grease:** thin film, spread with a finger, wipe off the extra; too much gives a felt drag. Add to README.
