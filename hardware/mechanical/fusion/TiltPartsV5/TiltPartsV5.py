"""TiltPartsV5: the tilter v0.5 - v0.4 plus a printed swing-arm clutch between the N20 and the worm.

Why: in v0.4 the wand had to spin the N20 backward through its gearbox (hard by hand), and the N20 had to drive the
worm through the same train (too weak). v0.5 puts a swing-arm ("pendulum gear") clutch in the motor's path:

  N20 -- 8T pinion -- 9T idler A or B (on a swing arm) -- 12T output -- (same shaft) 7T helical -- worm's 8T -- worm -- rod

The arm pivots on the pinion's hub and is dragged round with it by three small flexure pads. Motor on: the arm swings
until one idler meshes the 12T (a printed stop post in the module sets the mesh depth) and drives it. The firmware ends
every move with a short reverse nudge that swings the arm back to the middle, where neither idler touches the 12T: the
wand then turns only the worm and the 12T / 7T shaft, never the motor. The 8T : 12T adds 1.5:1, so the N20 can be a
stronger (slower) one.

Unchanged from v0.4 (built by TiltPartsV4's own code): worm, worm wheel, sensor gear, the main half. Changed: the 7T
is now on its own shaft (journal in the main half, bore in the lid) with the 12T on its far end; the lid loses the
motor socket and screw. New: 8T pinion (on the N20's D-flat), swing arm with two printed idler pins, two 9T idlers. The
N20 moves into the (longer) sensor module: TiltPodV5.

Global coordinates as TiltPartsV4 (mm): X along the rod (lid's outer face X -8.33, the module beyond it), Y across
(-Y room side), Z up from the rail floor.
"""

import importlib.util
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('tp4_for_v5', os.path.join(_HERE, '..', 'TiltPartsV4', 'TiltPartsV4.py'))
T4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T4)
adsk = T4.adsk
P = T4.P
PREFIX = 'T5 '
T4.PREFIX = PREFIX

# ------------------------------------------------------------------ clutch parameters (mm / deg)
C = dict(
    # rev 2 (after the independent review): taller teeth (contact ratio 1.16 / 1.18, was 0.93 / 0.96), 9T pinion (more
    # wall round its D-bore), 1.0 mm neutral gap (a +-8 deg neutral window for the nudge), a clutch plate that ties the
    # motor's gearbox nose to the clutch shaft's end (center distances no longer depend on the module's bolts), soft
    # cantilever fingers instead of the stiff pads, a full-length pinion hub under the arm, a real shoulder for the 12T
    m=0.8, z_pin=9, z_idl=9, z_out=12, addendum=1.0, dedendum=1.25,
    face=5.8,
    cd_extra=0.0,                            # rev 3: standard spacing (contact ratio ~1.29; the profile already has 0.15 backlash)
    out_gap=0.6,                             # pinion tips to the 12T's tips (they never mesh)
    neutral_gap=1.0,                         # idler tips to the 12T's tips with the arm in the middle
    theta=338.0,                             # direction of the motor axis from the 12T's axis (deg, from +Z toward +Y)
    motor_face_x=-18.6,                      # N20 gearbox face (seated 0.8 deep in the clutch plate)
    plate_x=(-19.4, -16.6), plate_pocket=0.8, plate_fit=0.3, plate_wall=1.2,   # rev 3: pocket loose (anti-rotation only)
    plate_hub_clear=0.1,                     # rev 3: the plate locates on the pinion's hub (the shaft's true axis)
    gear_x=(-14.4, -8.6),                    # clutch gear plane (lid face -8.33: idlers can float only 0.3)
    arm_x=(-16.4, -14.6),                    # arm plate, between the clutch plate and the gears
    pin_hub_d=5.5, pin_hub_x0=-17.8,         # pinion hub: through the clutch plate (0.8 off the gearbox face) and the arm
    arm_bore_clear=0.1,
    arm_hub_r=6.0, finger_t=0.8, finger_slot=0.8, finger_span=120.0, finger_interf=0.3, finger_bump_r=0.5,
    finger_roots=(150.0, 330.0),             # each finger runs CCW from its root; free end + bump at root + span
    lobe_w=4.6, pin_d=3.0, pin_tip_x=-8.45, pin_boss_d=4.6, pin_boss_x=-14.45, idler_bore_clear=0.1,
    pin_press=0.05,                          # rev 3: steel Ø3 x 8 dowels pressed into the arm (Ø2.95 holes)
    stop_dir=62.0, stop_r=7.2, stop_d=3.0, stop_clear=0.15, slot_wall=1.2, stop_tip_x=-14.7,
    tail_span=(22.0, 100.0),
    avoid=(((-23.0, 27.0), 3.8),),          # module bolt C's boss (TiltPodV5 bolts_rim): the plate keeps clear of it
    shaft_d=6.0, shaft_bore_clear=0.15,      # rev 3: Ø6 through the lid, so the 12T's Ø5 D-section has a real shoulder
    pin7_d=4.0, pin7_x=(4.1, 0.0), pin7_bore_clear=0.15, pin7_depth=3.4,
    thrust_ring=(3.0, 3.65, 0.15),           # lid-side thrust ring (bears on the lid outside its Ø6.3 bore); 0.35 total end float
    boss_face_gap=0.2,                       # main-half thrust boss face 0.2 off the 7T
    d_r=2.5, d_flat=1.8, d_fit=0.05,         # rev 3: 12T on a Ø5 D-section (flat 1.8 from the axis), glued
    journal_d=3.6, journal_x=(-14.3, -19.3), journal_clear=0.1,    # rev 3: Ø3.6 so the 12T's bore passes over it
)
c = C


def spur_c(z):
    g = T4.spur(z, c['m'])
    g['ra'] = g['rp'] + c['addendum'] * c['m']
    g['rf'] = g['rp'] - c['dedendum'] * c['m']
    return g


def clutch_layout():
    """2D positions (Y, Z) of the 12T axis O (= the old motor axis), the motor axis M, the idlers at neutral and at
    both stops, and the arm rotation at the stops."""
    L = T4.layout()
    O = (L['pin_c'][1], L['pin_c'][2])
    gp, gi, go = spur_c(c['z_pin']), spur_c(c['z_idl']), spur_c(c['z_out'])
    a = gp['rp'] + gi['rp'] + c['cd_extra']               # pinion - idler
    b = gi['rp'] + go['rp'] + c['cd_extra']               # idler - 12T (meshed)
    d = gp['ra'] + go['ra'] + c['out_gap']                # pinion - 12T
    neu = gi['ra'] + go['ra'] + c['neutral_gap']
    th = math.radians(c['theta'])
    M = (O[0] + d * math.sin(th), O[1] + d * math.cos(th))
    base = math.atan2(O[1] - M[1], O[0] - M[0])            # direction M -> O
    ang = lambda cc, b_, a_: math.acos((b_ * b_ + cc * cc - a_ * a_) / (2 * b_ * cc))
    phi = ang(d, a, b)                                     # M angle (from M->O) of a meshed idler
    psi = ang(d, a, neu)                                   # ... of an idler at neutral
    I = lambda off: (M[0] + a * math.cos(base + off), M[1] + a * math.sin(base + off))
    return dict(L=L, O=O, M=M, a=a, b=b, d=d, neu=neu, base=base, phi=phi, psi=psi, swing=psi - phi,
                A=I(psi), B=I(-psi), A_on=I(phi), B_on=I(-phi), A_far=I(2 * psi - phi), B_far=I(-(2 * psi - phi)),
                gp=gp, gi=gi, go=go)


# ------------------------------------------------------------------ lid / main half changes (patched into TiltPartsV4)
_case_shapes_v4 = T4.case_shapes


def case_shapes_v5(L):
    env, cav, trims, mo_len, dome = _case_shapes_v4(L)
    drop = {'motor socket', 'motor screw hole', 'motor screw counterbore', 'motor shaft'}
    cav = [pr for pr in cav if getattr(pr, 'label', '') not in drop]
    oy, oz = L['pin_c'][1], L['pin_c'][2]
    X = lambda x0, x1, r, nm: _lab(T4.Prim('cyl', p1=(x0, oy, oz), p2=(x1, oy, oz), r=r), nm)
    cav.append(X(-9.5, -2.9, c['shaft_d'] / 2 + c['shaft_bore_clear'], 'clutch shaft bore'))          # through the lid
    return env, cav, trims, mo_len, dome


def _lab(pr, nm):
    pr.label = nm
    return pr


def motor_pod_v5(L):
    """No motor pod on the lid any more (the N20 lives in the module): a token box far outside the case."""
    return T4.box_minmax(500, 501, 500, 501, 500, 501)


_case_plan_v4 = T4.case_plan


def case_plan_v5(L):
    plan = _case_plan_v4(L)
    oy, oz = L['pin_c'][1], L['pin_c'][2]
    x0, x1 = c['pin7_x']                    # grows up from the main half's pinion pocket floor (prints split face up)
    plan['pin_solids'].append(T4.Prim('cyl', p1=(x0, oy, oz), p2=(x1, oy, oz), r=c['pin7_d'] / 2))
    pf = P['pinion_face']                   # thrust boss round the pin: the 7T's main-half face bears only near its axis
    plan['pin_solids'].append(T4.Prim('cyl', p1=(pf / 2 + 0.3 + 0.8, oy, oz), p2=(pf / 2 + c['boss_face_gap'], oy, oz), r=c['pin7_d'] / 2 + 0.7))
    return plan


T4.case_shapes = case_shapes_v5
T4.motor_pod = motor_pod_v5
T4.case_plan = case_plan_v5


# ------------------------------------------------------------------ new printed parts
def _spur_body(comp, g, z0, face, backlash=None):
    sk = comp.sketches.add(T4.offset_plane(comp, z0))
    T4.polyline(sk, T4.gear_profile(g, backlash))
    return T4.extrude(comp, T4.largest_profile(sk), face, T4.NEW)


def _d_profile(comp, z0, R, flat):
    """A D: circle of radius R with a flat at distance flat from the center (on +x)."""
    sk = comp.sketches.add(T4.offset_plane(comp, z0))
    fy = math.sqrt(R * R - flat * flat)
    pt = lambda x, y: adsk.core.Point3D.create(x / 10.0, y / 10.0, 0)
    arc = sk.sketchCurves.sketchArcs.addByThreePoints(pt(flat, fy), pt(-R, 0), pt(flat, -fy))
    sk.sketchCurves.sketchLines.addByTwoPoints(arc.startSketchPoint, arc.endSketchPoint)
    return sk.profiles.item(0)


def _hex_profile(comp, z0, R):
    sk = comp.sketches.add(T4.offset_plane(comp, z0))
    T4.polyline(sk, [(R * math.cos(math.radians(30 + 60 * k)), R * math.sin(math.radians(30 + 60 * k))) for k in range(6)])
    return T4.largest_profile(sk)


def build_clutch_shaft(root, L):
    """7T 45° helical (as v0.4's motor pinion) + Ø5 shaft through the lid + hex for the 12T + Ø4 journal into the
    clutch plate. Turns on a Ø4 pin in the main half (blind bore, cone end). Local z = -X, origin at X = +3 (the 7T's
    main-half face). Prints standing on that face, shaft up: no overhangs."""
    occ, comp = T4.new_component(root, 'Clutch shaft')
    pf = P['pinion_face']
    T4.helical_body(comp, L['gp'], 0.0, pf)                                                      # 7T X 3..-3
    ri, ro, th = c['thrust_ring']
    T4.extrude(comp, T4.circle_profile(comp, pf - 0.01, ro), th + 0.01, T4.JOIN)                # lid-side thrust ring
    gx0, gx1 = c['gear_x']
    z_hex0 = (pf / 2) - gx1                                                                       # X -8.6
    T4.extrude(comp, T4.circle_profile(comp, pf - 0.3, c['shaft_d'] / 2), z_hex0 - pf + 0.3 + 0.01, T4.JOIN)
    z_j0 = (pf / 2) - c['journal_x'][0]                                                           # X -14.3
    T4.extrude(comp, _d_profile(comp, z_hex0, c['d_r'], c['d_flat']), z_j0 - z_hex0 + 0.01, T4.JOIN)
    z_j1 = (pf / 2) - c['journal_x'][1]
    T4.extrude(comp, T4.circle_profile(comp, z_j0, c['journal_d'] / 2), z_j1 - z_j0, T4.JOIN)
    T4.merge_bodies(comp)
    rb = c['pin7_d'] / 2 + c['pin7_bore_clear']
    T4.extrude(comp, T4.circle_profile(comp, 0.0, rb), c['pin7_depth'], T4.CUT)
    loft = comp.features.loftFeatures.createInput(T4.CUT)          # 45° cone end: prints without a bridge
    loft.loftSections.add(T4.circle_profile(comp, c['pin7_depth'] - 0.01, rb))
    loft.loftSections.add(T4.circle_profile(comp, c['pin7_depth'] + rb - 0.1, 0.1))
    loft.isSolid = True
    loft.participantBodies = T4.own_bodies(comp)
    comp.features.loftFeatures.add(loft)
    comp.bRepBodies.item(0).name = 'Clutch shaft'
    return occ, comp


def build_gear12(root):
    """12T spur with a D-bore (slides over the journal onto the shaft's D-section, stops on its Ø6 shoulder, glued).
    Local z = +X, origin at its motor-side face. Prints flat."""
    occ, comp = T4.new_component(root, 'Clutch 12T')
    _spur_body(comp, spur_c(c['z_out']), 0.0, c['gear_x'][1] - c['gear_x'][0])
    T4.extrude(comp, _d_profile(comp, 0.0, c['d_r'] + c['d_fit'], c['d_flat'] + c['d_fit']), c['face'], T4.CUT)
    comp.bRepBodies.item(0).name = 'Clutch 12T'
    return occ, comp


def build_pinion8(root):
    """9T on the N20's D-flat, with a full-length round hub on the motor side that the arm pivots on (hub radius
    2.75, just over the teeth's root 2.6: prints teeth down with a 0.15 mm step). Local z = +X, origin at the hub's
    motor-side face."""
    occ, comp = T4.new_component(root, 'Clutch pinion')
    hub_len = c['gear_x'][0] - c['pin_hub_x0']
    g = spur_c(c['z_pin'])
    T4.extrude(comp, T4.circle_profile(comp, 0.0, c['pin_hub_d'] / 2), hub_len + 0.01, T4.NEW)
    _spur_body(comp, g, hub_len, c['gear_x'][1] - c['gear_x'][0])
    T4.merge_bodies(comp)
    total = c['gear_x'][1] - c['pin_hub_x0']
    d_start = (c['motor_face_x'] + P['n20_d_start']) - c['pin_hub_x0']
    if d_start > 0:
        T4.extrude(comp, T4.circle_profile(comp, 0.0, P['n20_shaft_d'] / 2 + 0.05), d_start, T4.CUT)
    d_start = max(d_start, 0.0)
    sk = comp.sketches.add(T4.offset_plane(comp, d_start))
    r = P['n20_shaft_d'] / 2 + 0.05
    fx = P['n20_flat'] - P['n20_shaft_d'] / 2 + 0.05
    fy = math.sqrt(r * r - fx * fx)
    pt = lambda x, y: adsk.core.Point3D.create(x / 10.0, y / 10.0, 0)
    arc = sk.sketchCurves.sketchArcs.addByThreePoints(pt(fx, fy), pt(-r, 0), pt(fx, -fy))
    sk.sketchCurves.sketchLines.addByTwoPoints(arc.startSketchPoint, arc.endSketchPoint)
    T4.extrude(comp, sk.profiles.item(0), total - d_start + 0.01, T4.CUT)
    comp.bRepBodies.item(0).name = 'Clutch pinion'
    return occ, comp


def build_idler(root, name):
    """9T idler, bore for the arm's Ø3 pin. Local z = +X, origin at its motor-side face."""
    occ, comp = T4.new_component(root, name)
    _spur_body(comp, spur_c(c['z_idl']), 0.0, c['gear_x'][1] - c['gear_x'][0])
    T4.extrude(comp, T4.circle_profile(comp, 0.0, c['pin_d'] / 2 + c['idler_bore_clear']), c['face'], T4.CUT)
    comp.bRepBodies.item(0).name = name
    return occ, comp


def arm_body(tbm, CL, printed_pins=False):
    """The swing arm in global coordinates at neutral: plate (hub ring with three flexure pads that grip the pinion's
    hub, two lobes out to the idler pins, a tail carrying the stop slot) + the two Ø3 idler pins."""
    B = adsk.fusion.BooleanTypes
    M, A, Bp = CL['M'], CL['A'], CL['B']
    x0, x1 = c['arm_x']
    P3 = lambda y, z, x: adsk.core.Point3D.create(x / 10, y / 10, z / 10)

    def cyl(y, z, r, xa=x0, xb=x1):
        return tbm.createCylinderOrCone(P3(y, z, xa), r / 10, P3(y, z, xb), r / 10)

    def obox(cy, cz, uy, uz, L_, W_, xa=x0, xb=x1):
        obb = adsk.core.OrientedBoundingBox3D.create(P3(cy, cz, (xa + xb) / 2), adsk.core.Vector3D.create(0, uy, uz),
                                                     adsk.core.Vector3D.create(1, 0, 0), L_ / 10, (xb - xa) / 10, W_ / 10)
        return tbm.createBox(obb)

    def U(a, *bs):
        for b in bs:
            tbm.booleanOperation(a, b, B.UnionBooleanType)
        return a

    def D(a, *bs):
        for b in bs:
            tbm.booleanOperation(a, b, B.DifferenceBooleanType)
        return a

    def I(a, b):
        tbm.booleanOperation(a, b, B.IntersectionBooleanType)
        return a

    def wedge(a0, a1, r, xa=x0, xb=x1):
        """Sector of radius r round M between angles a0..a1 (deg, from +Y toward +Z), as disk minus two half-planes."""
        w = cyl(M[0], M[1], r, xa, xb)
        for ang, sgn in ((a0, -1), (a1, 1)):
            t = math.radians(ang)
            nx, nz = -math.sin(t) * sgn, math.cos(t) * sgn       # outward normal of the edge
            cx, cz = M[0] + nx * 2 * r, M[1] + nz * 2 * r
            D(w, obox(cx, cz, nx, nz, 4 * r, 4 * r, xa - 1, xb + 1))
        return w

    arm = cyl(M[0], M[1], c['arm_hub_r'])
    for p in (A, Bp):                                            # lobes to the idler pins
        dy, dz = p[0] - M[0], p[1] - M[1]
        Ln = math.hypot(dy, dz)
        U(arm, obox((M[0] + p[0]) / 2, (M[1] + p[1]) / 2, dy / Ln, dz / Ln, Ln, c['lobe_w']), cyl(p[0], p[1], c['lobe_w'] / 2))
    s0, s1 = c['tail_span']
    tail_r = c['stop_r'] + c['stop_d'] / 2 + c['stop_clear'] + c['slot_wall']
    U(arm, wedge(s0, s1, tail_r))
    # stop slot: arc round M at stop_r; the post's center may travel +-swing_stop from the neutral position
    sr = c['stop_d'] / 2 + c['stop_clear']
    sw = math.degrees(CL['swing'] - c['stop_clear'] / c['stop_r'])   # end disks are post + clearance: stop at the mesh
    sd = c['stop_dir']
    slot = D(I(cyl(M[0], M[1], c['stop_r'] + sr, x0 - 1, x1 + 1), wedge(sd - sw, sd + sw, c['stop_r'] + sr + 1, x0 - 1, x1 + 1)),
             cyl(M[0], M[1], c['stop_r'] - sr, x0 - 2, x1 + 2))
    for ang in (sd - sw, sd + sw):
        t = math.radians(ang)
        U(slot, cyl(M[0] + c['stop_r'] * math.cos(t), M[1] + c['stop_r'] * math.sin(t), sr, x0 - 1, x1 + 1))
    D(arm, slot)
    # hub bore with two soft cantilever fingers: each is a 0.8 mm arc between the bore and a 0.8 mm slot, fixed at its
    # root, free at its end, with a bump that presses 0.3 mm into the pinion's hub (about 0.5 N, ~1 N.mm of drag in all)
    rb = c['pin_hub_d'] / 2 + c['arm_bore_clear']
    D(arm, cyl(M[0], M[1], rb, x0 - 1, x1 + 1))
    ft, fs = c['finger_t'], c['finger_slot']
    for root_a in c['finger_roots']:
        free_a = root_a + c['finger_span']
        ring = D(cyl(M[0], M[1], rb + ft + fs, x0 - 1, x1 + 1), cyl(M[0], M[1], rb + ft, x0 - 2, x1 + 2))
        D(arm, I(ring, wedge(root_a, free_a, rb + ft + fs + 1, x0 - 1, x1 + 1)))            # slot behind the finger
        gap_deg = math.degrees(fs / (rb + ft / 2))
        D(arm, I(D(cyl(M[0], M[1], rb + ft + fs, x0 - 1, x1 + 1), cyl(M[0], M[1], rb - 0.5, x0 - 2, x1 + 2)),
                 wedge(free_a, free_a + gap_deg, rb + ft + fs + 1, x0 - 1, x1 + 1)))            # free end cut
        t = math.radians(free_a - 8.0)
        rr = c['pin_hub_d'] / 2 - c['finger_interf'] + c['finger_bump_r']
        U(arm, cyl(M[0] + rr * math.cos(t), M[1] + rr * math.sin(t), c['finger_bump_r']))
    # idler pins (printed with the arm: the arm prints flat on its motor-side face, pins standing up)
    for p in (A, Bp):
        U(arm, cyl(p[0], p[1], c['pin_boss_d'] / 2, x1 - 0.01, c['pin_boss_x']))       # boss: the idler rides on it
        if printed_pins:                                                               # bench-test variant
            U(arm, cyl(p[0], p[1], c['pin_d'] / 2, x1 - 0.01, c['pin_tip_x']))
        else:                                                                          # Ø3 x 8 steel dowels press in
            D(arm, cyl(p[0], p[1], c['pin_d'] / 2 - c['pin_press'], x0 - 1, c['pin_boss_x'] + 1))
    return arm


def plate_body(tbm, CL):
    """Clutch plate: the N20's gearbox nose sits in its square pocket, the clutch shaft's journal in its bore, so the
    motor-to-12T distance is set by this one printed part; carries the arm's stop post. Clamped between the gearbox face
    and the pinion's hub."""
    B = adsk.fusion.BooleanTypes
    M, O = CL['M'], CL['O']
    x0, x1 = c['plate_x']
    P3 = lambda y, z, x: adsk.core.Point3D.create(x / 10, y / 10, z / 10)
    cyl = lambda y, z, r, xa=x0, xb=x1: tbm.createCylinderOrCone(P3(y, z, xa), r / 10, P3(y, z, xb), r / 10)

    def box(cy, cz, uy, uz, L_, W_, xa=x0, xb=x1):
        return tbm.createBox(adsk.core.OrientedBoundingBox3D.create(P3(cy, cz, (xa + xb) / 2), adsk.core.Vector3D.create(0, uy, uz),
                                                                    adsk.core.Vector3D.create(1, 0, 0), L_ / 10, (xb - xa) / 10, W_ / 10))

    def U(a, *bs):
        for b in bs:
            tbm.booleanOperation(a, b, B.UnionBooleanType)
        return a

    def D(a, *bs):
        for b in bs:
            tbm.booleanOperation(a, b, B.DifferenceBooleanType)
        return a
    gw, gh = P['n20_w'] + 2 * c['plate_fit'], P['n20_h'] + 2 * c['plate_fit']
    w = c['plate_wall']
    t = math.radians(c['stop_dir'])
    S = (M[0] + c['stop_r'] * math.cos(t), M[1] + c['stop_r'] * math.sin(t))
    plate = box(M[0], M[1], 1, 0, gw + 2 * w, gh + 2 * w)
    for q, rq in ((O, c['journal_d'] / 2 + 1.8), (S, c['stop_d'] / 2 + 1.2)):
        dy, dz = q[0] - M[0], q[1] - M[1]
        Ln = math.hypot(dy, dz)
        U(plate, box((M[0] + q[0]) / 2, (M[1] + q[1]) / 2, dy / Ln, dz / Ln, Ln, 2 * rq), cyl(q[0], q[1], rq))
    D(plate, box(M[0], M[1], 1, 0, gw, gh, x0 - 1, x0 + c['plate_pocket']))                # gearbox pocket
    D(plate, cyl(M[0], M[1], c['pin_hub_d'] / 2 + c['plate_hub_clear'], x0 - 1, x1 + 1))     # runs on the pinion's hub
    rj = c['journal_d'] / 2 + c['journal_clear']
    D(plate, cyl(O[0], O[1], rj, x0 - 1, x1 + 1),
      tbm.createCylinderOrCone(P3(O[0], O[1], x1 - 0.5), rj / 10, P3(O[0], O[1], x1 + 0.01), (rj + 0.5) / 10))  # lead-in
    U(plate, cyl(S[0], S[1], c['stop_d'] / 2, x1 - 0.01, c['stop_tip_x']))                  # stop post
    for (ay, az), ar in c['avoid']:
        D(plate, cyl(ay, az, ar, x0 - 1, x1 + 1))
    return plate


def build_plate(root, CL):
    tbm = adsk.fusion.TemporaryBRepManager.get()
    occ, comp = T4.new_component(root, 'Clutch plate')
    T4.add_bodies(comp, [('Clutch plate', plate_body(tbm, CL))])
    return occ, comp


def build_arm(root, CL, printed_pins=False):
    tbm = adsk.fusion.TemporaryBRepManager.get()
    occ, comp = T4.new_component(root, 'Clutch arm printed pins' if printed_pins else 'Clutch arm')
    T4.add_bodies(comp, [('Clutch arm printed pins' if printed_pins else 'Clutch arm', arm_body(tbm, CL, printed_pins))])
    return occ, comp


def build_pins_ref(root, CL):
    """The two Ø3 x 8 steel dowels (reference bodies, checked like parts)."""
    tbm = adsk.fusion.TemporaryBRepManager.get()
    occ, comp = T4.new_component(root, 'Idler pins (steel)')
    x0 = c['arm_x'][0]
    P3 = lambda y, z, x: adsk.core.Point3D.create(x / 10, y / 10, z / 10)
    bodies = []
    for nm, p in (('Pin A', CL['A']), ('Pin B', CL['B'])):
        bodies.append((nm, tbm.createCylinderOrCone(P3(p[0], p[1], x0 + 0.05), c['pin_d'] / 20, P3(p[0], p[1], x0 + 0.05 + 8.0), c['pin_d'] / 20)))
    T4.add_bodies(comp, bodies)
    return occ, comp


def build_refs_v5(root, L, mo_len, CL):
    """v0.4's reference bodies (rod, rail, N20 ...) with the N20 moved to the clutch's motor axis."""
    M = CL['M']
    face = (c['motor_face_x'], M[0], M[1])
    L2 = dict(L, face=face, pin_c=(c['motor_face_x'] + P['n20_shaft_len'], M[0], M[1]), t_face=P['n20_shaft_len'])
    return T4.build_refs(root, L2, mo_len)


# ------------------------------------------------------------------ build
def clutch_phases(CL):
    """Tooth phases (deg, local x of each gear from +Y toward +Z) so the pinion meshes both idlers: a pinion tooth on
    the line to idler A, a space of A on the same line; B's phase follows the pinion tooth nearest its line."""
    M, zp, zi = CL['M'], c['z_pin'], c['z_idl']
    ang = lambda p: math.degrees(math.atan2(p[1] - M[1], p[0] - M[0]))
    fa, fb = ang(CL['A']), ang(CL['B'])
    pitch_p = 360.0 / zp
    delta = ((fa - fb) + pitch_p / 2) % pitch_p - pitch_p / 2          # nearest pinion tooth to B's line, from that line
    return dict(pinion=fa, A=fa + 180.0 + 180.0 / zi, B=fb + 180.0 + 180.0 / zi - delta * zp / zi)


def build(design, export_dir=None):
    root = design.rootComponent
    L = T4.layout()
    CL = clutch_layout()
    _, worm = T4.build_worm(root, L)
    _, wheel = T4.build_wheel(root, L)
    cases, bosses, mo_len, pegs = T4.build_case(root, L)
    _, sgear = T4.build_sensor_gear(root)
    _, refs = build_refs_v5(root, L, mo_len, CL)
    _, shaft = build_clutch_shaft(root, L)
    _, g12 = build_gear12(root)
    _, pin8 = build_pinion8(root)
    _, idA = build_idler(root, 'Idler A')
    _, idB = build_idler(root, 'Idler B')
    _, arm = build_arm(root, CL)
    _, arm_pp = build_arm(root, CL, printed_pins=True)
    arm_pp_occ = next(root.occurrences.item(i) for i in range(root.occurrences.count)
                      if root.occurrences.item(i).component.name == PREFIX + 'Clutch arm printed pins')
    mv = adsk.core.Matrix3D.create()                     # bench-test variant: set beside the tilter (not in the checks)
    mv.translation = adsk.core.Vector3D.create(0, -8.0, 0)
    arm_pp_occ.transform2 = mv
    _, pins = build_pins_ref(root, CL)
    _, plate = build_plate(root, CL)
    SL = T4.sensor_layout()

    def occ_named(name):
        return next(root.occurrences.item(i) for i in range(root.occurrences.count)
                    if root.occurrences.item(i).component.name == PREFIX + name)
    X, d = L['X'], L['d']
    T4.place(occ_named('Worm'), L['p0'], X, d)
    T4.place(occ_named('Worm wheel'), L['rod_c'], L['n'], X)
    pc = L['pin_c']
    T4.place(occ_named('Clutch shaft'), (P['pinion_face'] / 2, pc[1], pc[2]), L['w'], (-1, 0, 0))
    T4.place(occ_named('Clutch 12T'), (c['gear_x'][0], pc[1], pc[2]), (0, 1, 0), (1, 0, 0))
    M = CL['M']
    ph = clutch_phases(CL)
    xa = lambda deg: (0, math.cos(math.radians(deg)), math.sin(math.radians(deg)))
    T4.place(occ_named('Clutch pinion'), (c['pin_hub_x0'], M[0], M[1]), xa(ph['pinion']), (1, 0, 0))
    for nm, p, k in (('Idler A', CL['A'], 'A'), ('Idler B', CL['B'], 'B')):
        T4.place(occ_named(nm), (c['gear_x'][0], p[0], p[1]), xa(ph[k]), (1, 0, 0))
    # sensor gear phase (as v0.4)
    v = T4.sub((0, SL['y'], SL['z']), L['rod_c'])
    line_w = math.atan2(T4.dot(v, L['d']), T4.dot(v, L['n']))
    pw = 2 * math.pi / P['z_wheel']
    dw = (T4.wheel_tooth_angle((SL['gear_x0'] + SL['gear_x1']) / 2) - line_w + pw / 2) % pw - pw / 2
    beta = math.atan2(v[2], -v[1])
    gs = SL['gs']
    rho = beta + dw * P['z_wheel'] / P['ss_z'] + math.pi / P['ss_z'] - P['ss_hand'] * (P['ss_face'] / 2) * math.tan(gs['beta']) / gs['rp'] \
        + math.radians(P['ss_phase_trim'])
    T4.place(occ_named('Sensor gear'), (SL['gear_x0'], SL['y'], SL['z']), T4.rotate_about((0, 1, 0), (-1, 0, 0), rho), (-1, 0, 0))

    for comp in (worm, shaft):
        T4.color(design, comp, 'Plastic - Glossy (Yellow)')
    for comp in (wheel, sgear, idA, idB, g12):
        T4.color(design, comp, 'Plastic - Glossy (Green)')
    T4.color(design, pin8, 'Plastic - Glossy (Blue)')
    T4.color(design, arm, 'Plastic - Matte (Black)')
    T4.color(design, plate, 'Plastic - Matte (White)')
    T4.color(design, cases['Case left'][1], 'Plastic - Translucent Matte (Blue)')
    T4.color(design, cases['Case right'][1], 'Plastic - Matte (Blue)')
    T4.color(design, refs, 'Plastic - Matte (White)')

    files = []
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        em = design.exportManager
        for nm, comp in (('worm', worm), ('worm_wheel', wheel), ('sensor_gear', sgear), ('clutch_shaft', shaft), ('clutch_12t', g12),
                         ('clutch_pinion', pin8), ('clutch_idler', idA), ('clutch_arm', arm), ('clutch_arm_printed_pins', arm_pp), ('clutch_plate', plate),
                         ('case_left', cases['Case left'][1]), ('case_right', cases['Case right'][1])):
            path = os.path.join(export_dir, nm + '.stl')
            opt = em.createSTLExportOptions(comp, path)
            opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
            em.execute(opt)
            files.append(path)
    arm_pp_occ.deleteMe()                                # the printed-pin arm is a print file only, not part of the assembly
    return dict(CL={k: (tuple(round(x, 3) for x in v) if isinstance(v, tuple) else (round(v, 4) if isinstance(v, float) else None))
                    for k, v in CL.items() if k in ('O', 'M', 'A', 'B', 'A_on', 'B_on', 'A_far', 'B_far', 'a', 'b', 'd', 'neu', 'swing', 'base', 'phi', 'psi')},
                bosses=bosses, pegs=pegs, files=files)


if __name__ == '__main__':
    pass
