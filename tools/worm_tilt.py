"""How far can the one-piece worm tip inside its bearing clearances, and what does it hit when it does?

  python3 tools/worm_tilt.py [barrel_clear collar_clear exit_clear]

The worm is a rigid shaft; its axis may sit anywhere the bearing surfaces allow (|offset(s)| <= radial clearance at
every bearing station). For each non-bearing surface the worst-case offset of the axis is compared with that surface's
radial clearance: offset > clearance means it can rub the case when the worm tilts.
"""
import itertools
import math
import os
import sys
from unittest.mock import MagicMock

sys.modules['adsk'] = MagicMock()
sys.modules['adsk.core'] = sys.modules['adsk'].core
sys.modules['adsk.fusion'] = sys.modules['adsk'].fusion
import importlib.util

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sp = importlib.util.spec_from_file_location('t4', os.path.join(REPO, 'hardware/mechanical/fusion/TiltPartsV4/TiltPartsV4.py'))
t = importlib.util.module_from_spec(sp)
sp.loader.exec_module(t)
P = t.P
L = t.layout()
half, sg, sb = L['half'], L['s_g0'], L['s_back']
cl_end = sb + P['collar_len']
bc = float(sys.argv[1]) if len(sys.argv) == 4 else P['barrel_clear']
cc = float(sys.argv[2]) if len(sys.argv) == 4 else P['collar_clear']
ec = float(sys.argv[3]) if len(sys.argv) == 4 else P['collar_clear']
# wand exit: from the collar step to where the shaft leaves the case (first s where the axis exits the envelope)
s_exit = cl_end
while s_exit < cl_end + 30:
    y, z = L['S'](s_exit)[1:]
    if z < P['case_floor'] or y < -P['case_w'] / 2 or (abs(y - (-P['case_w'] / 2)) < P['notch_d'] and z < P['notch_h'] - 2):
        break
    s_exit += 0.1
hole = P['top_pin_len'] - P['top_pin_case'] - P['thread_end_clear'] + 0.4
bearings = [('barrel', P['thrust_s'], sg, bc), ('collar', sb, cl_end, cc), ('wand exit', cl_end, s_exit, ec)]
if P.get('top_pin_d'):          # steel pin fixed in the case, running in a hole in the worm's thread end
    bearings.append(('top pin', -half, -half + hole, P['top_pin_hole_clear']))
stations = [(s, c) for _, a, b, c in bearings for s in (a, b)]
others = [('thread top end', -half, P['thread_clear']), ('thread bottom end', half, P['thread_clear']),
          ('neck', P['thrust_s'] - 0.1, P['neck_clear']),
          ('gear, thread side', sg - 1.0, 0.4), ('gear, collar side', sb, 0.4)]


def worst(at):
    """Max |offset| of the axis at s=at over all lines that respect every bearing station."""
    best = 0.0
    pts = [(s, sgn * c) for s, c in stations for sgn in (1, -1)]
    for (s1, e1), (s2, e2) in itertools.combinations(pts, 2):
        if abs(s1 - s2) < 1e-6:
            continue
        k = (e2 - e1) / (s2 - s1)
        line = lambda s: e1 + k * (s - s1)
        if all(abs(line(s)) <= c + 1e-9 for s, c in stations):
            best = max(best, abs(line(at)))
    return best


tilt = max(abs((sgn2 * c2 - sgn1 * c1) / (s2 - s1)) for (s1, c1), (s2, c2) in itertools.combinations(stations, 2)
           for sgn1 in (1, -1) for sgn2 in (1, -1) if abs(s2 - s1) > 1e-6
           if all(abs(sgn1 * c1 + (sgn2 * c2 - sgn1 * c1) / (s2 - s1) * (s - s1)) <= c + 1e-9 for s, c in stations))
print('bearings: ' + ', '.join('%s s %.1f..%.1f c%.2f' % b for b in bearings))
print('max tilt %.2f deg; axis offset at the thread center (mesh) %.2f mm' % (math.degrees(math.atan(tilt)), worst(0.0)))
for name, s, c in others:
    w = worst(s)
    print('  %-20s s=%6.2f  can move %.2f mm, room %.2f mm  %s' % (name, s, w, c, 'RUBS' if w > c else 'clear'))
