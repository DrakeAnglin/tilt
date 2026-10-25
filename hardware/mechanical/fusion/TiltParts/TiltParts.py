"""TiltParts: printable parts for the motorized tilter, test-fit version (v0.1).

Layout (see tools/layout_spur.py): factory worm wheel on the 4 mm rod, factory worm at 75° from horizontal,
new printed ADAPTER on the worm's 8-ridge spline carrying a 14T spur gear and the teardrop wand loop,
an N20 (no encoder) parallel to the worm with its shaft pointing down, carrying a 16T spur gear.

Parts (each its own component, exported as STL):
  Adapter        14T m1.0 spur gear + 8-ridge spline socket + Ø8.13 body + teardrop loop
  Motor gear     16T m1.0 spur gear, D-bore for the N20 3 mm shaft, small hub
  Case left      lid half (X < 0)
  Case right     main half (X > 0) with the motor pod
  Spline test    three cups with socket clearances 0.10 / 0.15 / 0.20 mm (1 / 2 / 3 rim notches)
Reference bodies (not printed): rail, rod, worm wheel, worm, N20.

Global coordinates (mm): X along the rod (0 = tilter mid-plane), Y across the rail (-Y = room side),
Z up from the rail's inner floor. s = distance along the worm axis from its thread center, + toward the wand.
"""

import math
import os
import traceback

import adsk.core
import adsk.fusion

# ------------------------------------------------------------------ parameters (mm / deg)
P = dict(
    worm_angle=75.0, cd_worm=11.64, rod_z=24.0, rod=4.0,
    rail_w=55.5, rail_h=36.5, rail_wall=2.0,
    # gears
    module=1.0, z_adapter=14, z_motor=16, pressure=20.0, addendum=0.8, dedendum=1.25,
    backlash=0.15,            # total tooth thinning per gear at the pitch circle
    cd_extra=0.10,            # extra center distance for printed gears
    gear_s=22.0, phi=85.0,    # motor gear center along the worm axis, and its direction around the adapter
    motor_face=4.0, motor_hub_d=7.0, motor_hub=1.5, motor_gap=0.5,
    # adapter
    mouth_s=18.97, adapter_gear_len=5.6, body_d=8.13, body_len=15.0,
    spline_od=6.0, spline_root=5.0, spline_n=8, socket_depth=5.3, spline_clear=0.15,
    loop_center=21.0, loop_r_out=5.2, loop_r_in=2.6, loop_t=3.4,
    # N20 (no encoder)
    n20_w=12.0, n20_h=10.0, n20_gbx=9.0, n20_motor=15.0, n20_shaft_d=3.0, n20_flat=2.5,
    n20_screw_spacing=9.0,
    # case
    wall=1.6, clip_floor=0.3, clip_top=36.2, clip_side=0.3,
)

TOOTH_PTS = 10
PREFIX = 'TP '


# ------------------------------------------------------------------ vector helpers (mm)
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a): return math.sqrt(dot(a, a))
def unit(a): return mul(a, 1.0 / norm(a))


def P3(p): return adsk.core.Point3D.create(p[0] / 10.0, p[1] / 10.0, p[2] / 10.0)
def V3(v): return adsk.core.Vector3D.create(v[0], v[1], v[2])
def VI(mm): return adsk.core.ValueInput.createByReal(mm / 10.0)


# ------------------------------------------------------------------ geometry of the layout
def layout():
    a = math.radians(P['worm_angle'])
    X = (1.0, 0.0, 0.0)
    d = (0.0, -math.cos(a), -math.sin(a))
    n = (0.0, -math.sin(a), math.cos(a))
    rod_c = (0.0, 0.0, P['rod_z'])
    p0 = add(rod_c, mul(n, P['cd_worm']))
    f = math.radians(P['phi'])
    o = unit(add(mul(n, -math.cos(f)), mul(X, math.sin(f))))
    m = P['module']
    cd = m * (P['z_adapter'] + P['z_motor']) / 2.0 + P['cd_extra']
    S = lambda s: add(p0, mul(d, s))
    gear_c = S(P['gear_s'])
    pin_c = add(gear_c, mul(o, cd))
    w = unit(cross(mul(d, -1.0), o))
    return dict(X=X, d=d, n=n, o=o, w=w, rod_c=rod_c, p0=p0, S=S, cd=cd, gear_c=gear_c, pin_c=pin_c)


# ------------------------------------------------------------------ involute spur profile
def spur_profile(z, m, ha, hf, backlash):
    alpha = math.radians(P['pressure'])
    rp = z * m / 2.0
    rb = rp * math.cos(alpha)
    ra = rp + ha * m
    rf = rp - hf * m
    inv = lambda x: math.tan(x) - x
    half = math.pi / (2 * z) - (backlash / 2.0) / rp      # half tooth angle at the pitch circle
    def theta(r):                                          # flank angle from the tooth center line
        if r <= rb:
            return half + inv(alpha)
        return half + inv(alpha) - inv(math.acos(rb / r))
    r_start = max(rf, rb)
    radii = [r_start + (ra - r_start) * i / (TOOTH_PTS - 1) for i in range(TOOTH_PTS)]
    pts = []
    pitch = 2 * math.pi / z
    for k in range(z):
        c = k * pitch
        flank_r = [(r, c - theta(r)) for r in radii]                      # right flank, root -> tip
        flank_l = [(r, c + theta(r)) for r in reversed(radii)]            # left flank, tip -> root
        tooth = []
        if rf < rb:
            tooth.append((rf, c - theta(rb)))
        tooth += flank_r
        tip_a0, tip_a1 = c - theta(ra), c + theta(ra)
        tooth += [(ra, tip_a0 + (tip_a1 - tip_a0) * i / 3) for i in range(1, 3)]
        tooth += flank_l
        if rf < rb:
            tooth.append((rf, c + theta(rb)))
        # root arc to the next tooth
        a0 = tooth[-1][1]
        a1 = c + pitch - theta(rb if rf < rb else r_start)
        tooth += [(rf, a0 + (a1 - a0) * i / 3) for i in range(1, 3)]
        pts += tooth
    return [(r * math.cos(t), r * math.sin(t)) for r, t in pts]


def tip_width(z, m, ha, backlash):
    alpha = math.radians(P['pressure'])
    rp = z * m / 2.0
    rb = rp * math.cos(alpha)
    ra = rp + ha * m
    inv = lambda x: math.tan(x) - x
    half = math.pi / (2 * z) - (backlash / 2.0) / rp
    return 2 * ra * (half + inv(alpha) - inv(math.acos(rb / ra)))


def spline_socket_profile(clear):
    """Internal 8-ridge socket: arcs over the worm's ridges (r_out) and keys into its grooves (r_in)."""
    n = P['spline_n']
    r_out = P['spline_od'] / 2.0 + clear
    r_in = P['spline_root'] / 2.0 + clear
    gap_w = 2 * math.pi * (P['spline_od'] + P['spline_root']) / 4.0 / (2 * n)   # groove width at mid height
    key = max(gap_w - 2 * clear, 0.4)
    pts = []
    for k in range(n):
        c = k * 2 * math.pi / n
        ai, ao = (key / 2) / r_in, (key / 2) / r_out
        nxt = c + 2 * math.pi / n
        pts += [(r_in, c - ai), (r_in, c + ai), (r_out, c + ao)]
        pts += [(r_out, c + ao + (nxt - 2 * ao - c) * i / 4) for i in range(1, 4)]
        pts += [(r_out, nxt - ao)]
    return [(r * math.cos(t), r * math.sin(t)) for r, t in pts]


# ------------------------------------------------------------------ Fusion helpers
def new_component(root, name):
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = PREFIX + name
    return occ, occ.component


def offset_plane(comp, z_mm):
    if abs(z_mm) < 1e-9:
        return comp.xYConstructionPlane
    inp = comp.constructionPlanes.createInput()
    inp.setByOffset(comp.xYConstructionPlane, VI(z_mm))
    return comp.constructionPlanes.add(inp)


def polyline(sketch, pts2d, z=0.0):
    sketch.isComputeDeferred = True
    lines = sketch.sketchCurves.sketchLines
    first = prev = None
    for i, (x, y) in enumerate(pts2d):
        p = adsk.core.Point3D.create(x / 10.0, y / 10.0, 0)
        if prev is None:
            first = prev = p
            continue
        ln = lines.addByTwoPoints(prev, p)
        prev = ln.endSketchPoint
        if i == 1:
            first = ln.startSketchPoint
    lines.addByTwoPoints(prev, first)
    sketch.isComputeDeferred = False


def largest_profile(sketch):
    best, area = None, -1
    for i in range(sketch.profiles.count):
        pr = sketch.profiles.item(i)
        a = pr.areaProperties().area
        if a > area:
            best, area = pr, a
    return best


def extrude(comp, profile, dist_mm, op):
    return comp.features.extrudeFeatures.addSimple(profile, VI(dist_mm), op)


NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def circle_profile(comp, z_mm, r_mm):
    sk = comp.sketches.add(offset_plane(comp, z_mm))
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), r_mm / 10.0)
    return sk.profiles.item(0)


def place(occ, origin, xaxis, zaxis):
    zaxis = unit(zaxis)
    xaxis = unit(sub(xaxis, mul(zaxis, dot(xaxis, zaxis))))
    yaxis = cross(zaxis, xaxis)
    m = adsk.core.Matrix3D.create()
    m.setWithCoordinateSystem(P3(origin), V3(xaxis), V3(yaxis), V3(zaxis))
    try:
        occ.isGrounded = False
    except Exception:
        pass
    occ.transform2 = m      # note: design.snapshots.add() here resets some occurrences to the origin, so don't


# ------------------------------------------------------------------ parts
def build_adapter(root):
    occ, comp = new_component(root, 'Adapter')
    m = P['module']
    gear = spur_profile(P['z_adapter'], m, P['addendum'], P['dedendum'], P['backlash'])
    sk = comp.sketches.add(comp.xYConstructionPlane)
    polyline(sk, gear)
    extrude(comp, largest_profile(sk), P['adapter_gear_len'], NEW)
    extrude(comp, circle_profile(comp, P['adapter_gear_len'], P['body_d'] / 2),
            P['body_len'] - P['adapter_gear_len'], JOIN)
    # teardrop loop in the local XZ plane, point toward the body like the factory loop, round end outward
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.isComputeDeferred = True
    for r in (P['loop_r_out'], P['loop_r_in']):
        c = P['loop_center']
        tip = (0.0, c - r * math.sqrt(2))
        t_r = (r / math.sqrt(2), c - r / math.sqrt(2))
        t_l = (-r / math.sqrt(2), c - r / math.sqrt(2))
        bottom = (0.0, c + r)                      # far (round) end
        toS = lambda q: sk.modelToSketchSpace(adsk.core.Point3D.create(q[0] / 10.0, 0, q[1] / 10.0))
        arc = sk.sketchCurves.sketchArcs.addByThreePoints(toS(t_r), toS(bottom), toS(t_l))
        l1 = sk.sketchCurves.sketchLines.addByTwoPoints(arc.endSketchPoint, toS(tip))
        sk.sketchCurves.sketchLines.addByTwoPoints(l1.endSketchPoint, arc.startSketchPoint)
    sk.isComputeDeferred = False
    ring = None
    for i in range(sk.profiles.count):
        if sk.profiles.item(i).profileLoops.count == 2:
            ring = sk.profiles.item(i)
    inp = comp.features.extrudeFeatures.createInput(ring, JOIN)
    inp.setSymmetricExtent(VI(P['loop_t']), True)
    comp.features.extrudeFeatures.add(inp)
    # spline socket
    sk = comp.sketches.add(comp.xYConstructionPlane)
    polyline(sk, spline_socket_profile(P['spline_clear']))
    extrude(comp, largest_profile(sk), P['socket_depth'], CUT)
    comp.bRepBodies.item(0).name = 'Adapter'
    return occ, comp


def d_bore(comp, length):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    r = P['n20_shaft_d'] / 2.0 + 0.05
    fx = P['n20_flat'] - P['n20_shaft_d'] / 2.0 + 0.05
    fy = math.sqrt(r * r - fx * fx)
    pt = lambda x, y: adsk.core.Point3D.create(x / 10.0, y / 10.0, 0)
    arc = sk.sketchCurves.sketchArcs.addByThreePoints(pt(fx, fy), pt(-r, 0), pt(fx, -fy))
    sk.sketchCurves.sketchLines.addByTwoPoints(arc.startSketchPoint, arc.endSketchPoint)
    extrude(comp, sk.profiles.item(0), length, CUT)


def build_motor_gear(root):
    occ, comp = new_component(root, 'Motor gear')
    gear = spur_profile(P['z_motor'], P['module'], P['addendum'], P['dedendum'], P['backlash'])
    sk = comp.sketches.add(comp.xYConstructionPlane)
    polyline(sk, gear)
    extrude(comp, largest_profile(sk), P['motor_face'], NEW)
    extrude(comp, circle_profile(comp, P['motor_face'], P['motor_hub_d'] / 2), P['motor_hub'], JOIN)
    d_bore(comp, P['motor_face'] + P['motor_hub'])
    comp.bRepBodies.item(0).name = 'Motor gear'
    return occ, comp


def build_spline_test(root):
    occ, comp = new_component(root, 'Spline test')
    for i, c in enumerate((0.10, 0.15, 0.20)):
        x0 = i * 14.0
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(x0 / 10, 0, 0), 0.5)
        extrude(comp, sk.profiles.item(0), 7.0, NEW)
        sk = comp.sketches.add(comp.xYConstructionPlane)
        polyline(sk, [(x + x0, y) for x, y in spline_socket_profile(c)])
        cut = comp.features.extrudeFeatures.createInput(largest_profile(sk), CUT)
        cut.setDistanceExtent(False, VI(P['socket_depth']))
        cut.participantBodies = [comp.bRepBodies.item(i)]
        comp.features.extrudeFeatures.add(cut)
        # 1/2/3 notches on the far rim
        for k in range(i + 1):
            sk = comp.sketches.add(offset_plane(comp, 6.0))
            a = math.radians(90 + (k - i / 2.0) * 25)
            cx, cy = x0 + 4.6 * math.cos(a), 4.6 * math.sin(a)
            sk.sketchCurves.sketchLines.addCenterPointRectangle(
                adsk.core.Point3D.create(cx / 10, cy / 10, 0), adsk.core.Point3D.create((cx + 0.6) / 10, (cy + 0.6) / 10, 0))
            cut = comp.features.extrudeFeatures.createInput(sk.profiles.item(0), CUT)
            cut.setDistanceExtent(False, VI(1.0))
            cut.participantBodies = [comp.bRepBodies.item(i)]
            comp.features.extrudeFeatures.add(cut)
    for i, c in enumerate(('0.10', '0.15', '0.20')):
        comp.bRepBodies.item(i).name = 'Spline test %s mm' % c
    return occ, comp


# ------------------------------------------------------------------ case (TemporaryBRep primitives)
class Prim:
    """Finite cylinder along an axis, or an oriented box. Used both to build B-rep and for clearance checks."""

    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)

    def brep(self, tbm):
        if self.kind == 'cyl':
            return tbm.createCylinderOrCone(P3(self.p1), self.r / 10, P3(self.p2), self.r / 10)
        obb = adsk.core.OrientedBoundingBox3D.create(P3(self.c), V3(self.u), V3(self.w),
                                                     self.L / 10, self.W / 10, self.H / 10)
        return tbm.createBox(obb)

    def contains(self, p, grow=0.0):
        if self.kind == 'cyl':
            ax = sub(self.p2, self.p1)
            Lx = norm(ax)
            ax = mul(ax, 1 / Lx)
            v = sub(p, self.p1)
            t = dot(v, ax)
            if t < -grow or t > Lx + grow:
                return False
            return norm(sub(v, mul(ax, t))) <= self.r + grow
        v = sub(p, self.c)
        h = cross(self.u, self.w)
        return (abs(dot(v, self.u)) <= self.L / 2 + grow and abs(dot(v, self.w)) <= self.W / 2 + grow
                and abs(dot(v, h)) <= self.H / 2 + grow)


def cyl_s(L, s0, s1, r, axis_pt=None):
    base = axis_pt if axis_pt is not None else L['p0']
    return Prim('cyl', p1=add(base, mul(L['d'], s0)), p2=add(base, mul(L['d'], s1)), r=r)


def case_shapes(L):
    """Returns (envelope prims, cavity prims, motor reference box start)."""
    d, X, w, o = L['d'], L['X'], L['w'], L['o']
    wall = P['wall']
    rc = L['rod_c']
    pin_axis = sub(L['pin_c'], mul(d, P['gear_s']))          # point on the motor axis at s = 0
    ra_ad = P['module'] * (P['z_adapter'] / 2 + P['addendum'])
    ra_mo = P['module'] * (P['z_motor'] / 2 + P['addendum'])
    gs = P['gear_s']
    face_s = gs - P['motor_face'] / 2 - P['motor_hub'] - P['motor_gap']   # N20 gearbox face
    mo_len = P['n20_gbx'] + P['n20_motor']
    mo_c = add(add(pin_axis, mul(d, face_s - mo_len / 2)), (0, 0, 0))
    mouth = P['mouth_s']
    cav = [
        Prim('cyl', p1=add(rc, (-4.15, 0, 0)), p2=add(rc, (4.15, 0, 0)), r=8.3),        # wheel teeth
        Prim('cyl', p1=add(rc, (-9.5, 0, 0)), p2=add(rc, (9.5, 0, 0)), r=6.4),          # barrel bearings
        cyl_s(L, -7.3, -4.5, 2.65),                                                       # top pin
        cyl_s(L, -4.8, 4.8, 5.9),                                                         # threads
        cyl_s(L, 4.8, 6.7, 3.4),
        cyl_s(L, 6.7, 8.9, 5.1),                                                          # upper flange
        cyl_s(L, 8.9, 16.7, 2.95),                                                        # bearing shaft
        cyl_s(L, 16.7, mouth + 0.1, 5.1),                                                 # lower flange
        cyl_s(L, mouth - 0.2, mouth + P['adapter_gear_len'] + 0.3, ra_ad + 0.5),          # adapter gear
        cyl_s(L, mouth + P['adapter_gear_len'] + 0.3, mouth + 30, P['body_d'] / 2 + 0.3), # adapter body (exits)
        cyl_s(L, gs - P['motor_face'] / 2 - 0.3, gs + P['motor_face'] / 2 + 0.3, ra_mo + 0.6, pin_axis),  # motor gear
        cyl_s(L, gs + P['motor_face'] / 2, gs + P['motor_face'] / 2 + 4.0, 2.2, pin_axis),               # shaft tail
        cyl_s(L, face_s - 0.1, gs - P['motor_face'] / 2, 4.0, pin_axis),                                 # hub + boss
        Prim('box', c=add(pin_axis, mul(d, face_s - (mo_len + 6) / 2)), u=mul(d, -1), w=w,
             L=mo_len + 6, W=P['n20_w'] + 0.3, H=P['n20_h'] + 0.3),                                    # N20, open rear
    ]
    for sgn in (-1, 1):                                                                   # N20 gearbox screws
        hp = add(pin_axis, mul(w, sgn * P['n20_screw_spacing'] / 2))
        cav.append(cyl_s(L, face_s - 1.0, gs - P['motor_face'] / 2 + 0.5, 0.9, hp))
    env = [
        Prim('cyl', p1=add(rc, (-8.33, 0, 0)), p2=add(rc, (8.33, 0, 0)), r=8.3 + wall),
        cyl_s(L, -7.3 - wall, mouth, 5.9 + wall),
        cyl_s(L, mouth - 0.2, mouth + P['adapter_gear_len'] + 0.3 + wall, ra_ad + 0.5 + wall),
        cyl_s(L, face_s - 0.1, gs + P['motor_face'] / 2 + 4.0 + wall, ra_mo + 0.6 + wall, pin_axis),
        Prim('box', c=add(pin_axis, mul(d, face_s - (mo_len - 1) / 2)), u=mul(d, -1), w=w,
             L=mo_len - 1, W=P['n20_w'] + 0.3 + 2 * wall, H=P['n20_h'] + 0.3 + 2 * wall),
    ]
    return env, cav, dict(pin_axis=pin_axis, face_s=face_s, mo_len=mo_len)


def pick_bosses(env, cav, count=3):
    """Screw bosses along X (Ø6, M2 pilot) in the tilter slab, clear of every cavity, touching the envelope."""
    cands = []
    for yi in range(-25, 26):
        for zi in range(2, 36):
            y, z = float(yi), float(zi)
            ok = True
            near_env = False
            for xi in range(-4, 5):
                x = xi * 2.0
                for k in range(6):
                    a = k * math.pi / 3
                    q = (x, y + 1.9 * math.cos(a), z + 1.9 * math.sin(a))
                    if any(c.contains(q) for c in cav):
                        ok = False
                        break
                if not ok:
                    break
                if any(e.contains((x, y, z), grow=1.0) for e in env):
                    near_env = True
            if ok and near_env and abs(y) < 25.5 and 1.0 < z < 35.0:
                cands.append((y, z))
    chosen = []
    while cands and len(chosen) < count:
        if not chosen:
            pick = max(cands, key=lambda c: c[1])
        else:
            pick = max(cands, key=lambda c: min(math.hypot(c[0] - q[0], c[1] - q[1]) for q in chosen))
        chosen.append(pick)
    return chosen


def build_case(root, design, L):
    tbm = adsk.fusion.TemporaryBRepManager.get()
    env, cav, info = case_shapes(L)
    bosses = pick_bosses(env, cav)
    body = None
    for e in env + [Prim('cyl', p1=(-8.33, y, z), p2=(8.33, y, z), r=3.0) for y, z in bosses]:
        b = e.brep(tbm)
        if body is None:
            body = b
        else:
            tbm.booleanOperation(body, b, adsk.fusion.BooleanTypes.UnionBooleanType)
    for c in cav:
        tbm.booleanOperation(body, c.brep(tbm), adsk.fusion.BooleanTypes.DifferenceBooleanType)
    # keep the case inside the rail: anything below the floor or past a wall is trimmed (the rail closes those sides)
    rail_in = tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
        P3((20, 0, (P['clip_floor'] + P['clip_top']) / 2)), V3((1, 0, 0)), V3((0, 1, 0)),
        20.0, (P['rail_w'] - 2 * P['clip_side']) / 10, (P['clip_top'] - P['clip_floor']) / 10))
    tbm.booleanOperation(body, rail_in, adsk.fusion.BooleanTypes.IntersectionBooleanType)
    halves = {}
    for name, xc in (('Case left', -50.0), ('Case right', 50.0)):
        half = tbm.copy(body)
        cutter = tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
            P3((xc, 0, 18)), V3((1, 0, 0)), V3((0, 1, 0)), 10.0, 20.0, 20.0))
        tbm.booleanOperation(half, cutter, adsk.fusion.BooleanTypes.IntersectionBooleanType)
        for y, z in bosses:
            r = 1.1 if name == 'Case left' else 0.85        # clearance in the lid, pilot in the main half
            tbm.booleanOperation(half, Prim('cyl', p1=(-9, y, z), p2=(9, y, z), r=r).brep(tbm),
                                 adsk.fusion.BooleanTypes.DifferenceBooleanType)
        halves[name] = half
    out = {}
    for name, half in halves.items():
        occ, comp = new_component(root, name)
        add_bodies(comp, [(name, half)])
        out[name] = (occ, comp)
    return out, bosses, info


def build_refs(root, design, L, info):
    tbm = adsk.fusion.TemporaryBRepManager.get()
    occ, comp = new_component(root, 'REF (not printed)')
    rc = L['rod_c']
    items = [
        ('Worm wheel', Prim('cyl', p1=add(rc, (-3.75, 0, 0)), p2=add(rc, (3.75, 0, 0)), r=7.9)),
        ('Barrel', Prim('cyl', p1=add(rc, (-8.33, 0, 0)), p2=add(rc, (8.33, 0, 0)), r=6.25)),
        ('Rod', Prim('box', c=add(rc, (20, 0, 0)), u=(1, 0, 0), w=(0, 1, 0), L=80, W=4, H=4)),
    ]
    worm = [(-7, -4.5, 2.5), (-4.5, 4.5, 5.5), (4.5, 7, 2.8), (7, 8.6, 4.75), (8.6, 17, 2.8),
            (17, 18.77, 4.75), (18.77, 23.77, 3.0)]
    for i, (s0, s1, r) in enumerate(worm):
        items.append(('Worm %d' % i, cyl_s(L, s0, s1, r)))
    mo = info['mo_len']
    items.append(('N20', Prim('box', c=add(info['pin_axis'], mul(L['d'], info['face_s'] - mo / 2)),
                              u=mul(L['d'], -1), w=L['w'], L=mo, W=P['n20_w'], H=P['n20_h'])))
    items.append(('N20 shaft', cyl_s(L, info['face_s'], P['gear_s'] + P['motor_face'] / 2 + 2.5,
                                     P['n20_shaft_d'] / 2, info['pin_axis'])))
    w2, h = P['rail_w'] / 2, P['rail_h']
    t = P['rail_wall']
    for nm, c, W, H in (('Rail floor', (20, 0, -t / 2), P['rail_w'] + 2 * t, t),
                        ('Rail wall room', (20, -w2 - t / 2, h / 2), t, h),
                        ('Rail wall back', (20, w2 + t / 2, h / 2), t, h)):
        items.append((nm, Prim('box', c=c, u=(1, 0, 0), w=(0, 1, 0), L=80, W=W, H=H)))
    for b in add_bodies(comp, [(nm, pr.brep(tbm)) for nm, pr in items]):
        if b.name.startswith('Rail'):
            b.opacity = 0.2
    return occ, comp


def color(design, comp, name):
    app = adsk.core.Application.get()
    lib = None
    for i in range(app.materialLibraries.count):
        if app.materialLibraries.item(i).name == 'Fusion Appearance Library':
            lib = app.materialLibraries.item(i)
    if lib is None:
        return
    a = design.appearances.itemByName(name) or design.appearances.addByCopy(lib.appearances.itemByName(name), name)
    for i in range(comp.bRepBodies.count):
        comp.bRepBodies.item(i).appearance = a


def add_bodies(comp, named_bodies):
    """Add TemporaryBRep bodies: through a base feature in parametric designs, directly in direct designs."""
    parametric = comp.parentDesign.designType == adsk.fusion.DesignTypes.ParametricDesignType
    bf = None
    if parametric:
        bf = comp.features.baseFeatures.add()
        bf.startEdit()
    out = []
    for nm, body in named_bodies:
        b = comp.bRepBodies.add(body, bf) if bf else comp.bRepBodies.add(body)
        b.name = nm
        out.append(b)
    if bf:
        bf.finishEdit()
    return out


def remove_old(design):
    occs = design.rootComponent.occurrences
    for i in range(occs.count - 1, -1, -1):
        if occs.item(i).component.name.startswith(PREFIX):
            occs.item(i).deleteMe()


def build(design, export_dir=None):
    root = design.rootComponent
    L = layout()
    adapter_occ, adapter = build_adapter(root)
    mgear_occ, mgear = build_motor_gear(root)
    test_occ, test = build_spline_test(root)
    cases, bosses, info = build_case(root, design, L)
    refs_occ, refs = build_refs(root, design, L, info)

    # place the printed gears in the assembly (looked up by name: earlier proxies can go stale)
    def occ_named(name):
        for i in range(root.occurrences.count):
            if root.occurrences.item(i).component.name == PREFIX + name:
                return root.occurrences.item(i)
    mg_origin = add(L['pin_c'], mul(L['d'], P['motor_face'] / 2))          # gear's low face (shaft tip side)
    place(occ_named('Spline test'), (0, 60, 0), (1, 0, 0), (0, 0, 1))
    place(occ_named('Motor gear'), mg_origin, L['X'], mul(L['d'], -1))
    place(occ_named('Adapter'), L['S'](P['mouth_s']), L['X'], L['d'])

    color(design, adapter, 'Plastic - Glossy (Yellow)')
    color(design, mgear, 'Plastic - Glossy (Yellow)')
    color(design, test, 'Plastic - Glossy (Green)')
    color(design, cases['Case left'][1], 'Plastic - Translucent Matte (Blue)')
    color(design, cases['Case right'][1], 'Plastic - Matte (Blue)')
    color(design, refs, 'Plastic - Matte (White)')

    files = []
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        em = design.exportManager
        for nm, comp in (('adapter', adapter), ('motor_gear', mgear), ('spline_test', test),
                         ('case_left', cases['Case left'][1]), ('case_right', cases['Case right'][1])):
            path = os.path.join(export_dir, nm + '.stl')
            opt = em.createSTLExportOptions(comp, path)
            opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
            em.execute(opt)
            files.append(path)

    m = P['module']
    rep = [
        'Adapter gear: %dT m%.1f, tip width %.2f mm' % (P['z_adapter'], m, tip_width(P['z_adapter'], m, P['addendum'], P['backlash'])),
        'Motor gear:   %dT m%.1f, tip width %.2f mm' % (P['z_motor'], m, tip_width(P['z_motor'], m, P['addendum'], P['backlash'])),
        'Gear center distance: %.2f mm (ratio %d:%d)' % (L['cd'], P['z_motor'], P['z_adapter']),
        'Screw bosses (Y, Z): %s' % ', '.join('(%.1f, %.1f)' % b for b in bosses),
        'Exported: %s' % ', '.join(os.path.basename(f) for f in files),
    ]
    return '\n'.join(rep)


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        remove_old(design)
        ui.messageBox(build(design))
    except Exception:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
