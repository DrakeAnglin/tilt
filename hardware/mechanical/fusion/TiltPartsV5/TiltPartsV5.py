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
    m=0.8, z_pin=8, z_idl=9, z_out=12,      # module 0.8, 25 deg (P['pressure']), the same tooth size class as the 7T
    face=6.0,                                # all clutch gears 6 wide
    cd_extra=0.1,                            # added to every clutch center distance (printed teeth)
    out_gap=0.6,                             # pinion tips to the 12T's tips (they never mesh)
    neutral_gap=0.5,                         # idler tips to the 12T's tips with the arm in the middle (printed-gear wobble)
    theta=335.0,                             # direction of the motor axis from the 12T's axis (deg, from +Z toward +Y)
    motor_face_x=-18.53,                     # N20 gearbox face (the module holds the motor)
    gear_x=(-15.63, -9.63),                  # clutch gear plane (lid face -8.33: idlers can't slide off their pins)
    arm_x=(-18.23, -15.83),                  # arm plate, on the motor side of the gears
    pin_hub_d=6.4, pin_hub_x0=-18.33,        # pinion hub (round shaft section), the arm pivots on it
    arm_bore_clear=0.15, pad_interf=0.15, pad_n=3, pad_r=0.4, pad_slot=(0.6, 0.4), pad_span=56.0,
    arm_hub_r=5.0, lobe_w=4.6, pin_d=3.0, pin_tip_x=-8.73, idler_bore_clear=0.15,
    stop_dir=70.0, stop_r=7.2, stop_d=3.0, stop_clear=0.15, slot_wall=1.2, stop_post_x=(-18.53, -15.95),
    tail_span=(34.0, 104.0),                 # the arm's tail (with the stop slot): clear of bolt C and the rod tube
    shaft_d=5.0, shaft_bore_clear=0.2,
    pin7_d=4.0, pin7_x=(4.1, 0.0), pin7_bore_clear=0.15, pin7_depth=3.4,   # 7T turns on a Ø4 pin grown in the main half
    hex_r=2.7, hex_fit=0.0,                  # 12T pressed onto a hex on the shaft's end (circumradius)
    cone_len=1.05,                           # pinion: 45° cone from its neck up to the hub (prints teeth down)
)
c = C


def spur_c(z):
    return T4.spur(z, c['m'])


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
    return plan


T4.case_shapes = case_shapes_v5
T4.motor_pod = motor_pod_v5
T4.case_plan = case_plan_v5


# ------------------------------------------------------------------ new printed parts
def _spur_body(comp, g, z0, face, backlash=None):
    sk = comp.sketches.add(T4.offset_plane(comp, z0))
    T4.polyline(sk, T4.gear_profile(g, backlash))
    return T4.extrude(comp, T4.largest_profile(sk), face, T4.NEW)


def _hex_profile(comp, z0, R):
    sk = comp.sketches.add(T4.offset_plane(comp, z0))
    T4.polyline(sk, [(R * math.cos(math.radians(30 + 60 * k)), R * math.sin(math.radians(30 + 60 * k))) for k in range(6)])
    return T4.largest_profile(sk)


def build_clutch_shaft(root, L):
    """7T 45° helical (as v0.4's motor pinion) + Ø5 shaft through the lid + hex end for the 12T. Turns on a Ø4 pin in the
    main half (blind bore in the 7T). Local z = -X, origin at X = +3 (the 7T's main-half face). Prints standing on that
    face (bore open on the bed), shaft up: no overhangs."""
    occ, comp = T4.new_component(root, 'Clutch shaft')
    pf = P['pinion_face']
    T4.helical_body(comp, L['gp'], 0.0, pf)                                                      # 7T X 3..-3
    gx0, gx1 = c['gear_x']
    z_hex0 = (pf / 2) - gx1                                                                       # X -9.63
    T4.extrude(comp, T4.circle_profile(comp, pf - 0.3, c['shaft_d'] / 2), z_hex0 - pf + 0.3 + 0.01, T4.JOIN)
    T4.extrude(comp, _hex_profile(comp, z_hex0, c['hex_r']), (gx1 - gx0) - 0.1, T4.JOIN)         # hex to 0.1 inside the 12T
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
    """12T spur with a hex bore (pressed onto the shaft's end). Local z = +X, origin at its motor-side face. Prints flat."""
    occ, comp = T4.new_component(root, 'Clutch 12T')
    _spur_body(comp, spur_c(c['z_out']), 0.0, c['gear_x'][1] - c['gear_x'][0])
    T4.extrude(comp, _hex_profile(comp, 0.0, c['hex_r'] + c['hex_fit']), c['face'], T4.CUT)
    comp.bRepBodies.item(0).name = 'Clutch 12T'
    return occ, comp


def build_pinion8(root):
    """8T on the N20's D-flat, with a round hub on the motor side that the arm pivots on. Local z = +X, origin at the
    hub's motor-side face."""
    occ, comp = T4.new_component(root, 'Clutch pinion')
    hub_len = c['gear_x'][0] - c['pin_hub_x0']
    g8 = spur_c(c['z_pin'])
    r_neck = g8['rf'] - 0.05
    cone_z0 = hub_len - (c['pin_hub_d'] / 2 - r_neck)          # 45° cone from the hub down to the neck at the teeth
    T4.extrude(comp, T4.circle_profile(comp, 0.0, c['pin_hub_d'] / 2), cone_z0 + 0.01, T4.NEW)
    loft = comp.features.loftFeatures.createInput(T4.JOIN)
    loft.loftSections.add(T4.circle_profile(comp, cone_z0, c['pin_hub_d'] / 2))
    loft.loftSections.add(T4.circle_profile(comp, hub_len + 0.01, r_neck))
    loft.isSolid = True
    loft.participantBodies = T4.own_bodies(comp)
    comp.features.loftFeatures.add(loft)
    _spur_body(comp, g8, hub_len, c['gear_x'][1] - c['gear_x'][0])
    T4.merge_bodies(comp)
    # bore: round over the shaft's round section, D over its flat (the flat starts 3.2 from the gearbox face)
    total = c['gear_x'][1] - c['pin_hub_x0']
    d_start = (c['motor_face_x'] + P['n20_d_start']) - c['pin_hub_x0']
    T4.extrude(comp, T4.circle_profile(comp, 0.0, P['n20_shaft_d'] / 2 + 0.05), d_start, T4.CUT)
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


def arm_body(tbm, CL):
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
    # hub bore with three flexure pads (a tongue between the bore and a slot behind it, a bump on the tongue)
    rb = c['pin_hub_d'] / 2 + c['arm_bore_clear']
    D(arm, cyl(M[0], M[1], rb, x0 - 1, x1 + 1))
    tt, sw_ = c['pad_slot']
    for k in range(c['pad_n']):
        a_mid = 90.0 + k * 360.0 / c['pad_n']
        ring = D(cyl(M[0], M[1], rb + tt + sw_, x0 - 1, x1 + 1), cyl(M[0], M[1], rb + tt, x0 - 2, x1 + 2))
        D(arm, I(ring, wedge(a_mid - c['pad_span'] / 2, a_mid + c['pad_span'] / 2, rb + tt + sw_ + 1, x0 - 1, x1 + 1)))
        t = math.radians(a_mid)
        rr = c['pin_hub_d'] / 2 - c['pad_interf'] + c['pad_r']
        U(arm, cyl(M[0] + rr * math.cos(t), M[1] + rr * math.sin(t), c['pad_r']))
    # idler pins (printed with the arm: the arm prints flat on its motor-side face, pins standing up)
    for p in (A, Bp):
        U(arm, cyl(p[0], p[1], c['pin_d'] / 2, x1 - 0.01, c['pin_tip_x']))
    return arm


def build_arm(root, CL):
    tbm = adsk.fusion.TemporaryBRepManager.get()
    occ, comp = T4.new_component(root, 'Clutch arm')
    T4.add_bodies(comp, [('Clutch arm', arm_body(tbm, CL))])
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
    T4.color(design, cases['Case left'][1], 'Plastic - Translucent Matte (Blue)')
    T4.color(design, cases['Case right'][1], 'Plastic - Matte (Blue)')
    T4.color(design, refs, 'Plastic - Matte (White)')

    files = []
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        em = design.exportManager
        for nm, comp in (('worm', worm), ('worm_wheel', wheel), ('sensor_gear', sgear), ('clutch_shaft', shaft), ('clutch_12t', g12),
                         ('clutch_pinion', pin8), ('clutch_idler', idA), ('clutch_arm', arm),
                         ('case_left', cases['Case left'][1]), ('case_right', cases['Case right'][1])):
            path = os.path.join(export_dir, nm + '.stl')
            opt = em.createSTLExportOptions(comp, path)
            opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
            em.execute(opt)
            files.append(path)
    return dict(CL={k: (tuple(round(x, 3) for x in v) if isinstance(v, tuple) else (round(v, 4) if isinstance(v, float) else None))
                    for k, v in CL.items() if k in ('O', 'M', 'A', 'B', 'A_on', 'B_on', 'A_far', 'B_far', 'a', 'b', 'd', 'neu', 'swing', 'base', 'phi', 'psi')},
                bosses=bosses, pegs=pegs, files=files)


if __name__ == '__main__':
    pass
