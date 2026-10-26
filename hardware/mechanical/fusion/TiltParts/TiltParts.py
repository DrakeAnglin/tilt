"""TiltParts: printable parts for the motorized tilter, version v0.3 (crossed helical).

Layout: factory worm wheel on the 4 mm square rod, factory worm at 60° (factory 56°), so the wand still exits
through the headrail's existing corner notch; a small dome on the case covers the worm's top end where it rises into
the rail's open top slot. A new printed ADAPTER slides on the worm's 8-ridge spline. It carries
an 8T 45° helical gear and the teardrop wand loop. An N20 (no encoder) lies roughly along the rod and drives the
adapter through a 7T 45° helical pinion. The 90° crossed helicals are 1:1-ish and NOT self-locking, so the wand
still back-drives the motor. The 16:1 factory worm does the locking.

Parts (each its own component, exported to STL in its own print orientation):
  Adapter        8T helical (mn 1.0, 45° RH) + 8-ridge spline socket + Ø8.13 body + teardrop loop
  Motor pinion   7T helical (mn 1.0, 45° RH), D-bore for the N20 3 mm shaft, small hub
  Case left      lid half (X < 0)
  Case right     main half (X > 0) with the motor pod and the notch block
  Sensor module  separate press-fit block anywhere along the rod (the rod passes straight through):
                 sensor_case_left (with the AS5600 board frame), sensor_case_right, rod_gear (24T, square bore),
                 sensor_gear (12T with its shaft and the magnet pocket)
Reference bodies (not printed): rail with its corner notch, rod, worm wheel, worm, N20.

Global coordinates (mm): X along the rod (0 = tilter mid-plane, +X toward the tilt drums), Y across the rail
(-Y = room side), Z up from the rail's inner floor. s = distance along the worm axis from its thread center,
positive toward the wand.
"""

import math
import os
import traceback

import adsk.core
import adsk.fusion

# ------------------------------------------------------------------ parameters (mm / deg)
P = dict(
    worm_angle=60.0, cd_worm=11.64, rod_z=24.0, rod=4.0,
    rail_w=55.5, rail_h=36.5, rail_wall=2.0, lip_in=4.5, lip_h=3.0,
    # corner notch in the rail (measured from the outside): 12 tall, 10.5 into the floor, 12 wide along the rod
    notch_h=12.0, notch_d=10.5, notch_w=12.0, notch_clear=0.15,
    # crossed helical pair
    mn=1.0, helix=45.0, pressure=20.0, addendum=0.85, dedendum=1.25, backlash=0.15, cd_extra=0.10,
    z_adapter=8, z_pinion=7,
    adapter_face=2.6, pinion_face=6.0, pinion_hub_d=6.5, pinion_hub=1.5,
    pinion_gap=3.0,           # pinion face to N20 gearbox face
    motor_rot=0.0,            # motor axis swung about the worm axis (0 = parallel to the rod)
    # adapter
    mouth_s=18.97, collar_d=8.2, body_d=6.0, body_len=19.0,
    spline_od=6.0, spline_root=5.0, spline_n=8, socket_depth=5.3, spline_clear=0.10,   # owner's fit test: 0.10 fits best
    loop_center=25.0, loop_r_out=5.4, loop_r_in=2.7, loop_t=4.0, loop_round=1.0,
    # N20 (no encoder)
    n20_w=12.0, n20_h=10.0, n20_gbx=9.0, n20_motor=15.0, n20_end=1.0, n20_shaft_d=3.0, n20_flat=2.5,
    n20_screw_spacing=9.0,
    # case
    wall=1.6, slab_half=8.33, case_w=55.4, case_floor=0.2, case_top=36.3, edge_round=1.0,
    dome_wall=1.2, dome_max_y=21.0,   # cover over the worm's top end, allowed to rise into the rail's open top slot
    screw_cbore_d=3.4, screw_cbore=1.2, peg_d=2.5, peg_h=2.0, lid_cbore_d=4.2, lid_cbore=1.8,
    # AS5600 sensor module: its own press-fit block anywhere on the rod. A 24T gear on the square rod drives a 14T
    # sensor gear (60° of rod = 103° at the magnet); the magnet sits in the sensor shaft's head, facing the board.
    sm_x=55.0, sm_half=7.0, sm_m=0.8, sm_z_rod=24, sm_z_sensor=14, sm_face=4.0, sm_cd_extra=0.1,
    sm_sensor_y=15.2, sm_rod_hub_d=8.0, sm_shaft_d=4.0, sm_head_d=8.0, sm_head_len=3.4, sm_rod_clear=3.4,
    magnet_d=6.0, magnet_t=2.5, magnet_clear=0.15, sensor_gap=1.5, board_w=23.4, board_t=1.8, frame_wall=1.6,
)

TOOTH_PTS = 10
LOFT_SECTIONS = 7
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


# ------------------------------------------------------------------ helical gear math
def helical(z):
    b = math.radians(P['helix'])
    mt = P['mn'] / math.cos(b)
    at = math.atan(math.tan(math.radians(P['pressure'])) / math.cos(b))
    rp = z * mt / 2.0
    return dict(z=z, mt=mt, at=at, rp=rp, rb=rp * math.cos(at),
                ra=rp + P['addendum'] * P['mn'], rf=rp - P['dedendum'] * P['mn'], beta=b)


def gear_profile(g):
    """Transverse involute outline (closed polyline, mm) of a helical gear's cross-section."""
    z, rp, rb, ra, rf, at = g['z'], g['rp'], g['rb'], g['ra'], g['rf'], g['at']
    inv = lambda x: math.tan(x) - x
    half = math.pi / (2 * z) - (P['backlash'] / 2.0) / rp
    def theta(r):
        return half + inv(at) - (inv(math.acos(rb / r)) if r > rb else 0.0)
    r0 = max(rf, rb)
    radii = [r0 + (ra - r0) * i / (TOOTH_PTS - 1) for i in range(TOOTH_PTS)]
    pitch = 2 * math.pi / z
    pts = []
    for k in range(z):
        c = k * pitch
        tooth = []
        if rf < rb:
            tooth.append((rf, c - theta(rb)))
        tooth += [(r, c - theta(r)) for r in radii]
        a0, a1 = c - theta(ra), c + theta(ra)
        tooth += [(ra, a0 + (a1 - a0) * i / 3) for i in (1, 2)]
        tooth += [(r, c + theta(r)) for r in reversed(radii)]
        if rf < rb:
            tooth.append((rf, c + theta(rb)))
        b0 = tooth[-1][1]
        b1 = c + pitch - theta(rb if rf < rb else r0)
        tooth += [(rf, b0 + (b1 - b0) * i / 3) for i in (1, 2)]
        pts += tooth
    return [(r * math.cos(t), r * math.sin(t)) for r, t in pts]


def tip_width_normal(g):
    inv = lambda x: math.tan(x) - x
    half = math.pi / (2 * g['z']) - (P['backlash'] / 2.0) / g['rp']
    t = half + inv(g['at']) - inv(math.acos(g['rb'] / g['ra']))
    return 2 * g['ra'] * t * math.cos(g['beta'])


def spline_socket_profile(clear):
    n = P['spline_n']
    r_out = P['spline_od'] / 2.0 + clear
    r_in = P['spline_root'] / 2.0 + clear
    gap_w = 2 * math.pi * (P['spline_od'] + P['spline_root']) / 4.0 / (2 * n)
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


# ------------------------------------------------------------------ layout
def layout():
    a = math.radians(P['worm_angle'])
    X = (1.0, 0.0, 0.0)
    d = (0.0, -math.cos(a), -math.sin(a))          # worm axis, toward the wand
    n = (0.0, -math.sin(a), math.cos(a))           # rod axis -> worm axis
    rod_c = (0.0, 0.0, P['rod_z'])
    p0 = add(rod_c, mul(n, P['cd_worm']))
    S = lambda s: add(p0, mul(d, s))
    ga, gp = helical(P['z_adapter']), helical(P['z_pinion'])
    cd = ga['rp'] + gp['rp'] + P['cd_extra']
    rot = math.radians(P['motor_rot'])
    u = unit(add(mul(X, math.cos(rot)), mul(n, math.sin(rot))))      # pinion / motor axis (toward the motor)
    off = unit(mul(cross(d, u), -1.0))                                 # common perpendicular, away from the wall
    gs = P['mouth_s'] + P['adapter_face'] / 2.0
    gear_c = S(gs)
    pin_c = add(gear_c, mul(off, cd))
    vz = unit(sub((0, 0, 1), mul(u, dot((0, 0, 1), u))))
    w = cross(u, vz)
    face = add(pin_c, mul(u, P['pinion_face'] / 2 + P['pinion_gap']))  # N20 gearbox face
    return dict(X=X, d=d, n=n, u=u, w=w, vz=vz, off=off, rod_c=rod_c, p0=p0, S=S, cd=cd, gs=gs,
                gear_c=gear_c, pin_c=pin_c, face=face, ga=ga, gp=gp)


# ------------------------------------------------------------------ Fusion helpers
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


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


def polyline(sketch, pts2d):
    sketch.isComputeDeferred = True
    lines = sketch.sketchCurves.sketchLines
    first = prev = None
    for i, (x, y) in enumerate(pts2d):
        p = adsk.core.Point3D.create(x / 10.0, y / 10.0, 0)
        if prev is None:
            prev = p
            continue
        ln = lines.addByTwoPoints(prev, p)
        if i == 1:
            first = ln.startSketchPoint
        prev = ln.endSketchPoint
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


def own_bodies(comp):
    return [comp.bRepBodies.item(i) for i in range(comp.bRepBodies.count)]


def extrude(comp, profile, dist_mm, op):
    """Extrude; joins/cuts touch ONLY this component's bodies. (Every part is built at the origin before it is
    placed, and Fusion's default would otherwise cut or join whatever other part happens to overlap there.)"""
    inp = comp.features.extrudeFeatures.createInput(profile, op)
    inp.setDistanceExtent(False, VI(dist_mm))
    if op != NEW:
        inp.participantBodies = own_bodies(comp)
    return comp.features.extrudeFeatures.add(inp)


def circle_profile(comp, z_mm, r_mm):
    sk = comp.sketches.add(offset_plane(comp, z_mm))
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), r_mm / 10.0)
    return sk.profiles.item(0)


def helical_body(comp, g, face, hand=1.0):
    """Loft the transverse profile through sections rotated along the helix (right hand = +1)."""
    base = gear_profile(g)
    loft = comp.features.loftFeatures.createInput(NEW)
    for k in range(LOFT_SECTIONS):
        zk = face * k / (LOFT_SECTIONS - 1)
        th = hand * zk * math.tan(g['beta']) / g['rp']
        c, s = math.cos(th), math.sin(th)
        sk = comp.sketches.add(offset_plane(comp, zk))
        polyline(sk, [(x * c - y * s, x * s + y * c) for x, y in base])
        loft.loftSections.add(largest_profile(sk))
    loft.isSolid = True
    return comp.features.loftFeatures.add(loft)


def merge_bodies(comp):
    """Join every body in the component into the first one (some feature joins leave separate lumps)."""
    if comp.bRepBodies.count < 2:
        return
    tools = adsk.core.ObjectCollection.create()
    for i in range(1, comp.bRepBodies.count):
        tools.add(comp.bRepBodies.item(i))
    inp = comp.features.combineFeatures.createInput(comp.bRepBodies.item(0), tools)
    inp.operation = JOIN
    comp.features.combineFeatures.add(inp)


def round_region(comp, z_min, radii):
    """Fillet every edge of the component's body lying above z_min (local mm): loop faces, hole edges and the
    shaft-to-loop junction. Tries each radius in turn and keeps the first that Fusion accepts."""
    body = comp.bRepBodies.item(0)
    for r in radii:
        edges = adsk.core.ObjectCollection.create()
        for e in body.edges:
            if e.boundingBox.minPoint.z * 10 >= z_min:
                edges.add(e)
        if edges.count == 0:
            return None
        try:
            inp = comp.features.filletFeatures.createInput()
            inp.addConstantRadiusEdgeSet(edges, VI(r), True)
            comp.features.filletFeatures.add(inp)
            return r
        except Exception:
            continue
    return None


def place(occ, origin, xaxis, zaxis):
    zaxis = unit(zaxis)
    xaxis = unit(sub(xaxis, mul(zaxis, dot(xaxis, zaxis))))
    yaxis = cross(zaxis, xaxis)
    m = adsk.core.Matrix3D.create()
    m.setWithCoordinateSystem(P3(origin), V3(xaxis), V3(yaxis), V3(zaxis))
    occ.transform2 = m       # direct design: positions are permanent (snapshots reset occurrences)


def add_bodies(comp, named_bodies):
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


# ------------------------------------------------------------------ printed parts
def build_adapter(root, L):
    occ, comp = new_component(root, 'Adapter')
    helical_body(comp, L['ga'], P['adapter_face'])
    # collar (solid wall round the spline socket) -> 45° taper -> slim body, as ONE revolved profile
    collar_end = P['socket_depth'] + 0.5
    cone_end = collar_end + (P['collar_d'] - P['body_d']) / 2
    z0 = P['adapter_face'] - 0.3                               # overlaps the gear so the bodies fuse
    rc, rb = P['collar_d'] / 2, P['body_d'] / 2
    sk = comp.sketches.add(comp.xZConstructionPlane)
    toS = lambda r, z: sk.modelToSketchSpace(adsk.core.Point3D.create(r / 10.0, 0, z / 10.0))
    pts = [toS(0, z0), toS(rc, z0), toS(rc, collar_end), toS(rb, cone_end), toS(rb, P['body_len']), toS(0, P['body_len'])]
    lines = sk.sketchCurves.sketchLines
    prev = lines.addByTwoPoints(pts[0], pts[1])
    first = prev.startSketchPoint
    for q in pts[2:]:
        prev = lines.addByTwoPoints(prev.endSketchPoint, q)
    axis_line = lines.addByTwoPoints(prev.endSketchPoint, first)
    rev = comp.features.revolveFeatures.createInput(sk.profiles.item(0), axis_line, JOIN)
    rev.setAngleExtent(False, adsk.core.ValueInput.createByString('360 deg'))
    rev.participantBodies = own_bodies(comp)
    comp.features.revolveFeatures.add(rev)
    # dome on the shaft end (a sphere fused on): it runs into the loop instead of leaving a flat shoulder
    tbm = adsk.fusion.TemporaryBRepManager.get()
    add_bodies(comp, [('dome', tbm.createSphere(P3((0, 0, P['body_len'])), rb / 10.0))])
    merge_bodies(comp)
    # wand loop (local XZ plane): fully round, no points; the shaft's dome runs into it
    sk = comp.sketches.add(comp.xZConstructionPlane)
    c = P['loop_center']
    for r in (P['loop_r_out'], P['loop_r_in']):
        sk.sketchCurves.sketchCircles.addByCenterRadius(
            sk.modelToSketchSpace(adsk.core.Point3D.create(0, 0, c / 10.0)), r / 10.0)
    ring = next(sk.profiles.item(i) for i in range(sk.profiles.count) if sk.profiles.item(i).profileLoops.count == 2)
    inp = comp.features.extrudeFeatures.createInput(ring, JOIN)
    inp.setSymmetricExtent(VI(P['loop_t']), True)
    inp.participantBodies = own_bodies(comp)
    comp.features.extrudeFeatures.add(inp)
    merge_bodies(comp)
    round_region(comp, z_min=P['body_len'] - 1.0, radii=(P['loop_round'], 0.8, 0.6))
    sk = comp.sketches.add(comp.xYConstructionPlane)
    polyline(sk, spline_socket_profile(P['spline_clear']))
    extrude(comp, largest_profile(sk), P['socket_depth'], CUT)
    merge_bodies(comp)
    comp.bRepBodies.item(0).name = 'Adapter'
    return occ, comp


def build_pinion(root, L):
    occ, comp = new_component(root, 'Motor pinion')
    helical_body(comp, L['gp'], P['pinion_face'])
    extrude(comp, circle_profile(comp, P['pinion_face'], P['pinion_hub_d'] / 2), P['pinion_hub'], JOIN)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    r = P['n20_shaft_d'] / 2.0 + 0.05
    fx = P['n20_flat'] - P['n20_shaft_d'] / 2.0 + 0.05
    fy = math.sqrt(r * r - fx * fx)
    pt = lambda x, y: adsk.core.Point3D.create(x / 10.0, y / 10.0, 0)
    arc = sk.sketchCurves.sketchArcs.addByThreePoints(pt(fx, fy), pt(-r, 0), pt(fx, -fy))
    sk.sketchCurves.sketchLines.addByTwoPoints(arc.startSketchPoint, arc.endSketchPoint)
    extrude(comp, sk.profiles.item(0), P['pinion_face'] + P['pinion_hub'], CUT)
    comp.bRepBodies.item(0).name = 'Motor pinion'
    return occ, comp


# ------------------------------------------------------------------ case
class Prim:
    """Finite cylinder or oriented box: builds a TemporaryBRep body and answers point-containment queries."""

    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)

    def brep(self, tbm):
        if self.kind == 'cyl':
            r2 = getattr(self, 'r2', self.r)
            return tbm.createCylinderOrCone(P3(self.p1), self.r / 10, P3(self.p2), r2 / 10)
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
            rr = self.r + (getattr(self, 'r2', self.r) - self.r) * min(max(t / Lx, 0.0), 1.0)
            return -grow <= t <= Lx + grow and norm(sub(v, mul(ax, t))) <= rr + grow
        v = sub(p, self.c)
        h = cross(self.u, self.w)
        return (abs(dot(v, self.u)) <= self.L / 2 + grow and abs(dot(v, self.w)) <= self.W / 2 + grow
                and abs(dot(v, h)) <= self.H / 2 + grow)


def box(c, L, W, H, u=(1, 0, 0), w=(0, 1, 0)):
    return Prim('box', c=c, u=u, w=w, L=L, W=W, H=H)


def box_minmax(x0, x1, y0, y1, z0, z1):
    return box(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), x1 - x0, y1 - y0, z1 - z0)


def cyl_s(L, s0, s1, r):
    return Prim('cyl', p1=L['S'](s0), p2=L['S'](s1), r=r)


def cyl_u(L, c, t0, t1, r):
    return Prim('cyl', p1=add(c, mul(L['u'], t0)), p2=add(c, mul(L['u'], t1)), r=r)


def notch_box(grow=0.0):
    hw = P['rail_w'] / 2 + P['rail_wall']           # outer face of the room-side wall
    t = P['rail_wall']
    return box_minmax(-P['notch_w'] / 2 - grow, P['notch_w'] / 2 + grow,
                      -hw - grow, -hw + P['notch_d'] + grow, -t - grow, -t + P['notch_h'] + grow)


def case_shapes(L):
    wall = P['wall']
    rc, u, w, vz = L['rod_c'], L['u'], L['w'], L['vz']
    ga, gp = L['ga'], L['gp']
    mouth = P['mouth_s']
    mo_len = P['n20_gbx'] + P['n20_motor'] + P['n20_end']
    mo_c = add(L['face'], mul(u, (mo_len + 6) / 2))
    hw = P['case_w'] / 2
    cav = [
        Prim('cyl', p1=add(rc, (-4.15, 0, 0)), p2=add(rc, (4.15, 0, 0)), r=8.3),       # wheel teeth
        Prim('cyl', p1=add(rc, (-9.5, 0, 0)), p2=add(rc, (9.5, 0, 0)), r=6.4),         # barrel bearings
        cyl_s(L, -7.3, -4.5, 2.65),                                                      # top pin
        cyl_s(L, -4.8, 4.8, 5.9),                                                        # threads
        cyl_s(L, 4.8, 6.7, 3.4),
        cyl_s(L, 6.7, 8.9, 5.1),                                                         # upper flange
        cyl_s(L, 8.9, 16.7, 2.95),                                                       # bearing shaft
        cyl_s(L, 16.7, mouth + 0.1, 5.1),                                                # lower flange
        cyl_s(L, mouth - 0.2, mouth + P['adapter_face'] + 0.3, ga['ra'] + 0.5),          # adapter gear
        cyl_s(L, mouth + P['adapter_face'],
              mouth + P['socket_depth'] + 0.5 + (P['collar_d'] - P['body_d']) / 2 + 0.3, P['collar_d'] / 2 + 0.3),  # collar + taper
        cyl_s(L, mouth + P['socket_depth'] + 0.5, mouth + 40, P['body_d'] / 2 + 0.3),   # adapter body, exits
        cyl_u(L, L['pin_c'], -P['pinion_face'] / 2 - 0.3, P['pinion_face'] / 2 + 0.3, gp['ra'] + 0.6),   # pinion
        cyl_u(L, L['pin_c'], -P['pinion_face'] / 2 - 2.5, 0, 2.0),                       # shaft tip
        cyl_u(L, L['pin_c'], 0, P['pinion_face'] / 2 + P['pinion_gap'] + 0.1, 4.0),      # hub + gearbox boss
        Prim('box', c=mo_c, u=u, w=w, L=mo_len + 6, W=P['n20_w'] + 0.3, H=P['n20_h'] + 0.3),        # N20, open end
        box_minmax(-P['slab_half'] + 2, P['slab_half'] - 2, 11.0, hw - 2, 3.0, 31.0),    # lightening pocket
    ]
    pocket_end = P['pinion_face'] / 2 + 0.3                                            # pinion pocket face (from pin_c)
    for sgn in (-1, 1):                                                                  # gearbox screws M1.6 x 4
        hp = add(L['pin_c'], mul(w, sgn * P['n20_screw_spacing'] / 2))
        cav.append(cyl_u(L, hp, pocket_end - 0.5, P['pinion_face'] / 2 + P['pinion_gap'] + 0.5, 0.9))
        cav.append(cyl_u(L, hp, pocket_end - 0.5, pocket_end + P['screw_cbore'], P['screw_cbore_d'] / 2))
    slab = box_minmax(-P['slab_half'], P['slab_half'], -hw, hw, P['case_floor'], P['case_top'])
    dw = P['dome_wall']
    dome = [cyl_s(L, -4.8 - dw, 4.8, 5.9 + dw),                                        # over the threads
            cyl_s(L, -7.3, -4.8 - dw + 0.01, 2.65 + dw),                               # over the top pin
            Prim('cyl', p1=L['S'](-7.3), p2=L['S'](-7.3 - dw), r=2.65 + dw, r2=2.0)]   # tapered end cap
    env = [
        slab,
        *dome,
        notch_box(-P['notch_clear']),
        Prim('box', c=add(L['face'], mul(u, (mo_len - 1) / 2)), u=u, w=w,
             L=mo_len - 1, W=P['n20_w'] + 0.3 + 2 * wall, H=P['n20_h'] + 0.3 + 2 * wall),
        cyl_u(L, L['pin_c'], -P['pinion_face'] / 2 - 2.5 - wall, P['pinion_face'] / 2 + P['pinion_gap'],
              gp['ra'] + 0.6 + wall),
    ]
    # trims: stay under the rail's top lips, above the floor and inside the walls (except the notch block)
    trims = [
        box_minmax(-60, 80, -hw - 5, -hw + P['lip_in'], P['case_top'] - P['lip_h'], 60),
        box_minmax(-60, 80, hw - P['lip_in'], hw + 5, P['case_top'] - P['lip_h'], 60),
        box_minmax(-60, 80, -60, 60, P['case_top'], 80),
        box_minmax(-60, 80, -60, 60, -20, P['case_floor']),          # below the floor
        box_minmax(-60, 80, -60, -hw, -20, 80),                       # past the room-side wall
        box_minmax(-60, 80, hw, 60, -20, 80),                         # past the back wall
    ]
    return env, cav, trims, mo_len, dome


def pick_bosses(cav, keep_in, count=3):
    """M2 screw positions along X through the slab: clear of every cavity, inside the slab cross-section."""
    cands = []
    for yi in range(-25, 26):
        for zi in range(2, 35):
            y, z = float(yi), float(zi)
            if not keep_in(y, z):
                continue
            ok = True
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
            if ok:
                cands.append((y, z))
    chosen = []
    while cands and len(chosen) < count:
        pick = max(cands, key=lambda c: c[1]) if not chosen else \
            max(cands, key=lambda c: min(math.hypot(c[0] - q[0], c[1] - q[1]) for q in chosen))
        chosen.append(pick)
    return chosen


def round_outer_edges(comp, r):
    """Round the straight edges that run along X on the case's outer outline (rail corners, top, motor pod).
    Best effort: if Fusion can't fillet a set, the edges stay sharp."""
    body = comp.bRepBodies.item(0)
    bb = body.boundingBox
    ymin, ymax, zmin, zmax = bb.minPoint.y, bb.maxPoint.y, bb.minPoint.z, bb.maxPoint.z
    tol = 0.02
    picked = adsk.core.ObjectCollection.create()
    for e in body.edges:
        g = e.geometry
        if not isinstance(g, adsk.core.Line3D) or e.length < 0.5:
            continue
        a, b = e.startVertex.geometry, e.endVertex.geometry
        if abs(a.y - b.y) > 1e-4 or abs(a.z - b.z) > 1e-4:
            continue                                   # not parallel to X
        on_side = abs(a.y - ymin) < tol or abs(a.y - ymax) < tol
        on_tb = abs(a.z - zmin) < tol or abs(a.z - zmax) < tol
        if on_side or on_tb:
            picked.add(e)
    if picked.count == 0:
        return 0
    try:
        inp = comp.features.filletFeatures.createInput()
        inp.addConstantRadiusEdgeSet(picked, VI(r), True)
        comp.features.filletFeatures.add(inp)
        return picked.count
    except Exception:
        return -1


def build_case(root, L):
    tbm = adsk.fusion.TemporaryBRepManager.get()
    env, cav, trims, mo_len, dome = case_shapes(L)
    hw = P['case_w'] / 2
    picks = pick_bosses(cav, lambda y, z: abs(y) < hw - 3 and 3 < z < P['case_top'] - P['lip_h'] - 2, count=5)
    bosses, pegs = picks[:3], picks[3:]
    body = None
    for e in env:
        b = e.brep(tbm)
        if body is None:
            body = b
        else:
            tbm.booleanOperation(body, b, adsk.fusion.BooleanTypes.UnionBooleanType)
    keep = notch_box(-P['notch_clear'])
    dome_keep = dome[0].brep(tbm)
    for dpart in dome[1:]:
        tbm.booleanOperation(dome_keep, dpart.brep(tbm), adsk.fusion.BooleanTypes.UnionBooleanType)
    tbm.booleanOperation(dome_keep, box_minmax(-60, 80, -P['dome_max_y'], P['dome_max_y'], 0, 60).brep(tbm),
                         adsk.fusion.BooleanTypes.IntersectionBooleanType)
    for t in trims:
        tool = t.brep(tbm)
        tbm.booleanOperation(tool, keep.brep(tbm), adsk.fusion.BooleanTypes.DifferenceBooleanType)
        tbm.booleanOperation(tool, dome_keep, adsk.fusion.BooleanTypes.DifferenceBooleanType)
        tbm.booleanOperation(body, tool, adsk.fusion.BooleanTypes.DifferenceBooleanType)
    for c in cav:
        tbm.booleanOperation(body, c.brep(tbm), adsk.fusion.BooleanTypes.DifferenceBooleanType)
    out = {}
    for name, xc in (('Case left', -50.0), ('Case right', 50.0)):
        half = tbm.copy(body)
        cutter = tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
            P3((xc, 0, 18)), V3((1, 0, 0)), V3((0, 1, 0)), 10.0, 20.0, 20.0))
        tbm.booleanOperation(half, cutter, adsk.fusion.BooleanTypes.IntersectionBooleanType)
        for y, z in bosses:
            r = 1.1 if name == 'Case left' else 0.85
            tbm.booleanOperation(half, Prim('cyl', p1=(-9, y, z), p2=(9, y, z), r=r).brep(tbm),
                                 adsk.fusion.BooleanTypes.DifferenceBooleanType)
            if name == 'Case left':             # flush screw heads
                x0 = -P['slab_half']
                tbm.booleanOperation(half, Prim('cyl', p1=(x0 - 1, y, z), p2=(x0 + P['lid_cbore'], y, z),
                                                r=P['lid_cbore_d'] / 2).brep(tbm),
                                     adsk.fusion.BooleanTypes.DifferenceBooleanType)
        for y, z in pegs:                       # alignment pegs on the main half, sockets in the lid
            if name == 'Case right':
                tbm.booleanOperation(half, Prim('cyl', p1=(0, y, z), p2=(-P['peg_h'], y, z), r=P['peg_d'] / 2).brep(tbm),
                                     adsk.fusion.BooleanTypes.UnionBooleanType)
            else:
                tbm.booleanOperation(half, Prim('cyl', p1=(0.1, y, z), p2=(-P['peg_h'] - 0.4, y, z),
                                                r=P['peg_d'] / 2 + 0.15).brep(tbm),
                                     adsk.fusion.BooleanTypes.DifferenceBooleanType)
        occ, comp = new_component(root, name)
        add_bodies(comp, [(name, half)])
        round_outer_edges(comp, P['edge_round'])
        out[name] = (occ, comp)
    return out, bosses, mo_len, pegs


def spur(z, m):
    at = math.radians(P['pressure'])
    rp = z * m / 2.0
    return dict(z=z, mt=m, at=at, rp=rp, rb=rp * math.cos(at), ra=rp + 0.8 * m, rf=rp - 1.25 * m, beta=0.0)


def sensor_layout():
    xm = P['sm_x']
    gr, gs = spur(P['sm_z_rod'], P['sm_m']), spur(P['sm_z_sensor'], P['sm_m'])
    cd = gr['rp'] + gs['rp'] + P['sm_cd_extra']
    y = P['sm_sensor_y']
    z = P['rod_z'] - math.sqrt(cd * cd - y * y)          # sensor gear sits back-and-down from the rod
    face_x = xm - P['sm_half']                          # outer face the board frame sits on
    return dict(xm=xm, gr=gr, gs=gs, cd=cd, sc=(xm, y, z), face_x=face_x,
                magnet_face_x=face_x, board_front_x=face_x - P['sensor_gap'])


def build_rod_gear(root):
    """24T spur, square bore for the 4 mm rod, hub both sides (the hubs run in the module walls)."""
    occ, comp = new_component(root, 'Rod gear')
    S = sensor_layout()
    hub_len = 2 * P['sm_half'] - 0.4
    extrude(comp, circle_profile(comp, -hub_len / 2, P['sm_rod_hub_d'] / 2), hub_len, NEW)
    sk = comp.sketches.add(offset_plane(comp, -P['sm_face'] / 2))
    polyline(sk, gear_profile(S['gr']))
    extrude(comp, largest_profile(sk), P['sm_face'], JOIN)
    merge_bodies(comp)
    sk = comp.sketches.add(offset_plane(comp, -hub_len / 2))
    a = P['rod'] / 2 + 0.1
    polyline(sk, [(-a, -a), (a, -a), (a, a), (-a, a)])
    extrude(comp, sk.profiles.item(0), hub_len, CUT)
    comp.bRepBodies.item(0).name = 'Rod gear'
    return occ, comp


def build_sensor_gear(root):
    """12T spur on a shaft; local Z points toward the board (-X in the assembly); magnet pocket in that end."""
    occ, comp = new_component(root, 'Sensor gear')
    S = sensor_layout()
    half = P['sm_half']
    extrude(comp, circle_profile(comp, -(half - 0.6), P['sm_shaft_d'] / 2), 2 * half - 0.6, NEW)   # shaft (to the face)
    sk = comp.sketches.add(offset_plane(comp, -P['sm_face'] / 2))
    polyline(sk, gear_profile(S['gs']))
    extrude(comp, largest_profile(sk), P['sm_face'], JOIN)
    merge_bodies(comp)
    # head at the board end (flush with the module face) holding the magnet, with a solid floor under it
    extrude(comp, circle_profile(comp, half - P['sm_head_len'], P['sm_head_d'] / 2), P['sm_head_len'], JOIN)
    merge_bodies(comp)
    cut = comp.features.extrudeFeatures.createInput(
        circle_profile(comp, half, P['magnet_d'] / 2 + P['magnet_clear']), CUT)
    cut.setDistanceExtent(False, VI(-(P['magnet_t'] + 0.1)))
    cut.participantBodies = own_bodies(comp)
    comp.features.extrudeFeatures.add(cut)
    comp.bRepBodies.item(0).name = 'Sensor gear'
    return occ, comp


def build_sensor_case(root):
    """Press-fit block in the rail around both gears, split at its mid-plane; the left half carries the board frame."""
    tbm = adsk.fusion.TemporaryBRepManager.get()
    S = sensor_layout()
    xm, half, hw = S['xm'], P['sm_half'], P['case_w'] / 2
    rod_c = (xm, 0.0, P['rod_z'])
    sc = S['sc']
    fc = P['sm_face'] / 2 + 0.3
    X = lambda x0, x1, c, r: Prim('cyl', p1=(x0, c[1], c[2]), p2=(x1, c[1], c[2]), r=r)
    cav = [
        X(xm - fc, xm + fc, rod_c, S['gr']['ra'] + 0.5),                       # rod gear
        X(xm - half - 1, xm + half + 1, rod_c, P['sm_rod_hub_d'] / 2 + 0.2),  # rod gear hubs (bearings)
        X(xm - fc, xm + fc, sc, S['gs']['ra'] + 0.5),                          # sensor gear
        X(xm - half - 1, xm + half - 0.3, sc, P['sm_shaft_d'] / 2 + 0.15),    # shaft bearings (blind on the right)
        X(xm - half - 1, xm - half + P['sm_head_len'] + 0.3, sc, P['sm_head_d'] / 2 + 0.3),  # magnet head seat
        X(xm - half - 12, xm - half + 0.5, rod_c, P['sm_rod_clear']),         # rod passes through the board frame
        box_minmax(xm - half + 2, xm + half - 2, -hw + 2, -(S['gr']['ra'] + 2.0), 3.0, 31.0),   # lightening pocket
    ]
    block = box_minmax(xm - half, xm + half, -hw, hw, P['case_floor'], P['case_top'])
    # AS5600 board frame on the left outer face, centred on the sensor shaft; board slides in from the top
    bw, t = P['board_w'] / 2, P['frame_wall']
    fx1 = S['face_x']
    fx0 = S['board_front_x'] - P['board_t'] - t
    frame = [
        box_minmax(fx0, fx1, sc[1] - bw - t, sc[1] - bw, sc[2] - bw - t, sc[2] + bw),     # sides
        box_minmax(fx0, fx1, sc[1] + bw, min(sc[1] + bw + t, hw), sc[2] - bw - t, sc[2] + bw),
        box_minmax(fx0, fx1, sc[1] - bw - t, min(sc[1] + bw + t, hw), sc[2] - bw - t, sc[2] - bw),  # bottom
        box_minmax(fx0, fx0 + t, sc[1] - bw - t, min(sc[1] + bw + t, hw), sc[2] - bw - t, sc[2] + bw - 6),  # back
        box_minmax(S['board_front_x'], fx1, sc[1] - bw - t, sc[1] - bw + 1.5, sc[2] - bw - t, sc[2] + bw),  # lips
        box_minmax(S['board_front_x'], fx1, sc[1] + bw - 1.5, min(sc[1] + bw + t, hw), sc[2] - bw - t, sc[2] + bw),
    ]
    body = block.brep(tbm)
    for f in frame:
        tbm.booleanOperation(body, f.brep(tbm), adsk.fusion.BooleanTypes.UnionBooleanType)
    trims = [box_minmax(xm - 30, xm + 30, -hw - 5, -hw + P['lip_in'], P['case_top'] - P['lip_h'], 60),
             box_minmax(xm - 30, xm + 30, hw - P['lip_in'], hw + 5, P['case_top'] - P['lip_h'], 60)]
    for c in cav + trims:
        tbm.booleanOperation(body, c.brep(tbm), adsk.fusion.BooleanTypes.DifferenceBooleanType)
    # 2 M2 screws + 2 pegs, clear of the cavities
    def keep(y, z):
        return abs(y) < hw - 3 and 3 < z < P['case_top'] - P['lip_h'] - 2
    picks = []
    for yi in range(-25, 26):
        for zi in range(3, 31):
            y, z = float(yi), float(zi)
            if not keep(y, z):
                continue
            q = [(xm, y + 2.0 * math.cos(k * math.pi / 3), z + 2.0 * math.sin(k * math.pi / 3)) for k in range(6)]
            # stay out of the board frame footprint on the left face too
            in_frame = abs(y - sc[1]) < bw + t + 1.5 and abs(z - sc[2]) < bw + t + 1.5
            if not in_frame and not any(c.contains(pt) for c in cav for pt in q):
                picks.append((y, z))
    chosen = []
    while picks and len(chosen) < 4:
        pick = max(picks, key=lambda c: c[1]) if not chosen else \
            max(picks, key=lambda c: min(math.hypot(c[0] - q[0], c[1] - q[1]) for q in chosen))
        chosen.append(pick)
    screws, pegs = chosen[:2], chosen[2:]
    out = {}
    for name, sgn in (('Sensor case left', -1), ('Sensor case right', 1)):
        part = tbm.copy(body)
        cutter = tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
            P3((xm + sgn * 50, 0, 18)), V3((1, 0, 0)), V3((0, 1, 0)), 10.0, 20.0, 20.0))
        tbm.booleanOperation(part, cutter, adsk.fusion.BooleanTypes.IntersectionBooleanType)
        for y, z in screws:
            r = 1.1 if sgn < 0 else 0.85
            tbm.booleanOperation(part, X(xm - half - 5, xm + half + 1, (0, y, z), r).brep(tbm),
                                 adsk.fusion.BooleanTypes.DifferenceBooleanType)
        for y, z in pegs:
            if sgn > 0:
                tbm.booleanOperation(part, X(xm, xm - P['peg_h'], (0, y, z), P['peg_d'] / 2).brep(tbm),
                                     adsk.fusion.BooleanTypes.UnionBooleanType)
            else:
                tbm.booleanOperation(part, X(xm + 0.1, xm - P['peg_h'] - 0.4, (0, y, z), P['peg_d'] / 2 + 0.15).brep(tbm),
                                     adsk.fusion.BooleanTypes.DifferenceBooleanType)
        occ, comp = new_component(root, name)
        add_bodies(comp, [(name, part)])
        round_outer_edges(comp, P['edge_round'])
        out[name] = (occ, comp)
    return out, screws


def build_refs(root, L, mo_len):
    tbm = adsk.fusion.TemporaryBRepManager.get()
    occ, comp = new_component(root, 'REF (not printed)')
    rc = L['rod_c']
    items = [
        ('Worm wheel', Prim('cyl', p1=add(rc, (-3.75, 0, 0)), p2=add(rc, (3.75, 0, 0)), r=7.9)),
        ('Barrel', Prim('cyl', p1=add(rc, (-8.33, 0, 0)), p2=add(rc, (8.33, 0, 0)), r=6.25)),
        ('Rod', box(add(rc, (45, 0, 0)), 110, 4, 4)),
        ('N20', Prim('box', c=add(L['face'], mul(L['u'], mo_len / 2)), u=L['u'], w=L['w'],
                     L=mo_len, W=P['n20_w'], H=P['n20_h'])),
        ('N20 shaft', cyl_u(L, L['pin_c'], -P['pinion_face'] / 2 - 1.0, P['pinion_face'] / 2 + P['pinion_gap'],
                            P['n20_shaft_d'] / 2)),
    ]
    SL = sensor_layout()
    mx, (_, sy, sz) = SL['magnet_face_x'], SL['sc']
    items.append(('Magnet', Prim('cyl', p1=(mx + P['magnet_t'], sy, sz), p2=(mx + 0.05, sy, sz), r=P['magnet_d'] / 2)))
    bf = SL['board_front_x']
    items.append(('AS5600 board', box_minmax(bf - 1.6, bf, sy - 11.5, sy + 11.5, sz - 11.5, sz + 11.5)))
    for i, (s0, s1, r) in enumerate([(-7, -4.5, 2.5), (-4.5, 4.5, 5.5), (4.5, 7, 2.8), (7, 8.6, 4.75),
                                     (8.6, 17, 2.8), (17, 18.77, 4.75), (18.77, 23.77, 3.0)]):
        items.append(('Worm %d' % i, cyl_s(L, s0, s1, r)))
    w2, h, t = P['rail_w'] / 2, P['rail_h'], P['rail_wall']
    rail = [('Rail floor', box_minmax(-40, 100, -w2 - t, w2 + t, -t, 0)),
            ('Rail wall room', box_minmax(-40, 100, -w2 - t, -w2, -t, h)),
            ('Rail wall back', box_minmax(-40, 100, w2, w2 + t, -t, h))]
    bodies = []
    for nm, pr in rail:
        b = pr.brep(tbm)
        tbm.booleanOperation(b, notch_box().brep(tbm), adsk.fusion.BooleanTypes.DifferenceBooleanType)
        bodies.append((nm, b))
    for b in add_bodies(comp, [(nm, pr.brep(tbm)) for nm, pr in items] + bodies):
        if b.name.startswith('Rail'):
            b.opacity = 0.25
    return occ, comp


def color(design, comp, name):
    app = adsk.core.Application.get()
    lib = next((app.materialLibraries.item(i) for i in range(app.materialLibraries.count)
                if app.materialLibraries.item(i).name == 'Fusion Appearance Library'), None)
    if lib is None:
        return
    a = design.appearances.itemByName(name) or design.appearances.addByCopy(lib.appearances.itemByName(name), name)
    for i in range(comp.bRepBodies.count):
        comp.bRepBodies.item(i).appearance = a


def remove_old(design):
    occs = design.rootComponent.occurrences
    for i in range(occs.count - 1, -1, -1):
        if occs.item(i).component.name.startswith(PREFIX):
            occs.item(i).deleteMe()


def build(design, export_dir=None):
    root = design.rootComponent
    L = layout()
    _, adapter = build_adapter(root, L)
    _, pinion = build_pinion(root, L)
    cases, bosses, mo_len, pegs = build_case(root, L)
    _, rod_gear = build_rod_gear(root)
    _, sgear = build_sensor_gear(root)
    scases, sscrews = build_sensor_case(root)
    _, refs = build_refs(root, L, mo_len)
    SL = sensor_layout()

    def occ_named(name):
        return next(root.occurrences.item(i) for i in range(root.occurrences.count)
                    if root.occurrences.item(i).component.name == PREFIX + name)
    place(occ_named('Motor pinion'), add(L['pin_c'], mul(L['u'], -P['pinion_face'] / 2)), L['w'], L['u'])
    place(occ_named('Rod gear'), (SL['xm'], 0, P['rod_z']), (0, 1, 0), (1, 0, 0))
    place(occ_named('Sensor gear'), SL['sc'], (0, 1, 0), (-1, 0, 0))
    place(occ_named('Adapter'), L['S'](P['mouth_s']), L['X'], L['d'])

    color(design, adapter, 'Plastic - Glossy (Yellow)')
    color(design, pinion, 'Plastic - Glossy (Yellow)')
    color(design, cases['Case left'][1], 'Plastic - Translucent Matte (Blue)')
    color(design, cases['Case right'][1], 'Plastic - Matte (Blue)')
    color(design, refs, 'Plastic - Matte (White)')
    color(design, rod_gear, 'Plastic - Glossy (Green)')
    color(design, sgear, 'Plastic - Glossy (Green)')
    color(design, scases['Sensor case left'][1], 'Plastic - Matte (Green)')
    color(design, scases['Sensor case right'][1], 'Plastic - Matte (Green)')

    files = []
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        em = design.exportManager
        for nm, comp in (('adapter', adapter), ('motor_pinion', pinion), ('rod_gear', rod_gear), ('sensor_gear', sgear),
                         ('sensor_case_left', scases['Sensor case left'][1]),
                         ('sensor_case_right', scases['Sensor case right'][1]),
                         ('case_left', cases['Case left'][1]), ('case_right', cases['Case right'][1])):
            path = os.path.join(export_dir, nm + '.stl')
            opt = em.createSTLExportOptions(comp, path)
            opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
            em.execute(opt)
            files.append(path)

    ga, gp = L['ga'], L['gp']
    return '\n'.join([
        'Adapter gear: %dT helical, PD %.2f, OD %.2f, tip (normal) %.2f mm' % (ga['z'], 2 * ga['rp'], 2 * ga['ra'], tip_width_normal(ga)),
        'Motor pinion: %dT helical, PD %.2f, OD %.2f, tip (normal) %.2f mm' % (gp['z'], 2 * gp['rp'], 2 * gp['ra'], tip_width_normal(gp)),
        'Center distance %.2f mm, motor axis swung %.0f°' % (L['cd'], P['motor_rot']),
        'Pinion center (Y, Z): (%.1f, %.1f)' % (L['pin_c'][1], L['pin_c'][2]),
        'Screw holes (Y, Z): %s' % ', '.join('(%.0f, %.0f)' % b for b in bosses),
        'Alignment pegs (Y, Z): %s' % ', '.join('(%.0f, %.0f)' % b for b in pegs),
        'Sensor module at X=%.0f: gears %dT/%dT m%.1f, centres %.2f, sensor shaft (Y, Z)=(%.1f, %.1f), screws %s' % (
            SL['xm'], P['sm_z_rod'], P['sm_z_sensor'], P['sm_m'], SL['cd'], SL['sc'][1], SL['sc'][2],
            ', '.join('(%.0f, %.0f)' % b for b in sscrews)),
        'Exported: %s' % ', '.join(os.path.basename(f) for f in files),
    ])


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
