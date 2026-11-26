# Findings from the first photo build (fix before merge, then delete this file)

Done: the tilter README's assembly now points to the step-by-step guide (fixes the old order, sun piece, board
order, motor leads, grease, magnet, planets, tightening); BOM and README screw counts (case bolts M3 × 20, M3 × 16
listed).

Still open:
1. **Case bolt length in the CAD:** `Tilter.py` still models the case bolts as M3 × 25 (`h['bolt']`, shared with the
   sensor bolt). Change the case bolts to 20 and rerun the Fusion check.
2. **Worm top pin:** in the photo it sits in the worm; the design presses it into the case. Waiting on the owner.
3. **Planets "printed side up":** guide says bed face up, away from the carrier. Waiting on the owner.
4. **Sensor module page:** motor leads are a red/black pair in the build (page says white); give short real wire
   lengths (very little room behind the boards). Do with the sensor module guide.
5. **Fusion assembly sweep** was done in the old order; sweep the new order (tray on empty, boards in after).
