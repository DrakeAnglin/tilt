"""Check the ControllerV4 dev board on its own (no box): part bodies don't collide, and the wiring list makes exactly the
intended nets (nothing missing, nothing shorted).

  python3 tools/devboard_check.py
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('cv4', os.path.join(HERE, '../hardware/mechanical/fusion/ControllerV4/ControllerV4.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
H, HN = M.H, M.HN

# ------------------------------------------------------------------ physical
def bodies(parts):
    out = []
    for p in parts:
        for b in p.boxes:
            if 'tape' in b[0]:
                continue
            out.append((p.name, 'box', b[0], b[1:]))
        for nm, p1, p2, r in p.cyls:
            if abs(p1[0] - p2[0]) < 1e-9 and abs(p1[1] - p2[1]) < 1e-9:          # standing cylinder
                out.append((p.name, 'cyl', nm, (p1[0], p1[1], r, min(p1[2], p2[2]), max(p1[2], p2[2]))))
            else:                                                               # lying: use its box
                lo = [min(p1[k], p2[k]) - (r if abs(p1[k] - p2[k]) < 1e-9 else 0) for k in range(3)]
                hi = [max(p1[k], p2[k]) + (r if abs(p1[k] - p2[k]) < 1e-9 else 0) for k in range(3)]
                out.append((p.name, 'box', nm, (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])))
    return out


def gap(a, b):
    """Plan clearance (mm) between two bodies whose height ranges overlap; None if heights don't overlap."""
    za = a[3][4:6] if a[1] == 'box' else a[3][3:5]
    zb = b[3][4:6] if b[1] == 'box' else b[3][3:5]
    if za[1] <= zb[0] or zb[1] <= za[0]:
        return None
    if a[1] == 'cyl' and b[1] == 'cyl':
        return math.hypot(a[3][0] - b[3][0], a[3][1] - b[3][1]) - a[3][2] - b[3][2]
    if a[1] == 'cyl' or b[1] == 'cyl':
        c, r = (a, b) if a[1] == 'cyl' else (b, a)
        x, y, rad = c[3][:3]
        x0, x1, y0, y1 = r[3][:4]
        dx, dy = max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)
        if dx == 0 and dy == 0:
            return -rad
        return math.hypot(dx, dy) - rad
    a0, a1, ay0, ay1 = a[3][:4]
    b0, b1, by0, by1 = b[3][:4]
    dx = max(b0 - a1, a0 - b1)
    dy = max(by0 - ay1, ay0 - by1)
    if dx < 0 and dy < 0:
        return max(dx, dy)
    return math.hypot(max(dx, 0), max(dy, 0))


# ------------------------------------------------------------------ nets
EXPECT = {
    'GND': ['h2', 'i2', 'j2', 'a12', 'a13', 'a18', 'a24', 'i9', 'j12', 'a14', 'f14', 'i14', 'b24', 'd24', 'f24', 'i24',
            'a15', 'a16', 'a17', 'a20', 'a21', 'a22'],
    'VBAT': ['j13', 'j24', 'j6', 'j7', 'j15', 'j16', 'j17', 'j20'],
    '5V': ['h1', 'j1', 'j5'],
    '3V3': ['h3', 'i3', 'j3'],
    'STAT': ['b10', 'a10', 'j4'],
    'VDIV': ['b6', 'a6', 'j8', 'j9', 'j10'],
    'ADC0': ['b3', 'a3', 'c12', 'c13', 'c14'], 'ADC1': ['b4', 'a4', 'd13', 'd14'], 'ADC2': ['b5', 'a5', 'g12', 'g13', 'g14'],
    'ANG1': ['b11', 'b12'], 'ANG2': ['d11', 'd12'], 'ANG3': ['f11', 'f12'],
    'EN1': ['a7', 'b7'], 'EN2': ['a8', 'b8'], 'EN3': ['a9', 'b9'],
    'P3IN1': ['a1', 'b1'], 'P3IN2': ['a2', 'b2'], 'P1IN1': ['i6', 'h6'], 'P1IN2': ['i5', 'h5'],
    'P2IN1': ['i4', 'h4'], 'P2IN2': ['i8', 'h8'],
    'PWR': ['d23', 'f23', 'g23'], 'USB+': ['e23', 'e24'], 'SOL+': ['h23', 'h24'], 'BATT+': ['c24'],
}


def netlist():
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def join(a, b):
        parent[find(a)] = find(b)

    for f, t, note in M.WIRES:
        if note.startswith(('GND rail', 'VBAT rail')):                    # a whole column range
            i0, m = H(f)
            i1, _ = H(t)
            for i in range(min(i0, i1), max(i0, i1)):
                join(HN(i, m), HN(i + 1, m))
        elif 'over' in note:                                   # bridge across the hole between
            (i0, m0), (i1, m1) = H(f), H(t)
            mid = HN(i0, (m0 + m1) // 2)
            join(f, mid)
            join(mid, t)
        else:
            join(f, t)
    return find


def main():
    parts = M.layout()
    rep = M.check(parts)
    bs = bodies(parts)
    tight = []
    for i in range(len(bs)):
        for j in range(i + 1, len(bs)):
            if bs[i][0] == bs[j][0]:
                continue
            g = gap(bs[i], bs[j])
            if g is not None and g < 0.3:
                tight.append('%s / %s: %.2f mm' % (bs[i][2], bs[j][2], g))
    find = netlist()
    errs = []
    for net, holes in EXPECT.items():
        roots = {find(h) for h in holes}
        if len(roots) > 1:
            errs.append('OPEN  %s: %s' % (net, ', '.join('%s' % h for h in holes)))
    roots = {net: find(holes[0]) for net, holes in EXPECT.items()}
    seen = {}
    for net, r in roots.items():
        if r in seen:
            errs.append('SHORT %s <-> %s' % (seen[r], net))
        seen[r] = net
    print('\n'.join(rep))
    print('parts closer than 0.3 mm (negative = overlap):', tight or 'none')
    print('nets:', errs or 'all %d nets connected, none shorted' % len(EXPECT))
    return 1 if (tight or errs) else 0


if __name__ == '__main__':
    sys.exit(main())
