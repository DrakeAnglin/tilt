"""TiltPartsV4: printable parts for the motorized tilter, version v0.4 (all printed, crossed-helical drive).

Every moving part is printed now; nothing is reused from the factory tilter. The layout keeps the factory geometry
that matters: the 4 mm rod, a worm at 60° so the wand hangs from the same teardrop loop at the same angle and
leaves through the headrail's corner notch, and the 16:1 single-start ratio (self-locking, 11-12 wand turns end to end).

  WORM          printed single-start worm (m 0.88, Ø9.6 pitch, 25° pressure angle), thrust ring, and the 8T 45°
                helical gear (v0.3's tested pair) as part of the same print. Hex socket in the gear's lower face.
  WORM WHEEL    16T, teeth generated from the worm's motion ("hobbed" numerically), barrel journals in both case
                halves, square bore for the rod.
  WAND SHAFT    collar + shaft + teardrop wand loop (same exit and loop position as v0.3), hex socket in the collar.
  HEX KEY       joins worm and wand shaft (or use 12 mm of a 4 mm steel hex key).
  MOTOR PINION  7T 45° helical on the N20's D-flat (6 mm grip). Motor axis parallel to the rod on the lid side (-X),
                beside the worm, so the uncut shaft runs on past the pinion into the main half; the gearbox sits in
                a 1.5 mm square inset in the flat lid.
  CASE          two halves, press fit in the rail like v0.3; the lid carries the N20 socket and the AS5600 board.
  SENSOR GEAR   20T spur on the worm wheel, magnet head out through the lid (as v0.3).

Global coordinates (mm): X along the rod (0 = tilter mid-plane, +X toward the tilt drums), Y across the rail
(-Y = room side), Z up from the rail's inner floor. s = distance along the worm axis from its thread centre,
positive toward the wand.
"""

import math
import os
import traceback

import adsk.core
import adsk.fusion

# ------------------------------------------------------------------ parameters (mm / deg)
P = dict(
    rod_z=24.0, rod=4.0, rod_clear=0.25,
    rail_w=55.5, rail_h=36.5, rail_wall=2.0, lip_in=4.5, lip_h=3.0,
    notch_h=12.0, notch_d=10.5, notch_w=12.0, notch_clear=0.15,
    pressure=25.0,            # all gears: 25° prints cleaner than 20° (less flank overhang on the vertical worm)
    backlash=0.15,
    ss_backlash=0.4,          # sensor spur on the (5° helix) worm wheel teeth: extra room for the helix mismatch
    # worm + worm wheel: same ratio / size class as the factory pair (16:1, m 0.88)
    module_worm=0.88, z_wheel=16, worm_d=9.6, worm_angle=60.0, cd_extra=0.2,
    worm_backlash=0.2,        # axial, cut into the wheel teeth
    worm_root_clear=0.25,     # x module: worm tip to wheel root
    wheel_face=7.5, barrel_r=6.25, wheel_slices=7, wheel_pts=16,
    worm_pin_len=2.0, worm_pin_r=2.5, journal_r=3.5,
    # thrust ring: the ONLY axial stop of the worm, both directions (owner: the factory worm rode up and down)
    flange_r=4.4, flange_s=6.7, flange_t=1.4, flange_clear=0.1,
    thread_end_clear=0.3, worm_pin_end_clear=0.4, worm_thrust_clear=0.15,
    # crossed 45° helicals (v0.3's tested 8T : 7T pair), the 8T now part of the worm. The two shafts don't meet, so
    # the motor sits beside the worm and its shaft runs on past the pinion into the main half
    mn=1.0, helix=45.0, addendum=0.85, dedendum=1.25, hx_cd_extra=0.20,
    z_worm_gear=8, z_pinion=7, worm_gear_face=5.5, pinion_face=6.0,   # owner: 3 mm worm gear looked weak
    worm_gear_s0=16.0,        # s of the worm gear's upper face (grown up the shaft); lower face = collar start, 21.5
    n20_shaft_len=10.0,       # used uncut; the D-flat starts 3.2 mm from the gearbox face and the pinion sits on it
    n20_d_start=3.2,
    motor_inset=1.5,          # gearbox face sits in a square pocket this deep in the (flat) lid: stops it twisting
    hex_af=4.0, hex_depth=6.0, hex_clear=0.15,
    # wand shaft (same exit + loop as v0.3)
    collar_d=8.2, collar_len=2.5, body_d=6.0, body_end_s=37.97, loop_s=43.97,
    loop_r_out=5.4, loop_r_in=2.7, loop_t=4.0, loop_round=1.0,
    # N20 (no encoder)
    n20_w=12.0, n20_h=10.0, n20_gbx=9.0, n20_motor=15.0, n20_end=1.0, n20_shaft_d=3.0, n20_flat=2.5,
    n20_screw_spacing=9.0,
    motor_side=-1,            # N20 on the lid side (owner: +X hits a tilt spindle)
    # case: both halves 8.33 thick (factory barrel width); the N20 gets a pod on the lid only where it sits
    wall=1.6, slab_half=8.33, motor_socket=4.0, pod_wall=1.6, case_w=55.4, case_floor=0.2, case_top=36.3, edge_round=1.0,
    dome_wall=1.2, dome_max_y=21.0,
    plateau_top=38.9, plateau_clear=1.5,
    screw_cbore_d=3.4, screw_cbore=1.2, peg_d=2.5, peg_h=2.0,
    # case screws: M2 flat head from the lid (90° countersink) into M2 heat-set inserts pressed into the main half's
    # back face. The two under the AS5600 board go through the board (pan head there)
    cs_d=4.2, m2_clear_lid=2.4, m2_clear_main=2.2, insert_d=3.2, insert_depth=5.0, insert_wall=1.3, n_case_screws=2,
    case_screw_len=16.0,      # M2 x 16 flat heads; the board screws go through the board + whole lid (M2 x 25 pan)
    # AS5600: board flush on the lid's outer face, chip facing in; magnet glued into the sensor gear inside the case
    ss_z=20, ss_m=0.88, ss_face=3.0, ss_cd_extra=0.15, ss_y=15.3, ss_shaft_d=4.0,
    ss_bore=3.5,              # the gear turns on a Ø4 pin moulded into the main half (gear prints flat, no stub)
    ss_x0=1.5,                # X of the sensor gear's main-half face: centred on the wheel (a worm wheel's teeth change
                              # shape toward its faces, a spur gear only meshes cleanly near the middle)
    ss_head_d=8.0,
    magnet_d=6.0, magnet_t=2.5, magnet_clear=0.15, magnet_gap=0.3, cover_wall=0.8,
    board_w=23.4, board_t=1.6, chip_h=1.5, board_pocket=2.0, board_rim=1.5, board_land=4.7,
    board_holes=((9.0, 9.0), (-9.0, -9.0)),   # (+Y,+Z) and (-Y,-Z) diagonal. TO MEASURE on the real board
)

PREFIX = 'T4 '
LOFT_SECTIONS = 7
WALL_HOLE = 1.3               # tools/fusion_wallcheck.py: min wall round screw / insert / peg holes (insert maker's spec)
# lid prints outer face down (flat, motor in a 1.5 mm inset), main half back face down; pegs + sensor pin on the main half
PEG_HALF = 'Case right'
PRINT_DIRS = {'Case left': (1, 0, 0), 'Case right': (-1, 0, 0)}     # lid: outer face down; main: back face down


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


# ------------------------------------------------------------------ gear math
def inv(x): return math.tan(x) - x


def involute_teeth(z, rp, rb, ra, rf, at, half, rscale=1.0, ascale=1.0, rot=0.0, n_flank=8):
    """Closed outline of z involute teeth. half = tooth half-angle at the pitch circle. rscale / ascale map a
    virtual gear onto a real one (bevel back cone: radius x cos δ, angle / cos δ)."""
    def theta(r):
        return half + inv(at) - (inv(math.acos(rb / r)) if r > rb else 0.0)
    r0 = max(rf, rb)
    radii = [r0 + (ra - r0) * i / (n_flank - 1) for i in range(n_flank)]
    pitch = 2 * math.pi / z
    pts = []
    for k in range(z):
        c = k * pitch + rot
        tooth = []
        if rf < rb:
            tooth.append((rf, c - theta(rb) * ascale))
        tooth += [(r, c - theta(r) * ascale) for r in radii]
        a0, a1 = c - theta(ra) * ascale, c + theta(ra) * ascale
        tooth += [(ra, a0 + (a1 - a0) * i / 3) for i in (1, 2)]
        tooth += [(r, c + theta(r) * ascale) for r in reversed(radii)]
        if rf < rb:
            tooth.append((rf, c + theta(rb) * ascale))
        b0 = tooth[-1][1]
        b1 = c + pitch - theta(rb if rf < rb else r0) * ascale
        tooth += [(rf, b0 + (b1 - b0) * i / 3) for i in (1, 2)]
        pts += tooth
    return [(r * rscale * math.cos(t), r * rscale * math.sin(t)) for r, t in pts]


def spur(z, m):
    at = math.radians(P['pressure'])
    rp = z * m / 2.0
    return dict(z=z, mt=m, at=at, rp=rp, rb=rp * math.cos(at), ra=rp + 0.8 * m, rf=rp - 1.25 * m, beta=0.0)


def gear_profile(g, backlash=None):
    half = math.pi / (2 * g['z']) - ((P['backlash'] if backlash is None else backlash) / 2.0) / g['rp']
    return involute_teeth(g['z'], g['rp'], g['rb'], g['ra'], g['rf'], g['at'], half)


def helical(z):
    b = math.radians(P['helix'])
    mt = P['mn'] / math.cos(b)
    at = math.atan(math.tan(math.radians(P['pressure'])) / math.cos(b))
    rp = z * mt / 2.0
    return dict(z=z, mt=mt, at=at, rp=rp, rb=rp * math.cos(at),
                ra=rp + P['addendum'] * P['mn'], rf=rp - P['dedendum'] * P['mn'], beta=b)


def worm_dims():
    m = P['module_worm']
    rp = P['worm_d'] / 2.0
    return dict(m=m, p=math.pi * m, rp=rp, ra=rp + m, rf=rp - 1.2 * m, at=math.radians(P['pressure']),
                lead_deg=math.degrees(math.atan(m / P['worm_d'])))


def worm_radius(th, z, extra=0.0, tip=0.0):
    """Single-start right-hand worm: outer radius at angle th of the transverse section at axial position z.
    extra thickens the thread (axially, both flanks); tip raises the outside diameter."""
    w = worm_dims()
    p = w['p']
    e = (p * (th - 2 * math.pi * z / p) / (2 * math.pi)) % p
    e = min(e, p - e)
    return min(max(w['rp'] + (p / 4 + extra / 2 - e) / math.tan(w['at']), w['rf']), w['ra'] + tip)


def wheel_dims():
    m, z = P['module_worm'], P['z_wheel']
    w = worm_dims()
    R = z * m / 2.0
    cd = R + w['rp'] + P['cd_extra']
    return dict(m=m, z=z, R=R, ra=R + m, rf=cd - w['ra'] - P['worm_root_clear'] * m, cd=cd)


def wheel_section(zz):
    """Wheel outline in its plane at axial position zz (wheel-local: x toward the worm, y along the worm axis toward
    the wand, z = wheel axis): the worm (thickened by the backlash, tip raised by the root clearance) is moved
    through its mesh with the wheel and every point it ever reaches is removed. Radius per angle, one pitch, then
    patterned (the wheel is 16-fold symmetric)."""
    w, wh = worm_dims(), wheel_dims()
    zw, cd = wh['z'], wh['cd']
    pitch = 2 * math.pi / zw
    tip = P['worm_root_clear'] * w['m']
    reach = w['ra'] + tip

    def hit(x, y, phi):
        wx, wy, wz = zz, x - cd, y               # worm-local: x = wheel axis, y = toward the worm, z = worm axis
        r = math.hypot(wx, wy)
        if r > reach:
            return False
        return r <= worm_radius(math.atan2(wy, wx) - phi, wz, P['worm_backlash'], tip)

    n_th, n_phi = P['wheel_pts'], 240

    def blocked(r, th):
        for k in range(n_phi):
            psi = -1.6 * pitch + 3.2 * pitch * k / n_phi            # wheel turns psi, worm turns -16 psi
            a = th + psi
            if hit(r * math.cos(a), r * math.sin(a), -zw * psi):
                return True
        return False

    radii = []
    for i in range(n_th):
        th = pitch * i / n_th
        r = wh['rf'] - 0.3
        while r < wh['ra'] and not blocked(r, th):
            r += 0.05
        if r < wh['ra']:                               # refine the edge (coarse steps make the loft ripple)
            lo, hi = r - 0.05, r
            for _ in range(7):
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if blocked(mid, th) else (mid, hi)
            r = lo
        radii.append(min(r, wh['ra']))
    out = []
    for k in range(zw):
        for i, r in enumerate(radii):
            a = k * pitch + pitch * i / n_th
            out.append((r * math.cos(a), r * math.sin(a)))
    return out


def wheel_tooth_angle(zz=0.0):
    """Wheel-local angle of a tooth centre in the plane zz (middle of the tip land)."""
    pts = wheel_section(zz)
    n = P['wheel_pts']
    rs = [math.hypot(*q) for q in pts[:n]]
    top = max(rs)
    idx = [i for i, r in enumerate(rs) if r > top - 0.05]
    return 2 * math.pi / P['z_wheel'] * (sum(idx) / len(idx)) / n


# ------------------------------------------------------------------ layout
def layout():
    a = math.radians(P['worm_angle'])
    X = (1.0, 0.0, 0.0)
    d = (0.0, -math.cos(a), -math.sin(a))          # worm axis, toward the wand
    n = (0.0, -math.sin(a), math.cos(a))           # rod axis -> worm axis
    rod_c = (0.0, 0.0, P['rod_z'])
    w, wh = worm_dims(), wheel_dims()
    p0 = add(rod_c, mul(n, wh['cd']))
    S = lambda s: add(p0, mul(d, s))
    # worm thread half-length: covers the wheel's tips
    half = math.sqrt(max(wh['ra'] ** 2 - (wh['cd'] - w['ra']) ** 2, 0)) + 0.5 * w['m']
    ga, gp = helical(P['z_worm_gear']), helical(P['z_pinion'])
    s_g0 = P['worm_gear_s0']
    s_back = s_g0 + P['worm_gear_face']             # gear's lower face = wand collar start
    gc = S((s_g0 + s_back) / 2)
    off = unit(mul(cross(d, X), -1.0))              # common perpendicular, away from the room-side wall
    cd = ga['rp'] + gp['rp'] + P['hx_cd_extra']
    pin_c = add(gc, mul(off, cd))                   # pinion centre (X = 0)
    u = mul(X, P['motor_side'])                     # motor axis, toward the motor
    vz = (0.0, 0.0, 1.0)
    wv = cross(u, vz)
    t_face = P['slab_half'] - P['motor_inset']     # gearbox face, from the pinion centre along u (lid stays 8.33)
    face = add(pin_c, mul(u, t_face))
    return dict(X=X, d=d, n=n, u=u, w=wv, vz=vz, rod_c=rod_c, p0=p0, S=S, half=half, ga=ga, gp=gp, cd=cd, off=off,
                s_g0=s_g0, s_back=s_back, gear_c=gc, pin_c=pin_c, t_face=t_face, face=face, worm=w, wheel=wh)


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


def spline_closed(sketch, pts2d):
    """One closed fitted spline (smooth, few faces: keeps later booleans and interference checks fast)."""
    col = adsk.core.ObjectCollection.create()
    for x, y in pts2d:
        col.add(adsk.core.Point3D.create(x / 10.0, y / 10.0, 0))
    sp = sketch.sketchCurves.sketchFittedSplines.add(col)
    sp.isClosed = True
    return sp


def loft_sections(comp, sections, op=None, smooth=True):
    """Loft through closed sections given as (z_mm, points): smooth splines, or exact polylines (gear teeth with
    sharp corners: a spline would overshoot there)."""
    loft = comp.features.loftFeatures.createInput(op or NEW)
    for zk, pts in sections:
        sk = comp.sketches.add(offset_plane(comp, zk))
        if smooth:
            spline_closed(sk, pts)
        else:
            polyline(sk, pts)
        loft.loftSections.add(sk.profiles.item(0))
    loft.isSolid = True
    if op not in (None, NEW):
        loft.participantBodies = own_bodies(comp)
    return comp.features.loftFeatures.add(loft)


def helical_body(comp, g, z0, face, hand=1.0):
    """Loft the transverse profile through sections rotated along the helix (right hand = +1), from z0."""
    base = gear_profile(g)
    loft = comp.features.loftFeatures.createInput(NEW)
    for k in range(LOFT_SECTIONS):
        zk = face * k / (LOFT_SECTIONS - 1)
        th = hand * zk * math.tan(g['beta']) / g['rp']
        c, s_ = math.cos(th), math.sin(th)
        sk = comp.sketches.add(offset_plane(comp, z0 + zk))
        polyline(sk, [(x * c - y * s_, x * s_ + y * c) for x, y in base])
        loft.loftSections.add(largest_profile(sk))
    loft.isSolid = True
    return comp.features.loftFeatures.add(loft)


def hex_profile(comp, z_mm, af):
    sk = comp.sketches.add(offset_plane(comp, z_mm))
    r = af / math.sqrt(3)
    polyline(sk, [(r * math.cos(math.pi / 3 * k), r * math.sin(math.pi / 3 * k)) for k in range(6)])
    return sk.profiles.item(0)


# ------------------------------------------------------------------ printed parts
def build_worm(root, L):
    """Local z = s (worm axis toward the wand), origin at the thread centre; local x = the rod direction (X)."""
    occ, comp = new_component(root, 'Worm')
    w, half = L['worm'], L['half']
    # threads: transverse section swept straight along the axis with one full twist per lead (right hand)
    z0, length = -half, 2 * half
    sk = comp.sketches.add(offset_plane(comp, z0))
    N = 180
    spline_closed(sk, [(worm_radius(2 * math.pi * k / N - 2 * math.pi * z0 / w['p'], 0.0) * math.cos(2 * math.pi * k / N),
                        worm_radius(2 * math.pi * k / N - 2 * math.pi * z0 / w['p'], 0.0) * math.sin(2 * math.pi * k / N))
                       for k in range(N)])
    sk2 = comp.sketches.add(comp.xZConstructionPlane)
    line = sk2.sketchCurves.sketchLines.addByTwoPoints(sk2.modelToSketchSpace(adsk.core.Point3D.create(0, 0, z0 / 10)),
                                                       sk2.modelToSketchSpace(adsk.core.Point3D.create(0, 0, (z0 + length) / 10)))
    sw = comp.features.sweepFeatures.createInput(sk.profiles.item(0), comp.features.createPath(line, False), NEW)
    sw.twistAngle = adsk.core.ValueInput.createByReal(2 * math.pi * length / w['p'])
    comp.features.sweepFeatures.add(sw)
    # top pin journal, bearing journal down to the gear
    extrude(comp, circle_profile(comp, -half - P['worm_pin_len'], P['worm_pin_r']), P['worm_pin_len'] + 0.3, JOIN)
    extrude(comp, circle_profile(comp, half - 0.3, P['journal_r']), L['s_g0'] - half + 0.6, JOIN)
    extrude(comp, circle_profile(comp, P['flange_s'], P['flange_r']), P['flange_t'], JOIN)     # thrust ring
    # 8T 45° helical (right hand), part of the worm: no spline joint to wear or slip
    helical_body(comp, L['ga'], L['s_g0'], P['worm_gear_face'])
    merge_bodies(comp)
    cut = comp.features.extrudeFeatures.createInput(hex_profile(comp, L['s_back'], P['hex_af'] + P['hex_clear']), CUT)
    cut.setDistanceExtent(False, VI(-P['hex_depth']))
    cut.participantBodies = own_bodies(comp)
    comp.features.extrudeFeatures.add(cut)
    comp.bRepBodies.item(0).name = 'Worm'
    return occ, comp


def build_wand(root, L):
    """Collar + shaft + teardrop loop, local z along the worm axis from the collar's top face (= worm gear's lower face)."""
    occ, comp = new_component(root, 'Wand shaft')
    s0 = L['s_back']
    cl, body_end, loop_c = P['collar_len'], P['body_end_s'] - s0, P['loop_s'] - s0
    rc, rb = P['collar_d'] / 2, P['body_d'] / 2
    sk = comp.sketches.add(comp.xZConstructionPlane)
    toS = lambda r, z: sk.modelToSketchSpace(adsk.core.Point3D.create(r / 10.0, 0, z / 10.0))
    pts = [toS(0, 0), toS(rc, 0), toS(rc, cl), toS(rb, cl), toS(rb, body_end), toS(0, body_end)]
    lines = sk.sketchCurves.sketchLines
    prev = lines.addByTwoPoints(pts[0], pts[1])
    first = prev.startSketchPoint
    for q in pts[2:]:
        prev = lines.addByTwoPoints(prev.endSketchPoint, q)
    axis_line = lines.addByTwoPoints(prev.endSketchPoint, first)
    rev = comp.features.revolveFeatures.createInput(sk.profiles.item(0), axis_line, NEW)
    rev.setAngleExtent(False, adsk.core.ValueInput.createByString('360 deg'))
    comp.features.revolveFeatures.add(rev)
    tbm = adsk.fusion.TemporaryBRepManager.get()
    add_bodies(comp, [('dome', tbm.createSphere(P3((0, 0, body_end)), rb / 10.0))])
    merge_bodies(comp)
    sk = comp.sketches.add(comp.xZConstructionPlane)
    for r in (P['loop_r_out'], P['loop_r_in']):
        sk.sketchCurves.sketchCircles.addByCenterRadius(
            sk.modelToSketchSpace(adsk.core.Point3D.create(0, 0, loop_c / 10.0)), r / 10.0)
    ring = next(sk.profiles.item(i) for i in range(sk.profiles.count) if sk.profiles.item(i).profileLoops.count == 2)
    inp = comp.features.extrudeFeatures.createInput(ring, JOIN)
    inp.setSymmetricExtent(VI(P['loop_t']), True)
    inp.participantBodies = own_bodies(comp)
    comp.features.extrudeFeatures.add(inp)
    merge_bodies(comp)
    round_region(comp, z_min=body_end - 1.0, radii=(P['loop_round'], 0.8, 0.6))
    extrude(comp, hex_profile(comp, 0.0, P['hex_af'] + P['hex_clear']), P['hex_depth'], CUT)
    merge_bodies(comp)
    comp.bRepBodies.item(0).name = 'Wand shaft'
    return occ, comp


def build_hex_key(root):
    occ, comp = new_component(root, 'Hex key')
    ln = 2 * P['hex_depth'] - 0.6
    extrude(comp, hex_profile(comp, -ln / 2, P['hex_af']), ln, NEW)
    comp.bRepBodies.item(0).name = 'Hex key'
    return occ, comp


def build_wheel(root, L):
    """Wheel-local: z = rod axis (X), x toward the worm (n), y along the worm axis toward the wand (d)."""
    occ, comp = new_component(root, 'Worm wheel')
    fw = P['wheel_face']
    ns = P['wheel_slices']
    secs = [(-fw / 2 + fw * i / (ns - 1), None) for i in range(ns)]
    loft_sections(comp, [(zz, wheel_section(zz)) for zz, _ in secs], smooth=False)   # splines wiggle at the tips
    x0, x1 = slab_x(L)
    extrude(comp, circle_profile(comp, x0 + 0.2, P['barrel_r']), -x0 - 0.2 - fw / 2 + 0.3, JOIN)
    extrude(comp, circle_profile(comp, fw / 2 - 0.3, P['barrel_r']), x1 - 0.2 - fw / 2 + 0.3, JOIN)
    merge_bodies(comp)
    sk = comp.sketches.add(offset_plane(comp, x0))
    h = (P['rod'] + P['rod_clear']) * math.sqrt(2) / 2
    a0 = math.atan2(dot((0, 1, 0), L['d']), dot((0, 1, 0), L['n'])) + math.pi / 4   # flats parallel to Y and Z
    polyline(sk, [(h * math.cos(a0 + k * math.pi / 2), h * math.sin(a0 + k * math.pi / 2)) for k in range(4)])
    extrude(comp, sk.profiles.item(0), x1 - x0, CUT)
    comp.bRepBodies.item(0).name = 'Worm wheel'
    return occ, comp


def build_pinion(root, L):
    """7T 45° helical (right hand) on the N20. Local z = the motor axis toward the motor; the whole gear sits on the
    shaft's D-flat (D-bore all through, 6 mm of grip)."""
    occ, comp = new_component(root, 'Motor pinion')
    helical_body(comp, L['gp'], 0.0, P['pinion_face'])
    sk = comp.sketches.add(comp.xYConstructionPlane)
    r = P['n20_shaft_d'] / 2.0 + 0.05
    fx = P['n20_flat'] - P['n20_shaft_d'] / 2.0 + 0.05
    fy = math.sqrt(r * r - fx * fx)
    pt = lambda x, y: adsk.core.Point3D.create(x / 10.0, y / 10.0, 0)
    arc = sk.sketchCurves.sketchArcs.addByThreePoints(pt(fx, fy), pt(-r, 0), pt(fx, -fy))
    sk.sketchCurves.sketchLines.addByTwoPoints(arc.startSketchPoint, arc.endSketchPoint)
    extrude(comp, sk.profiles.item(0), P['pinion_face'], CUT)
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



def slab_x(L):
    """X of the lid's outer face and the main half's back face. The lid is flat and as thick as the motor needs: its
    gearbox face sits motor_inset deep in a square pocket in the lid's outer face."""
    return min(-P['slab_half'], L['face'][0] + P['motor_inset'] * P['motor_side']), P['slab_half']


def motor_pod(L):
    """Box on the lid around the N20 socket, from the split face to the socket's outer end."""
    q, pw = L['pin_c'], P['pod_wall']
    x_out = L['face'][0] + P['motor_inset'] * P['motor_side']
    hy, hz = (P['n20_w'] + 0.3) / 2 + pw, (P['n20_h'] + 0.3) / 2 + pw
    return box_minmax(min(x_out, 0.0), max(x_out, 0.0), q[1] - hy, q[1] + hy, max(P['case_floor'], q[2] - hz), q[2] + hz)


def case_shapes(L):
    rc, u, w = L['rod_c'], L['u'], L['w']
    wd, wh, ga, gp = L['worm'], L['wheel'], L['ga'], L['gp']
    half = L['half']
    pf = P['pinion_face'] / 2 + 0.3
    mo_len = P['n20_gbx'] + P['n20_motor'] + P['n20_end']
    mo_c = add(L['face'], mul(u, (mo_len + 6) / 2))
    hw = P['case_w'] / 2
    thr, free, fc = P['worm_thrust_clear'], P['thread_end_clear'], P['flange_clear']
    pin_end = -half - P['worm_pin_len'] - P['worm_pin_end_clear']
    x0, x1 = slab_x(L)
    collar_end = L['s_back'] + P['collar_len']
    fw = P['wheel_face'] / 2 + 0.4
    named = [
        ('wheel teeth', Prim('cyl', p1=add(rc, (-fw, 0, 0)), p2=add(rc, (fw, 0, 0)), r=wh['ra'] + 0.45)),
        ('barrel bore', Prim('cyl', p1=add(rc, (x0 - 1, 0, 0)), p2=add(rc, (x1 + 1, 0, 0)), r=P['barrel_r'] + 0.15)),
        # worm: thrust up on the thread's top face, the thrust ring both ways (wand pull: collar -> case shoulder)
        ('worm top pin', cyl_s(L, pin_end, -half, P['worm_pin_r'] + 0.15)),
        ('worm threads', cyl_s(L, -half - free, half + free, wd['ra'] + 0.45)),       # threads run free both ends
        *sensor_cavities(),
        ('worm journal', cyl_s(L, half + free - 0.01, L['s_g0'] - 0.3, P['journal_r'] + 0.15)),
        ('worm thrust groove', cyl_s(L, P['flange_s'] - fc, P['flange_s'] + P['flange_t'] + fc, P['flange_r'] + 0.3)),
        ('worm gear', cyl_s(L, L['s_g0'] - 0.3, L['s_back'] + 0.3, ga['ra'] + 0.4)),     # its faces run free
        ('wand collar', cyl_s(L, L['s_back'], collar_end + thr, P['collar_d'] / 2 + 0.3)),
        ('wand exit', cyl_s(L, collar_end + thr - 0.01, collar_end + 40, P['body_d'] / 2 + 0.3)),
        ('pinion', cyl_u(L, L['pin_c'], -pf, pf, gp['ra'] + 0.5)),
        ('motor shaft', cyl_u(L, L['pin_c'], -(L['t_face'] - P['n20_shaft_len']) - 0.5, L['t_face'] + 0.1,
                              P['n20_shaft_d'] / 2 + 0.5)),     # the shaft runs on into the main half
        ('motor socket', Prim('box', c=mo_c, u=u, w=w, L=mo_len + 6, W=P['n20_w'] + 0.3, H=P['n20_h'] + 0.3)),
    ]
    # gearbox screw M1.6 x 4: only the hole away from the worm gear; the socket stops rotation
    pocket_end = P['pinion_face'] / 2 + 0.3
    far = max((-1, 1), key=lambda sg: norm(sub(add(L['pin_c'], mul(w, sg * P['n20_screw_spacing'] / 2)), L['gear_c'])))
    hp = add(L['pin_c'], mul(w, far * P['n20_screw_spacing'] / 2))
    named.append(('motor screw hole', cyl_u(L, hp, pocket_end - 0.5, L['t_face'] + 0.5, 0.9)))
    named.append(('motor screw counterbore', cyl_u(L, hp, pocket_end - 0.5, L['t_face'] - 2.0,   # M1.6 x 4: 2 mm
                                                   P['screw_cbore_d'] / 2)))                    # wall + 2 mm thread
    for nm, pr in named:
        pr.label = nm
    cav = [pr for _, pr in named]
    slab = box_minmax(x0, x1, -hw, hw, P['case_floor'], P['case_top'])
    dw = P['dome_wall']
    dome = [cyl_s(L, -half - free - dw, 4.8, wd['ra'] + 0.45 + dw),
            cyl_s(L, pin_end, -half - free - dw + 0.01, P['worm_pin_r'] + 0.15 + dw),
            Prim('cyl', p1=L['S'](pin_end), p2=L['S'](pin_end - dw), r=P['worm_pin_r'] + 0.15 + dw, r2=2.0)]
    py = hw - P['lip_in'] - P['plateau_clear']
    plateau = box_minmax(x0, x1, -py, py, P['case_top'] - 1.0, P['plateau_top'])
    env = [slab, plateau, *dome, notch_box(-P['notch_clear'])]
    trims = [
        box_minmax(-60, 80, -hw - 5, -py, P['case_top'] - P['lip_h'], 60),
        box_minmax(-60, 80, py, hw + 5, P['case_top'] - P['lip_h'], 60),
        box_minmax(-60, 80, -60, 60, P['plateau_top'], 80),
        box_minmax(-60, 80, -60, 60, -20, P['case_floor']),
        box_minmax(-60, 80, -60, -hw, -20, 80),
        box_minmax(-60, 80, hw, 60, -20, 80),
    ]
    return env, cav, trims, mo_len, dome


def pick_bosses(cav, keep_in, count=3, clear_r=1.9, chosen=None):
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
                    q = (x, y + clear_r * math.cos(a), z + clear_r * math.sin(a))
                    if any(c.contains(q) for c in cav):
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                cands.append((y, z))
    chosen = list(chosen or [])
    count += len(chosen)
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


def case_plan(L):
    """Everything that defines the two case halves: envelope, cavities, trims, and the per-half holes / pegs.
    Used by build_case() and by tools/fusion_wallcheck.py (so the checker sees exactly what gets built).
    Case screws: M2 flat head from the lid's outer face into heat-set inserts pressed into the main half's back face.
    The two AS5600 holes are case screws too (through the board)."""
    env, cav, trims, mo_len, dome = case_shapes(L)
    hw = P['case_w'] / 2
    on_board = board_footprint(margin=2.0)
    pod = motor_pod(L)
    ir = P['insert_d'] / 2 + P['insert_wall']      # insert hole radius + the insert's minimum wall

    def screw_ok(y, z):
        if abs(y) > hw - ir or z < P['case_floor'] + ir:
            return False
        if abs(y) > hw - P['lip_in'] - P['plateau_clear'] - ir and z > P['case_top'] - P['lip_h'] - ir:
            return False                          # next to the lip step
        if pod.contains((pod.c[0], y, z), grow=ir):
            return False
        return z < P['case_top'] - ir and not on_board(y, z)
    fixed = board_holes()
    picks = pick_bosses(cav, screw_ok, count=P['n_case_screws'] + 2, clear_r=ir, chosen=fixed)
    bosses, pegs = picks[:len(fixed) + P['n_case_screws']], picks[len(fixed) + P['n_case_screws']:]
    x0, x1 = slab_x(L)
    X = lambda xa, xb, y, z, r, r2=None: Prim('cyl', p1=(xa, y, z), p2=(xb, y, z), r=r, **({} if r2 is None else {'r2': r2}))
    holes = {'Case left': [], 'Case right': []}
    for k, (y, z) in enumerate(bosses):
        holes['Case left'].append(('screw clearance', X(x0 - 1, 0.5, y, z, P['m2_clear_lid'] / 2)))
        if (y, z) not in fixed:                   # flat head (board screws: head on the board). In a lid thicker than
            cs = P['cs_d'] / 2                    # the screw allows, a counterbore takes the head down to its seat
            seat = max(x0, x1 - 0.8 - P['case_screw_len'])
            if seat > x0:
                holes['Case left'].append(('screw counterbore', X(x0 - 1, seat + 0.01, y, z, cs + 0.1)))
            holes['Case left'].append(('screw countersink', X(seat - 0.01, seat + cs - P['m2_clear_lid'] / 2, y, z, cs,
                                                              P['m2_clear_lid'] / 2)))
        holes['Case right'].append(('screw clearance', X(-0.5, x1 - P['insert_depth'] + 0.01, y, z, P['m2_clear_main'] / 2)))
        holes['Case right'].append(('screw insert', X(x1 - P['insert_depth'], x1 + 1, y, z, P['insert_d'] / 2)))
    for y, z in pegs:
        holes['Case left'].append(('peg socket', X(-(P['peg_h'] + 0.4), 0.1, y, z, P['peg_d'] / 2 + 0.15)))
    peg_solids = [X(0.5, -P['peg_h'], y, z, P['peg_d'] / 2) for y, z in pegs]   # on the main half (prints split face up)
    S = sensor_layout()                           # sensor gear pin, grows up from the main half's pocket floor
    pin_solids = [X(S['gear_x0'] + 0.8, S['gear_x0'] - P['ss_bore'] + 0.2, S['y'], S['z'], P['ss_shaft_d'] / 2)]
    return dict(env=env, cav=cav, trims=trims, dome=dome, mo_len=mo_len, bosses=bosses, pegs=pegs,
                holes=holes, peg_solids=peg_solids, pin_solids=pin_solids)


def build_case(root, L):
    tbm = adsk.fusion.TemporaryBRepManager.get()
    plan = case_plan(L)
    env, cav, trims, dome, mo_len = plan['env'], plan['cav'], plan['trims'], plan['dome'], plan['mo_len']
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
    tbm.booleanOperation(dome_keep, box_minmax(-60, 80, -P['dome_max_y'], P['dome_max_y'], 0, P['plateau_top']).brep(tbm),
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
        if name == PEG_HALF:                    # alignment pegs + sensor gear pin: main half, printed split face up
            for peg in plan['peg_solids'] + plan['pin_solids']:
                tbm.booleanOperation(half, peg.brep(tbm), adsk.fusion.BooleanTypes.UnionBooleanType)
        for _, h in plan['holes'][name]:
            tbm.booleanOperation(half, h.brep(tbm), adsk.fusion.BooleanTypes.DifferenceBooleanType)
        occ, comp = new_component(root, name)
        add_bodies(comp, [(name, half)])
        round_outer_edges(comp, P['edge_round'])
        out[name] = (occ, comp)
    return out, plan['bosses'], mo_len, plan['pegs']

def sensor_layout():
    """Sensor gear axis (parallel to the rod), magnet and board planes. The board lies flush on the lid's outer face,
    chip facing in, over a shallow pocket; the magnet sits in the gear's short head, 0.8 mm of lid below the pocket."""
    gs = spur(P['ss_z'], P['ss_m'])
    wheel_rp = P['z_wheel'] * P['module_worm'] / 2.0
    cd = wheel_rp + gs['rp'] + P['ss_cd_extra']
    y = P['ss_y']
    z = P['rod_z'] - math.sqrt(cd * cd - y * y)
    lid_face = slab_x(layout())[0]
    floor_x = lid_face + P['board_pocket']               # pocket floor (chip side)
    magnet_x = floor_x + P['cover_wall'] + P['magnet_gap']  # magnet face = end of the gear's head
    return dict(gs=gs, cd=cd, y=y, z=z, lid_face=lid_face, floor_x=floor_x, magnet_x=magnet_x,
                gear_x0=P['ss_x0'], gear_x1=P['ss_x0'] - P['ss_face'],
                chip_x=lid_face + P['chip_h'], board_back_x=lid_face - P['board_t'])


def build_sensor_gear(root):
    """20T spur meshing with the worm wheel, short head holding the magnet, bore for the case pin.
    Local z points to the lid (-X); local origin = the gear's main-half face (X = ss_x0): it prints on that face."""
    occ, comp = new_component(root, 'Sensor gear')
    S = sensor_layout()
    head_end = S['gear_x0'] - S['magnet_x']                # local z of the magnet face
    sk = comp.sketches.add(comp.xYConstructionPlane)
    polyline(sk, gear_profile(S['gs'], P['ss_backlash']))
    extrude(comp, largest_profile(sk), P['ss_face'], NEW)
    extrude(comp, circle_profile(comp, P['ss_face'] - 0.3, P['ss_head_d'] / 2), head_end - P['ss_face'] + 0.3, JOIN)
    merge_bodies(comp)
    cut = comp.features.extrudeFeatures.createInput(
        circle_profile(comp, head_end, P['magnet_d'] / 2 + P['magnet_clear']), CUT)
    cut.setDistanceExtent(False, VI(-(P['magnet_t'] + 0.1)))     # glue the magnet in, face flush with the head
    cut.participantBodies = own_bodies(comp)
    comp.features.extrudeFeatures.add(cut)
    extrude(comp, circle_profile(comp, 0.0, P['ss_shaft_d'] / 2 + 0.15), P['ss_bore'], CUT)
    comp.bRepBodies.item(0).name = 'Sensor gear'
    return occ, comp


def sensor_cavities():
    S = sensor_layout()
    c = (0.0, S['y'], S['z'])
    X = lambda x0, x1, r: Prim('cyl', p1=(x0, c[1], c[2]), p2=(x1, c[1], c[2]), r=r)
    hb, rim, land = P['board_w'] / 2, P['board_rim'], P['board_land']
    pin = hb - rim
    B = lambda y0, y1, z0, z1: box_minmax(S['lid_face'] - 1.0, S['floor_x'], c[1] + y0, c[1] + y1, c[2] + z0, c[2] + z1)
    return [
        ('sensor gear', X(S['gear_x0'] + 0.3, S['gear_x1'] - 0.3, S['gs']['ra'] + 0.4)),     # straddles the split
        ('magnet head', X(S['gear_x1'] + 0.01, S['magnet_x'] - P['magnet_gap'], P['ss_head_d'] / 2 + 0.3)),
        # pocket under the board for the chip, parts and solder joints; the board rests on its rim and on two lands
        # round the screw holes (the (+Y,+Z) and (-Y,-Z) corners)
        ('AS5600 pocket', B(-pin, pin, -(hb - land), hb - land)),
        ('AS5600 pocket', B(-pin, hb - land, hb - land, pin)),
        ('AS5600 pocket', B(-(hb - land), pin, -pin, -(hb - land))),
    ]


def board_holes():
    S = sensor_layout()
    return [(round(S['y'] + dy, 2), round(S['z'] + dz, 2)) for dy, dz in P['board_holes']]


def board_footprint(margin=0.0):
    S = sensor_layout()
    hb = P['board_w'] / 2 + margin
    return lambda y, z: abs(y - S['y']) < hb and abs(z - S['z']) < hb


def build_refs(root, L, mo_len):
    tbm = adsk.fusion.TemporaryBRepManager.get()
    occ, comp = new_component(root, 'REF (not printed)')
    rc = L['rod_c']
    items = [
        ('Rod', box(add(rc, (45, 0, 0)), 110, 4, 4)),
        ('N20', Prim('box', c=add(L['face'], mul(L['u'], mo_len / 2)), u=L['u'], w=L['w'],
                     L=mo_len, W=P['n20_w'], H=P['n20_h'])),
        ('N20 shaft', cyl_u(L, L['pin_c'], L['t_face'] - P['n20_shaft_len'], L['t_face'], P['n20_shaft_d'] / 2)),
    ]
    SL = sensor_layout()
    sy, sz = SL['y'], SL['z']
    items.append(('Magnet', Prim('cyl', p1=(SL['magnet_x'] + P['magnet_t'], sy, sz), p2=(SL['magnet_x'] + 0.05, sy, sz),
                                 r=P['magnet_d'] / 2)))
    hb = P['board_w'] / 2
    items.append(('AS5600 board', box_minmax(SL['board_back_x'], SL['lid_face'] - 0.02, sy - hb, sy + hb, sz - hb, sz + hb)))
    items.append(('AS5600 chip', box_minmax(SL['lid_face'], SL['chip_x'], sy - 2.5, sy + 2.5, sz - 2.0, sz + 2.0)))
    w2, h, t = P['rail_w'] / 2, P['rail_h'], P['rail_wall']
    rail = [('Rail floor', box_minmax(-50, 100, -w2 - t, w2 + t, -t, 0)),
            ('Rail wall room', box_minmax(-50, 100, -w2 - t, -w2, -t, h)),
            ('Rail wall back', box_minmax(-50, 100, w2, w2 + t, -t, h))]
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


def rotate_about(v, axis, ang):
    """Rodrigues rotation of v about a unit axis."""
    c, s = math.cos(ang), math.sin(ang)
    return add(add(mul(v, c), mul(cross(axis, v), s)), mul(axis, dot(axis, v) * (1 - c)))


def build(design, export_dir=None):
    root = design.rootComponent
    L = layout()
    _, worm = build_worm(root, L)
    _, wand = build_wand(root, L)
    _, key = build_hex_key(root)
    _, wheel = build_wheel(root, L)
    _, pinion = build_pinion(root, L)
    cases, bosses, mo_len, pegs = build_case(root, L)
    _, sgear = build_sensor_gear(root)
    _, refs = build_refs(root, L, mo_len)
    SL = sensor_layout()

    def occ_named(name):
        return next(root.occurrences.item(i) for i in range(root.occurrences.count)
                    if root.occurrences.item(i).component.name == PREFIX + name)
    X, d = L['X'], L['d']
    place(occ_named('Worm'), L['p0'], X, d)                    # thread phase = the one the wheel was cut with
    place(occ_named('Wand shaft'), L['S'](L['s_back']), X, d)
    place(occ_named('Hex key'), L['S'](L['s_back']), X, d)
    place(occ_named('Worm wheel'), L['rod_c'], L['n'], X)
    place(occ_named('Motor pinion'), add(L['pin_c'], mul(L['u'], -P['pinion_face'] / 2)), L['w'], L['u'])
    # sensor gear phase: a tooth space where the wheel has a tooth on the centre line, then rolled with the wheel
    v = sub((0, SL['y'], SL['z']), L['rod_c'])
    line_w = math.atan2(dot(v, L['d']), dot(v, L['n']))                # centre line, wheel-local angle
    pw = 2 * math.pi / P['z_wheel']
    dw = (wheel_tooth_angle((SL['gear_x0'] + SL['gear_x1']) / 2) - line_w + pw / 2) % pw - pw / 2   # nearest tooth
    beta = math.atan2(v[2], -v[1])                                       # toward the rod, sensor-local angle
    rho = beta + dw * P['z_wheel'] / P['ss_z'] + math.pi / P['ss_z']
    place(occ_named('Sensor gear'), (SL['gear_x0'], SL['y'], SL['z']), rotate_about((0, 1, 0), (-1, 0, 0), rho), (-1, 0, 0))

    for comp in (worm, wand, pinion):
        color(design, comp, 'Plastic - Glossy (Yellow)')
    color(design, key, 'Plastic - Glossy (Red)')
    color(design, wheel, 'Plastic - Glossy (Green)')
    color(design, cases['Case left'][1], 'Plastic - Translucent Matte (Blue)')
    color(design, cases['Case right'][1], 'Plastic - Matte (Blue)')
    color(design, refs, 'Plastic - Matte (White)')
    color(design, sgear, 'Plastic - Glossy (Green)')

    files = []
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        em = design.exportManager
        for nm, comp in (('worm', worm), ('wand_shaft', wand), ('hex_key', key), ('worm_wheel', wheel),
                         ('motor_pinion', pinion), ('sensor_gear', sgear),
                         ('case_left', cases['Case left'][1]), ('case_right', cases['Case right'][1])):
            path = os.path.join(export_dir, nm + '.stl')
            opt = em.createSTLExportOptions(comp, path)
            opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
            em.execute(opt)
            files.append(path)

    wd, wh, ga, gp = L['worm'], L['wheel'], L['ga'], L['gp']
    x0, x1 = slab_x(L)
    return '\n'.join([
        'Worm: single start m%.2f, pitch Ø%.2f, OD %.2f, lead angle %.1f° (self-locking), threads s ±%.2f' % (
            wd['m'], 2 * wd['rp'], 2 * wd['ra'], wd['lead_deg'], L['half']),
        'Worm wheel: %dT, OD %.2f, centre distance %.2f' % (wh['z'], 2 * wh['ra'], wh['cd']),
        'Crossed helicals: worm %dT (face %.1f) / motor %dT (face %.1f) mn%.1f 45°, centres %.2f, pinion at (Y %.1f, Z %.1f)' % (
            ga['z'], P['worm_gear_face'], gp['z'], P['pinion_face'], P['mn'], L['cd'], L['pin_c'][1], L['pin_c'][2]),
        'N20 gearbox face X=%.2f in a %.1f mm pocket, %.0f mm shaft uncut (tip at X=%.2f, in the main half), D-flat '
        'from X=%.2f, pinion X %.1f..%.1f; case X %.2f .. %.2f' % (
            L['face'][0], P['motor_inset'], P['n20_shaft_len'], L['face'][0] + P['n20_shaft_len'],
            L['face'][0] + P['n20_d_start'], -P['pinion_face'] / 2, P['pinion_face'] / 2, x0, x1),
        'Screw holes (Y, Z): %s' % ', '.join('(%.0f, %.0f)' % b for b in bosses),
        'Alignment pegs (Y, Z): %s' % ', '.join('(%.0f, %.0f)' % b for b in pegs),
        'AS5600 board screws (Y, Z): %s; magnet face X=%.2f, chip X=%.2f (gap %.2f mm)' % (
            ', '.join('(%.1f, %.1f)' % b for b in board_holes()), SL['magnet_x'], SL['chip_x'], SL['magnet_x'] - SL['chip_x']),
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
