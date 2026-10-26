"""Printability check for the two tilter case halves (run inside Fusion through FusionBridge).

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_wallcheck.py --timeout 600
  (prepend GEN = '<generator path>' to the code to check another version)

Uses exactly the geometry TiltParts builds (case_plan): envelope, trims, cavities, per-half holes and pegs, modelled
as signed-distance functions. For every pocket / bore / hole surface it marches along the surface normal INTO the
material until it reaches emptiness (another pocket, the outside, or the split face) and records that wall thickness.
Grazing hits (ray running parallel to the other surface, e.g. where a bore exits a face) are ignored; only walls the
ray actually crosses count.

Also reports overhangs in each half's print orientation (both print on their backs, split face up): pocket ceilings
whose outward normal points along the build direction and that are not open to the top.

Thresholds: 1.2 mm general walls (3 perimeters at 0.4 mm); 1.6 mm around screw / pilot / insert / peg holes.
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
try:
    GEN                     # which generator to check (v0.3 by default; GEN = 'hardware/mechanical/fusion/TiltPartsV4/TiltPartsV4.py')
except NameError:
    GEN = 'hardware/mechanical/fusion/TiltParts/TiltParts.py'
mod = load_script(os.path.join(REPO, GEN))
try:
    OVERRIDES
except NameError:
    OVERRIDES = {}
mod.P.update(OVERRIDES)
P = mod.P
L = mod.layout()
plan = mod.case_plan(L)

GENERAL, HOLE = 1.2, 1.6
HOLE_KINDS = ('screw', 'peg', 'AS5600')


def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a): return math.sqrt(dot(a, a))
def unit(a): return mul(a, 1.0 / norm(a))


def sd(pr, p):
    """Signed distance to a Prim (negative inside)."""
    if pr.kind == 'cyl':
        ax = sub(pr.p2, pr.p1)
        Lx = norm(ax)
        a = mul(ax, 1 / Lx)
        v = sub(p, pr.p1)
        t = dot(v, a)
        r = pr.r + (getattr(pr, 'r2', pr.r) - pr.r) * min(max(t / Lx, 0.0), 1.0)
        dr = norm(sub(v, mul(a, t))) - r
        da = max(-t, t - Lx)
        out = math.hypot(max(dr, 0.0), max(da, 0.0))
        return out + min(max(dr, da), 0.0)
    h = cross(pr.u, pr.w)
    v = sub(p, pr.c)
    q = (abs(dot(v, pr.u)) - pr.L / 2, abs(dot(v, pr.w)) - pr.W / 2, abs(dot(v, h)) - pr.H / 2)
    out = math.sqrt(sum(max(x, 0.0) ** 2 for x in q))
    return out + min(max(q), 0.0)


def samples(pr, step=0.6):
    """(point, outward normal) pairs on the primitive's surface."""
    pts = []
    if pr.kind == 'cyl':
        ax = sub(pr.p2, pr.p1)
        Lx = norm(ax)
        a = mul(ax, 1 / Lx)
        e1 = unit(cross(a, (0, 0, 1)) if abs(a[2]) < 0.9 else cross(a, (1, 0, 0)))
        e2 = cross(a, e1)
        r2 = getattr(pr, 'r2', pr.r)
        nl = max(2, int(Lx / step) + 1)
        for i in range(nl):
            t = Lx * i / (nl - 1)
            r = pr.r + (r2 - pr.r) * t / Lx
            na = max(12, int(2 * math.pi * r / step))
            for k in range(na):
                ang = 2 * math.pi * k / na
                rad = add(mul(e1, math.cos(ang)), mul(e2, math.sin(ang)))
                pts.append((add(add(pr.p1, mul(a, t)), mul(rad, r)), rad))
        for t, n, r in ((0.0, mul(a, -1), pr.r), (Lx, a, r2)):
            for fr in (0.0, 0.35, 0.7, 0.95):
                na = max(1, int(2 * math.pi * r * fr / step))
                for k in range(na):
                    ang = 2 * math.pi * k / na
                    rad = add(mul(e1, math.cos(ang)), mul(e2, math.sin(ang)))
                    pts.append((add(add(pr.p1, mul(a, t)), mul(rad, r * fr)), n))
        return pts
    h = cross(pr.u, pr.w)
    axes = ((pr.u, pr.L, pr.w, pr.W, h, pr.H), (pr.w, pr.W, pr.u, pr.L, h, pr.H), (h, pr.H, pr.u, pr.L, pr.w, pr.W))
    for n, ln, a1, l1, a2, l2 in axes:
        n1 = max(2, min(30, int(l1 / step) + 1))
        n2 = max(2, min(30, int(l2 / step) + 1))
        for sgn in (-1, 1):
            c = add(pr.c, mul(n, sgn * ln / 2))
            for i in range(n1):
                for j in range(n2):
                    p = add(add(c, mul(a1, l1 * (i / (n1 - 1) - 0.5))), mul(a2, l2 * (j / (n2 - 1) - 0.5)))
                    pts.append((p, mul(n, sgn)))
    return pts


# ---------------------------------------------------------------- solid model as SDFs
env = plan['env']
keep_parts = [mod.notch_box(-P['notch_clear'])]
dome = plan['dome']
dome_box = mod.box_minmax(-60, 80, -P['dome_max_y'], P['dome_max_y'], 0, P['plateau_top'])


def sd_keep(p):
    d_dome = max(min(sd(d, p) for d in dome), sd(dome_box, p))
    return min(sd(keep_parts[0], p), d_dome)


def sd_outer(p, half):
    s = min(sd(e, p) for e in env)
    k = sd_keep(p)
    for t in plan['trims']:
        s = max(s, -max(sd(t, p), -k))
    s = max(s, -p[0] if half == 'Case right' else p[0])       # the half's side of the split plane
    if half == 'Case left':
        s = min(s, min(sd(g, p) for g in plan['peg_solids']))
    return s


def run(half, build_dir):
    voids = [(getattr(c, 'label', 'cavity %d' % i), c) for i, c in enumerate(plan['cav'])]
    voids += plan['holes'][half]

    def emptiness(p, skip):
        best, who = -sd_outer(p, half), 'outside / split face'
        for j, (n, v) in enumerate(voids):
            if j == skip or (skip, j) in overlap:
                continue
            d = sd(v, p)
            if d < best:
                best, who = d, n
        return best, who

    def grad(f, p, h=0.02):
        g = tuple((f(add(p, e)) - f(sub(p, e))) / (2 * h) for e in ((h, 0, 0), (0, h, 0), (0, 0, h)))
        n = norm(g)
        return mul(g, 1 / n) if n > 1e-9 else (0, 0, 0)

    # pockets that intersect each other form one chamber: the material between them near their intersection is a cusp
    # on a solid block, not a free-standing fin, so walls between overlapping pockets are not counted
    samp = [samples(v) for _, v in voids]
    overlap = set()
    for i in range(len(voids)):
        for j in range(len(voids)):
            if i != j and any(sd(voids[j][1], q) < -0.05 for q, _ in samp[i][::3]):
                overlap.add((i, j))
                overlap.add((j, i))
    findings = []
    overhangs = []
    for i, (name, v) in enumerate(voids):
        thr = HOLE if any(k in name for k in HOLE_KINDS) else GENERAL
        worst = {}
        for q, n in samp[i]:
            if sd_outer(q, half) > -0.02:
                continue                                   # not inside this half
            if any(sd(w, q) < 0.05 for j, (_, w) in enumerate(voids) if j != i):
                continue                                   # inside / on another pocket: not a real wall surface
            # overhang: pocket ceiling facing the build direction, with material above it
            if dot(n, build_dir) > 0.7:
                above = add(q, mul(build_dir, 0.4))
                if sd_outer(above, half) < 0 and all(sd(w, above) > 0 for _, w in voids):
                    overhangs.append((name, q))
            t = 0.02
            hit = None
            while t < 6.0:
                p = add(q, mul(n, t))
                e, who = emptiness(p, i)
                if e <= 0.01:
                    hit = who
                    break
                t += max(e, 0.04)
            if hit is None:
                continue
            # only walls the ray really crosses: ignore grazing hits
            if hit == 'outside / split face':
                f = lambda x: -sd_outer(x, half)
            else:
                w = next(w for nm, w in voids if nm == hit)
                f = lambda x, w=w: sd(w, x)
            if dot(n, grad(f, add(q, mul(n, t)))) > -0.3:
                continue
            if hit not in worst or t < worst[hit][0]:
                worst[hit] = (t, q)
        for hit, (t, q) in worst.items():
            if t < thr:
                findings.append(dict(feature=name, wall_mm=round(t, 2), next_to=hit, need=thr,
                                     at=[round(x, 1) for x in q]))
    # summarize overhangs per feature (approximate area from sample count)
    oh = {}
    for name, q in overhangs:
        oh.setdefault(name, []).append(q)
    oh_sum = [dict(feature=k, samples=len(v), x=round(sum(q[0] for q in v) / len(v), 1)) for k, v in oh.items()]
    return sorted(findings, key=lambda d: d['wall_mm']), oh_sum


left, left_oh = run('Case left', (1, 0, 0))       # lid prints outer face down: build direction +X
right, right_oh = run('Case right', (-1, 0, 0))   # main half prints back face down: build direction -X
result = dict(case_left_thin=left, case_right_thin=right, case_left_overhangs=left_oh, case_right_overhangs=right_oh,
              screws=plan['bosses'], pegs=plan['pegs'])
