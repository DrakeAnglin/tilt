"""Find the spur-gear layout (motor parallel to the worm, shaft down) with the most clearance in the rail.

Coordinates (mm): X along the rod (0 = tilter mid-plane), Y across (-Y = room side), Z up from the rail floor.
s = distance along the worm axis from the thread center, positive toward the wand.
"""
import math, json, sys

def add(a, b): return tuple(x + y for x, y in zip(a, b))
def mul(a, k): return tuple(x * k for x in a)
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def sub(a, b): return add(a, mul(b, -1))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def unit(a): return mul(a, 1 / math.sqrt(dot(a, a)))
def dline(p, o, dr):
    v = sub(p, o); al = dot(v, dr); q = sub(v, mul(dr, al)); return math.sqrt(dot(q, q)), al

RAIL_HALF_W, RAIL_H, ROD_Z = 27.75, 36.5, 24.0
BARREL_R, BARREL_HALF = 6.25, 8.33
CD_WORM = 11.64
X = (1.0, 0.0, 0.0)

def frame(angle_deg):
    a = math.radians(angle_deg)
    d = (0.0, -math.cos(a), -math.sin(a))      # worm axis toward the wand
    n = (0.0, -math.sin(a), math.cos(a))       # rod axis -> worm axis
    p0 = add((0.0, 0.0, ROD_Z), mul(n, CD_WORM))
    return d, n, p0

def evaluate(angle, m, zg, zp, gs, phi, motor_len, face=5.0, hub=1.5, gap=0.5, ha=0.8, cd_extra=0.1):
    d, n, p0 = frame(angle)
    rg, rp = m * zg / 2, m * zp / 2
    cd = rg + rp + cd_extra
    C = add(p0, mul(d, gs))
    f = math.radians(phi)
    o = unit(add(mul(n, -math.cos(f)), mul(X, math.sin(f))))
    Pp = add(C, mul(o, cd))
    gb_face = add(Pp, mul(d, -(face / 2 + hub + gap)))
    u = mul(d, -1); w = unit(cross(u, o)); v = o
    pts = [add(add(add(gb_face, mul(u, l)), mul(w, sw)), mul(v, sv))
           for l in [i * motor_len / 8 for i in range(9)] for sw in (-6, 0, 6) for sv in (-5, 0, 5)]
    # gear rims checked at both faces (the 70° tilt drops the lower face well below the center plane)
    ts = [k * math.pi / 18 for k in range(36)]
    pr = [add(add(Pp, mul(d, sf)), add(mul(o, (rp + ha * m) * math.cos(t)), mul(w, (rp + ha * m) * math.sin(t))))
          for t in ts for sf in (-face / 2, face / 2)]
    gr = [add(add(C, mul(d, sf)), add(mul(n, (rg + ha * m) * math.cos(t)), mul(X, (rg + ha * m) * math.sin(t))))
          for t in ts for sf in (-face / 2, face / 2)]
    # the case wall under the lower faces needs room too
    lowest = min(p[2] for p in pr + gr)
    allp = pts + pr
    ys = [p[1] for p in allp]; zs = [p[2] for p in allp]
    c = dict(
        wall=min(min(ys) + RAIL_HALF_W, RAIL_HALF_W - max(ys), min(p[1] for p in gr) + RAIL_HALF_W),
        floor=min(min(zs), min(p[2] for p in gr)),
        top=RAIL_H - max(zs),
        barrel=min((dline(p, (0, 0, ROD_Z), X)[0] - BARREL_R) if abs(p[0]) <= BARREL_HALF + 0.1 else 99 for p in allp),
    )
    return min(c.values()), c, dict(C=C, Pp=Pp, o=o, d=d, n=n, p0=p0, gb_face=gb_face, cd=cd)

if __name__ == '__main__':
    angle, m, zg, zp, L = 70, 1.0, 14, 18, 25
    best = None
    for gs10 in range(195, 251, 5):
        for phi in range(30, 151, 5):
            mm, c, g = evaluate(angle, m, zg, zp, gs10 / 10, phi, L)
            if best is None or mm > best[0]:
                best = (mm, gs10 / 10, phi, c, g)
    mm, gs, phi, c, g = best
    print(json.dumps(dict(angle=angle, gear_s=gs, phi=phi, margin=round(mm, 2),
                          clear={k: round(v, 2) for k, v in c.items()},
                          C=[round(x, 3) for x in g['C']], Pp=[round(x, 3) for x in g['Pp']],
                          o=[round(x, 4) for x in g['o']]), indent=1))
