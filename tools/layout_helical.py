"""Offline search for the crossed-helical layout: worm angle x motor swing. Mirrors TiltParts.layout()."""
import math

def add(a, b): return tuple(x + y for x, y in zip(a, b))
def mul(a, k): return tuple(x * k for x in a)
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def sub(a, b): return add(a, mul(b, -1))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def unit(a): return mul(a, 1 / math.sqrt(dot(a, a)))

HW, H = 27.75, 36.5
RA_G, RP_G, RA_P, RP_P = 6.507, 5.657, 5.80, 4.95
CD = RP_G + RP_P + 0.1
MOUTH, FACE_G, FACE_P, GAP = 18.97, 2.6, 6.0, 3.0
MO_LEN, MO_W, MO_H = 25.0, 12.0, 10.0

def evaluate(angle, rot, top_wall=1.2):
    a = math.radians(angle)
    X = (1.0, 0, 0)
    d = (0, -math.cos(a), -math.sin(a)); n = (0, -math.sin(a), math.cos(a))
    p0 = add((0, 0, 24.0), mul(n, 11.64)); S = lambda s: add(p0, mul(d, s))
    r = math.radians(rot)
    u = unit(add(mul(X, math.cos(r)), mul(n, math.sin(r))))
    off = unit(mul(cross(d, u), -1))
    gs = MOUTH + FACE_G / 2
    C = S(gs); Pc = add(C, mul(off, CD))
    vz = unit(sub((0, 0, 1), mul(u, dot((0, 0, 1), u)))); w = cross(u, vz)
    ts = [k * math.pi / 18 for k in range(36)]
    # pinion rim at both faces
    e1 = unit(cross(u, (0, 0, 1))) if abs(u[2]) < 0.99 else (1, 0, 0); e2 = cross(u, e1)
    pin = [add(add(Pc, mul(u, f)), add(mul(e1, RA_P * math.cos(t)), mul(e2, RA_P * math.sin(t)))) for t in ts for f in (-FACE_P/2, FACE_P/2)]
    # adapter gear rim at both faces
    g1 = n; g2 = X
    gear = [add(add(C, mul(d, f)), add(mul(g1, RA_G * math.cos(t)), mul(g2, RA_G * math.sin(t)))) for t in ts for f in (-FACE_G/2, FACE_G/2)]
    face = add(Pc, mul(u, FACE_P / 2 + GAP))
    mot = [add(add(add(face, mul(u, l)), mul(w, sw)), mul(vz, sh)) for l in (0, MO_LEN/2, MO_LEN) for sw in (-MO_W/2, MO_W/2) for sh in (-MO_H/2, MO_H/2)]
    allp = pin + gear + mot
    c = dict(
        floor=min(p[2] for p in allp),
        top=H - max(p[2] for p in mot),
        wall=min(min(p[1] for p in allp) + HW, HW - max(p[1] for p in allp)),
        # case top above the worm: thread pocket (r 5.9) and pin pocket end must sit under 36.3 - wall
        worm_cover=36.3 - max(S(-4.8)[2] + 5.9 * abs(n[2]), S(-7.3)[2] + 2.65 * abs(n[2])) - top_wall,
        # motor body vs worm-wheel barrel (r 6.25, |x|<=8.33) around the rod axis (0,0,24)
        barrel=min((math.hypot(p[1], p[2] - 24) - 6.25) if abs(p[0]) <= 8.4 else 99 for p in mot),
    )
    return min(c.values()), c

if __name__ == '__main__':
    rows = []
    for ang in range(60, 71):
        for rot in range(-40, 41, 5):
            m, c = evaluate(ang, rot)
            rows.append((round(m, 2), ang, rot, {k: round(v, 2) for k, v in c.items()}))
    rows.sort(reverse=True)
    for r in rows[:12]:
        print(r)
