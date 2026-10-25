"""TiltLayout: layout/fit study for the motorized tilter (Fusion 360 script).

Builds reference bodies for the headrail end pocket, the factory worm + worm wheel, and the motor drive: a
crossed-axis (90°, 45° helix) helical gear pair. The driven gear is part of a NEW printed wand connector that grips the
worm's 8-ridge spline (the worm itself is unmodified); the pinion is on an N20 gear motor lying parallel to the tilt rod. Crossed helicals at 45° are not self-locking, so
the wand still back-drives the motor, and their axes don't intersect, so no shaft passes through the other gear.

All sizes are Fusion User Parameters prefixed "tl_". Edit them in Modify > Change Parameters, then run the
script again: it deletes and rebuilds its own "TL ..." components in the active design. The bodies are
non-parametric base features. They are reference geometry to design the printed housing around.

Coordinates (mm): X along the tilt rod (0 = tilter mid-plane, +X toward the first tilt drum),
Y across the rail (0 = rail center, -Y = room side where the wand hangs), Z up (0 = inner floor of the rail).
"""

import math
import traceback

import adsk.core
import adsk.fusion

PREFIX = 'TL '

# name: (default, unit, comment)
PARAMS = {
    # Headrail
    'tl_rail_w':        (55.5, 'mm', 'Rail inner width'),
    'tl_rail_h':        (36.5, 'mm', 'Rail inner height (floor to top of lips)'),
    'tl_rail_wall':     (2.0, 'mm', 'Rail wall thickness'),
    'tl_pocket_len':    (110.0, 'mm', 'End cap to first tilt drum cradle'),
    'tl_tilter_x':      (12.0, 'mm', 'End cap to tilter mid-plane'),
    'tl_frame_gap':     (6.5, 'mm', 'Rail top to window frame when installed'),
    # Tilt rod
    'tl_rod_z':         (24.0, 'mm', 'Rod axis height above inner floor'),
    'tl_rod_size':      (4.0, 'mm', 'Square rod size'),
    # Worm wheel (factory)
    'tl_wheel_od':      (15.8, 'mm', 'Worm wheel outside diameter (16 teeth)'),
    'tl_wheel_face':    (7.5, 'mm', 'Worm wheel tooth face width'),
    'tl_wheel_hub_len': (16.66, 'mm', 'Worm wheel barrel length along rod'),
    'tl_wheel_hub_d':   (12.5, 'mm', 'Worm wheel barrel diameter (measured)'),
    'tl_module':        (0.88, 'mm', 'Worm/wheel module (derived)'),
    # Worm (factory), sections listed top (gear end) to bottom (wand end)
    'tl_worm_angle':    (56.0, 'deg', 'Worm axis slope from horizontal, down toward the room'),
    'tl_worm_od':       (11.0, 'mm', 'Worm thread OD'),
    'tl_worm_thread':   (9.0, 'mm', 'Threaded length'),
    'tl_worm_pin_d':    (5.0, 'mm', 'Upper journal pin diameter'),
    'tl_worm_pin_len':  (2.5, 'mm', 'Upper journal pin length'),
    'tl_worm_gap':      (2.5, 'mm', 'Threads to upper flange'),
    'tl_worm_shaft_d':  (5.6, 'mm', 'Shaft diameter'),
    'tl_flange_d':      (9.5, 'mm', 'Flange diameter (both)'),
    'tl_flange1_t':     (1.6, 'mm', 'Upper flange thickness'),
    'tl_flange_gap':    (8.4, 'mm', 'Between flanges'),
    'tl_flange2_t':     (1.77, 'mm', 'Lower flange thickness'),
    'tl_spline_d':      (6.0, 'mm', 'Spline OD (8 ridges)'),
    'tl_spline_len':    (5.0, 'mm', 'Spline length'),
    # Printed wand connector: grips the worm's 8-ridge spline, carries the helical gear and the wand loop
    'tl_conn_d':        (8.13, 'mm', 'Connector body OD (factory size)'),
    'tl_conn_depth':    (5.3, 'mm', 'Connector socket depth on the spline'),
    'tl_conn_len':      (26.0, 'mm', 'Connector + loop length'),
    'tl_conn_gap':      (0.2, 'mm', 'Lower flange to connector mouth'),
    # Crossed helical drive (45° helix, 90° shafts)
    'tl_hg_d':          (11.314, 'mm', 'Helical gear pitch diameter (connector, 8T, mn 1.0)'),
    'tl_hp_d':          (9.899, 'mm', 'Helical pinion pitch diameter (N20, 7T, mn 1.0)'),
    'tl_h_mn':          (0.85, 'mm', 'Addendum of the helical pair (0.85 x module 1.0)'),
    'tl_hg_face':       (4.0, 'mm', 'Helical gear face width'),
    'tl_hp_face':       (5.0, 'mm', 'Helical pinion face width'),
    'tl_gear_s':        (20.97, 'mm', 'Gear center along worm axis from thread center (spline 18.77-23.77)'),
    'tl_motor_rot':     (0.0, 'deg', 'Motor axis rotation about the worm axis (0 = parallel to rod)'),
    # N20 gear motor
    'tl_n20_w':         (12.0, 'mm', 'N20 width'),
    'tl_n20_h':         (10.0, 'mm', 'N20 height (across flats)'),
    'tl_n20_gbx_len':   (9.0, 'mm', 'Gearbox length (longer for high ratios)'),
    'tl_n20_mot_len':   (15.0, 'mm', 'Motor can length'),
    'tl_n20_enc_len':   (8.0, 'mm', 'Encoder + cap length'),
    'tl_n20_shaft_d':   (3.0, 'mm', 'Output shaft diameter'),
    'tl_pinion_gap':    (4.0, 'mm', 'Pinion face to gearbox face'),
}


# ---------- small vector helpers (mm) ----------
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def unit(a):
    n = math.sqrt(dot(a, a))
    return mul(a, 1.0 / n)


def pt(p):  # mm tuple -> Fusion Point3D (cm)
    return adsk.core.Point3D.create(p[0] / 10.0, p[1] / 10.0, p[2] / 10.0)


def vec(v):
    return adsk.core.Vector3D.create(v[0], v[1], v[2])


class Builder:
    def __init__(self, design):
        self.design = design
        self.root = design.rootComponent
        self.tbm = adsk.fusion.TemporaryBRepManager.get()
        app = adsk.core.Application.get()
        libs = [app.materialLibraries.item(i) for i in range(app.materialLibraries.count)]
        self.lib = next((l for l in libs if l.name == 'Fusion Appearance Library'), None)

    def appearance(self, name):
        if not name or self.lib is None:
            return None
        a = self.design.appearances.itemByName(name)
        if a is None:
            src = self.lib.appearances.itemByName(name)
            if src is None:
                return None
            a = self.design.appearances.addByCopy(src, name)
        return a

    def cyl(self, p1, r1, p2, r2=None):
        return self.tbm.createCylinderOrCone(pt(p1), r1 / 10.0, pt(p2), (r1 if r2 is None else r2) / 10.0)

    def box(self, center, ldir, wdir, length, width, height):
        obb = adsk.core.OrientedBoundingBox3D.create(pt(center), vec(ldir), vec(wdir),
                                                     length / 10.0, width / 10.0, height / 10.0)
        return self.tbm.createBox(obb)

    def union(self, bodies):
        target = bodies[0]
        for b in bodies[1:]:
            self.tbm.booleanOperation(target, b, adsk.fusion.BooleanTypes.UnionBooleanType)
        return target

    def component(self, name, bodies, opacity=1.0, look=None):
        # Assemblies get one component per group. Single-component "Part" documents can't hold more
        # components, so there the bodies go into the root, prefixed with the group name.
        try:
            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = PREFIX + name
            body_prefix = ''
        except RuntimeError:
            occ = None
            comp = self.root
            body_prefix = PREFIX + name + ': '
        base = comp.features.baseFeatures.add()
        base.name = PREFIX + name
        base.startEdit()
        for body_name, body in bodies:
            b = comp.bRepBodies.add(body, base)
            b.name = body_prefix + body_name
            a = self.appearance(look)
            if a is not None:
                b.appearance = a
            try:
                b.opacity = opacity
            except Exception:
                pass
        base.finishEdit()
        return occ


def get_params(design):
    """Create missing tl_ parameters, then return all values in mm / degrees / plain numbers."""
    ups = design.userParameters
    um = design.unitsManager
    vals = {}
    for name, (default, unit, comment) in PARAMS.items():
        p = ups.itemByName(name)
        if p is None:
            expr = '{} {}'.format(default, unit) if unit else str(default)
            p = ups.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)
        if unit == 'mm':
            vals[name] = um.convert(p.value, um.internalUnits, 'mm')
        elif unit == 'deg':
            vals[name] = math.degrees(p.value)
        else:
            vals[name] = p.value
    return vals


def remove_old(design):
    root = design.rootComponent
    occs = root.occurrences
    for i in range(occs.count - 1, -1, -1):
        if occs.item(i).component.name.startswith(PREFIX):
            occs.item(i).deleteMe()
    bases = root.features.baseFeatures
    for i in range(bases.count - 1, -1, -1):
        if bases.item(i).name.startswith(PREFIX):
            bases.item(i).deleteMe()


def build(design):
    P = get_params(design)
    B = Builder(design)
    X = (1.0, 0.0, 0.0)
    Y = (0.0, 1.0, 0.0)
    Z = (0.0, 0.0, 1.0)

    # --- Headrail end pocket ---
    w, h, t = P['tl_rail_w'], P['tl_rail_h'], P['tl_rail_wall']
    x0 = -P['tl_tilter_x']
    x1 = x0 + P['tl_pocket_len']
    xm, L = (x0 + x1) / 2.0, x1 - x0
    rail = B.union([
        B.box((xm, 0, -t / 2), X, Y, L, w + 2 * t, t),                    # floor
        B.box((xm, -(w + t) / 2, h / 2 - t / 2), X, Y, L, t, h + t),      # room-side wall
        B.box((xm, (w + t) / 2, h / 2 - t / 2), X, Y, L, t, h + t),       # wall side
    ])
    endcap = B.box((x0 - t / 2, 0, h / 2 - t / 2), X, Y, t, w + 2 * t, h + t)
    frame = B.box((xm, 0, h + P['tl_frame_gap'] + 0.5), X, Y, L, w + 2 * t, 1.0)
    B.component('Headrail', [('Rail', rail), ('End cap', endcap), ('Window frame limit', frame)], 0.25,
                'Plastic - Matte (Gray)')

    # --- Tilt rod + worm wheel ---
    rod_c = (0.0, 0.0, P['tl_rod_z'])
    rod = B.box((xm, 0, P['tl_rod_z']), X, Y, L, P['tl_rod_size'], P['tl_rod_size'])
    hw = P['tl_wheel_hub_len'] / 2.0
    wheel = B.union([
        B.cyl(add(rod_c, (-P['tl_wheel_face'] / 2, 0, 0)), P['tl_wheel_od'] / 2,
              add(rod_c, (P['tl_wheel_face'] / 2, 0, 0))),
        B.cyl(add(rod_c, (-hw, 0, 0)), P['tl_wheel_hub_d'] / 2, add(rod_c, (hw, 0, 0))),
    ])
    B.component('Rod and worm wheel', [('Tilt rod', rod), ('Worm wheel (factory)', wheel)], 1.0,
                'Plastic - Matte (White)')

    # --- Worm (factory) ---
    a = math.radians(P['tl_worm_angle'])
    m = P['tl_module']
    d = (0.0, -math.cos(a), -math.sin(a))        # worm axis, pointing down toward the wand
    n = (0.0, -math.sin(a), math.cos(a))         # from rod axis toward worm axis
    cd = ((P['tl_worm_od'] - 2 * m) + (P['tl_wheel_od'] - 2 * m)) / 2.0
    p0 = add(rod_c, mul(n, cd))                  # thread center

    def S(s):
        return add(p0, mul(d, s))

    sections = []
    bounds = []
    s = -P['tl_worm_thread'] / 2 - P['tl_worm_pin_len']
    thread_start = s + P['tl_worm_pin_len']
    for dia, length in ((P['tl_worm_pin_d'], P['tl_worm_pin_len']),
                        (P['tl_worm_od'] - 4.5 * P['tl_module'], P['tl_worm_thread']),   # root cylinder
                        (P['tl_worm_shaft_d'], P['tl_worm_gap']),
                        (P['tl_flange_d'], P['tl_flange1_t']),
                        (P['tl_worm_shaft_d'], P['tl_flange_gap']),
                        (P['tl_flange_d'], P['tl_flange2_t']),
                        (P['tl_spline_d'], P['tl_spline_len'])):
        sections.append(B.cyl(S(s), dia / 2, S(s + length)))
        s += length
        bounds.append(s)
    flange1_end, flange2_start = bounds[3], bounds[4]
    # thread crests drawn as rings at the axial pitch (visual only; a single-start helix in reality)
    pitch = math.pi * P['tl_module']
    crest_w = 0.4 * pitch
    c = thread_start + pitch / 2
    while c + crest_w / 2 <= thread_start + P['tl_worm_thread']:
        sections.append(B.cyl(S(c - crest_w / 2), P['tl_worm_od'] / 2, S(c + crest_w / 2)))
        c += pitch
    worm_end = s
    worm_top = S(-P['tl_worm_thread'] / 2 - P['tl_worm_pin_len'])
    B.component('Worm (factory)', [('Worm', B.union(sections))], 1.0, 'Plastic - Matte (White)')

    # --- NEW printed wand connector (socket over the spline, carries the gear and the wand loop) ---
    mouth = worm_end - P['tl_spline_len'] + P['tl_conn_gap']       # connector mouth, just clear of the lower flange
    conn = B.cyl(S(mouth), P['tl_conn_d'] / 2, S(mouth + P['tl_conn_len']))
    B.component('NEW wand connector', [('Connector + loop envelope', conn)], 0.6,
                'Plastic - Translucent Matte (Yellow)')

    # --- Crossed helical drive + N20 ---
    gs = P['tl_gear_s']
    rg = P['tl_hg_d'] / 2.0
    rp = P['tl_hp_d'] / 2.0
    ad = P['tl_h_mn']                                    # addendum
    gear = B.cyl(S(gs - P['tl_hg_face'] / 2), rg + ad, S(gs + P['tl_hg_face'] / 2))
    rot = math.radians(P['tl_motor_rot'])
    u = unit(add(mul(X, math.cos(rot)), mul(n, math.sin(rot))))   # motor axis, perpendicular to the worm
    off = unit(mul(cross(d, u), -1.0))                            # common perpendicular, away from the room-side wall
    pc = add(S(gs), mul(off, rg + rp))                            # pinion center
    pinion = B.cyl(add(pc, mul(u, -P['tl_hp_face'] / 2)), rp + ad, add(pc, mul(u, P['tl_hp_face'] / 2)))
    vz = unit(sub(Z, mul(u, dot(Z, u))))
    wv = cross(u, vz)
    face = add(pc, mul(u, P['tl_hp_face'] / 2 + P['tl_pinion_gap']))
    shaft = B.cyl(add(pc, mul(u, -P['tl_hp_face'] / 2)), P['tl_n20_shaft_d'] / 2, face)

    def seg(start, length):
        return B.box(add(start, mul(u, length / 2)), u, wv, length, P['tl_n20_w'], P['tl_n20_h'])

    gbx = seg(face, P['tl_n20_gbx_len'])
    mot_start = add(face, mul(u, P['tl_n20_gbx_len']))
    mot = seg(mot_start, P['tl_n20_mot_len'])
    enc_start = add(mot_start, mul(u, P['tl_n20_mot_len']))
    enc = seg(enc_start, P['tl_n20_enc_len'])
    B.component('NEW helical gear on connector', [('Helical gear envelope', gear)], 1.0, 'Plastic - Glossy (Yellow)')
    B.component('NEW helical pinion', [('Pinion envelope', pinion)], 1.0, 'Plastic - Glossy (Yellow)')
    B.component('N20 motor', [('Shaft', shaft), ('Gearbox', gbx), ('Motor', mot), ('Encoder', enc)], 1.0,
                'Plastic - Glossy (Blue)')

    # --- Fit report: motor envelope corners vs the rail ---
    total = P['tl_n20_gbx_len'] + P['tl_n20_mot_len'] + P['tl_n20_enc_len']
    corners = []
    for along in (0.0, total):
        for sw in (-P['tl_n20_w'] / 2, P['tl_n20_w'] / 2):
            for sh in (-P['tl_n20_h'] / 2, P['tl_n20_h'] / 2):
                corners.append(add(add(add(face, mul(u, along)), mul(wv, sw)), mul(vz, sh)))
    ys = [c[1] for c in corners]
    zs = [c[2] for c in corners]
    xs = [c[0] for c in corners]
    def dist_to_line(p, origin, direction):
        v = sub(p, origin)
        along = dot(v, direction)
        perp = sub(v, mul(direction, along))
        return math.sqrt(dot(perp, perp))

    # closest approach of the motor box to the rod axis (samples along the motor's near edges)
    samples = []
    for k in range(0, 41):
        along = total * k / 40.0
        for sw in (-P['tl_n20_w'] / 2, 0, P['tl_n20_w'] / 2):
            for sh in (-P['tl_n20_h'] / 2, 0, P['tl_n20_h'] / 2):
                samples.append(add(add(add(face, mul(u, along)), mul(wv, sw)), mul(vz, sh)))
    rod_clear = min(dist_to_line(q, rod_c, X) for q in samples) - P['tl_wheel_hub_d'] / 2
    worm_clear = min(dist_to_line(q, p0, d) for q in samples if 0 <= dot(sub(q, p0), d) <= worm_end) \
        - P['tl_flange_d'] / 2 if any(0 <= dot(sub(q, p0), d) <= worm_end for q in samples) else 99.0
    g0, g1 = gs - P['tl_hg_face'] / 2, gs + P['tl_hg_face'] / 2
    spline_start = worm_end - P['tl_spline_len']
    if g0 >= spline_start - 0.01 and g1 <= spline_start + P['tl_conn_depth'] + 0.01:
        gear_where = 'on the connector, over the spline'
    elif g0 >= spline_start:
        gear_where = 'on the connector, below the spline'
    elif g0 >= flange1_end and g1 <= flange2_start:
        gear_where = 'on the plain shaft between the flanges (needs a pin or flat)'
    else:
        gear_where = 'OVERLAPS a flange'
    report = [
        'Worm-wheel center distance: {:.2f} mm (ratio {:.0f}:1)'.format(cd, 16),
        'Worm top end: Y {:.1f}, Z {:.1f}  (rail top Z {:.1f})'.format(worm_top[1], worm_top[2], h),
        'Worm spline end: Y {:.1f}, Z {:.1f}'.format(S(worm_end)[1], S(worm_end)[2]),
        '',
        'Motor envelope X {:.1f}..{:.1f}  (pocket {:.1f}..{:.1f})'.format(min(xs), max(xs), x0, x1),
        'Motor envelope Y {:.1f}..{:.1f}  (walls at ±{:.2f})'.format(min(ys), max(ys), w / 2),
        'Motor envelope Z {:.1f}..{:.1f}  (floor 0, top {:.1f})'.format(min(zs), max(zs), h),
        'Helical center distance {:.2f} mm, pinion center Y {:.1f} Z {:.1f}'.format(rg + rp, pc[1], pc[2]),
        'Motor clearance to worm-wheel barrel: {:.2f} mm'.format(rod_clear),
        'Motor clearance to worm flanges: {:.2f} mm'.format(worm_clear),
        'Gear position: {}'.format(gear_where),
    ]
    problems = []
    if min(ys) < -w / 2 or max(ys) > w / 2:
        problems.append('motor hits a rail wall')
    if min(zs) < 0 or max(zs) > h:
        problems.append('motor hits floor/top')
    if min(xs) < x0 or max(xs) > x1:
        problems.append('motor outside the pocket length')
    if rod_clear < 0.3:
        problems.append('motor too close to the worm-wheel barrel')
    if worm_clear < 0.3:
        problems.append('motor too close to the worm flanges')
    if gear_where.startswith('OVERLAPS'):
        problems.append('helical gear overlaps a flange (adjust tl_gear_s / tl_hg_face)')
    report.append('')
    report.append('FIT OK' if not problems else 'CHECK: ' + '; '.join(problems))
    return '\n'.join(report)


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None:
            doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            design = adsk.fusion.Design.cast(app.activeProduct)
        if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
            design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        remove_old(design)
        report = build(design)
        app.activeViewport.fit()
        ui.messageBox(report, 'Tilt layout')
    except Exception:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
