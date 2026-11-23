"""Can the controller box be tilted into the headrail past its lips, and how far must the rail's walls spread for it?

A search over the box's cross-section (Controller.py's outline with its bevels) inside the rail's cross-section
(floor, walls, lips): position across, height and tilt angle, from seated on the floor to lifted clear of the rail.
The tilt rod is left out: it is lifted while the box goes under it. Pure Python, no Fusion.

  python3 hardware/mechanical/fusion/Controller/tilt_in.py
"""
import importlib.util
import math
import os
from collections import deque

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load('Controller')
C, FIT = M.C, M.FIT
RAIL_W, RAIL_H, LIP_IN, LIP_H = FIT.RAIL_W, FIT.RAIL_H, FIT.LIP_IN, FIT.LIP_H
YMIN, YMAX, ZMIN, ZMAX = -45.0, 45.0, -2.0, 75.0


def hull(pts):
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))
    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(p)
        return h
    lo, up = half(pts), half(reversed(pts))
    return lo[:-1] + up[:-1]          # counter-clockwise


def blocked_rows(poly, STEP, NY, NZ):
    """Convex polygon (ccw) -> {iz: (iy0, iy1)} of grid points strictly inside (shrunk by 0.02)."""
    rows = {}
    zs = [p[1] for p in poly]
    for iz in range(max(0, int(math.ceil((min(zs) - ZMIN) / STEP))), min(NZ - 1, int((max(zs) - ZMIN) / STEP)) + 1):
        z = ZMIN + iz * STEP
        lo, hi = -1e9, 1e9
        ok = True
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            # inside: cross((p1-p0),(q-p0)) >= 0  ->  a*y + b >= 0 for q = (y, z)
            ex, ey = x1 - x0, y1 - y0
            a, b = -ey, ex * (z - y0) + ey * x0
            n = math.hypot(ex, ey)
            b -= 0.02 * n
            if abs(a) < 1e-12:
                if b < 0:
                    ok = False
                    break
            elif a > 0:
                lo = max(lo, -b / a)
            else:
                hi = min(hi, -b / a)
        if ok and lo < hi:
            i0, i1 = int(math.ceil((lo - YMIN) / STEP)), int(math.floor((hi - YMIN) / STEP))
            i0, i1 = max(i0, 0), min(i1, NY - 1)
            if i0 <= i1:
                rows[iz] = (i0, i1)
    return rows


def obstacles(spread):
    h, s = RAIL_W / 2, spread / 2
    R = lambda y0, y1, z0, z1: [(y0, z0), (y1, z0), (y1, z1), (y0, z1)]
    return [R(-80, 80, -30, 0), R(-80, -h - s, -30, RAIL_H), R(h + s, 80, -30, RAIL_H),
            R(-80, -h - s + LIP_IN, RAIL_H - LIP_H, RAIL_H), R(h + s - LIP_IN, 80, RAIL_H - LIP_H, RAIL_H)]


def reachable(pieces, spread, STEP=0.25, ASTEP=1.0):
    """True if the box can get from seated on the rail floor to clear above the rail, walls spread by `spread`."""
    NY, NZ = int((YMAX - YMIN) / STEP) + 1, int((ZMAX - ZMIN) / STEP) + 1
    ANGLES = [a * ASTEP for a in range(int(-90 / ASTEP), int(90 / ASTEP) + 1)]
    obs = obstacles(spread)
    free = []
    for a in ANGLES:
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        g = [bytearray(b'\x01') * NY for _ in range(NZ)]
        for piece in pieces:
            rp = [(y * c - z * s, y * s + z * c) for y, z in piece]
            for ob in obs:
                ms = hull([(oy - py, oz - pz) for oy, oz in ob for py, pz in rp])
                for iz, (i0, i1) in blocked_rows(ms, STEP, NY, NZ).items():
                    g[iz][i0:i1 + 1] = bytes(i1 - i0 + 1)
        free.append(g)
    a0 = ANGLES.index(0.0)
    iy0 = int(round((0 - YMIN) / STEP))
    gz = next((iz for iz in range(int((0 - ZMIN) / STEP), NZ) if free[a0][iz][iy0]), None)   # seated: lowest free height
    if gz is None or gz > (1.0 - ZMIN) / STEP:
        return False
    start = (a0, gz, iy0)
    seen = {start}
    q = deque([start])
    top = int((60 - ZMIN) / STEP)
    while q:
        ia, iz, iy = q.popleft()
        if iz >= top:
            return True
        for da, dz, dy in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (ia + da, iz + dz, iy + dy)
            if 0 <= n[0] < len(ANGLES) and 0 <= n[1] < NZ and 0 <= n[2] < NY and n not in seen and free[n[0]][n[1]][n[2]]:
                seen.add(n)
                q.append(n)
    return False


def min_spread(pieces, **grid):
    """How far the rail's walls must spread (mm, total) for the box to go in; 0 = it tilts in freely."""
    lo, hi = 0.0, 12.0
    if reachable(pieces, 0.0, **grid):
        return 0.0
    while hi - lo > 0.2:
        mid = (lo + hi) / 2
        if reachable(pieces, mid, **grid):
            hi = mid
        else:
            lo = mid
    return hi


def section(bevels=True):
    """The box's outline [(y, z)], centered in the rail. bevels False = the old square box (for comparison)."""
    h, top = (C['out_hi'] - C['room_out']) / 2, C['top']
    bot, tb = (C['bevel_bot'], C['bevel_top']) if bevels else (0.9, 0.9)       # 0.9: the old 1.5 mm rounds, about
    return [hull([(-h + bot, 0), (h - bot, 0), (h, bot), (h, top - tb), (h - tb, top), (-h + tb, top), (-h, top - tb), (-h, bot)])]


if __name__ == '__main__':
    print('square box: rail walls must spread %.1f mm' % min_spread(section(False)))
    print('this box:   rail walls must spread %.1f mm' % min_spread(section(True)))
