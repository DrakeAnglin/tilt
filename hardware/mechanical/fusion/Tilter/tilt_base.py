"""Tilter's Fusion side of the worm drive: small Fusion helpers and the worm builder. Dimensions and pure geometry
(gear math, layout, the worm case's pockets) are in gear_geom.py; fastener sizes in ../fits.py.

The worm is one piece: a printed single-start worm (m 0.88, Ø9.6 pitch, 25° pressure angle) at 60°, thrust ring,
barrel, and the wand shaft + teardrop loop. It prints standing on its top pin, no supports.
"""

import importlib.util
import math
import os

import adsk.core
import adsk.fusion


def _load(path):
    spec = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(path))[0], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GG = _load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gear_geom.py'))
FIT = GG.FIT
P = GG.P
add, sub, mul, dot, cross, unit = GG.add, GG.sub, GG.mul, GG.dot, GG.cross, GG.unit
worm_radius, gear_profile = GG.worm_radius, GG.gear_profile

PREFIX = 'T9 '                # every component name starts with this
LOFT_SECTIONS = 7


def P3(p): return adsk.core.Point3D.create(p[0] / 10.0, p[1] / 10.0, p[2] / 10.0)
def V3(v): return adsk.core.Vector3D.create(v[0], v[1], v[2])
def VI(mm): return adsk.core.ValueInput.createByReal(mm / 10.0)


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


def helical_body(comp, g, z0, face, hand=1.0, backlash=None):
    """Loft the transverse profile through sections rotated along the helix (right hand = +1), from z0."""
    base = gear_profile(g, backlash)
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


# ------------------------------------------------------------------ printed parts
def build_worm(root, L):
    """Local z = s (worm axis toward the wand), origin at the thread center; local x = the rod direction (X)."""
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
    # hole for the steel top pin in the thread end (prints as a hole in the bed face)
    hole = P['top_pin_len'] - P['top_pin_case'] - P['thread_end_clear'] + 0.4
    cut = comp.features.extrudeFeatures.createInput(circle_profile(comp, -half, P['top_pin_d'] / 2 + P['top_pin_hole_clear']), CUT)
    cut.setDistanceExtent(False, VI(hole))
    cut.participantBodies = own_bodies(comp)
    comp.features.extrudeFeatures.add(cut)
    # bearing journal from the threads down to the gear
    extrude(comp, circle_profile(comp, half - 0.3, P['journal_r']), P['thrust_s'] - half + 0.6, JOIN)          # neck
    extrude(comp, circle_profile(comp, P['thrust_s'], P['collar_d'] / 2), L['s_g0'] - P['thrust_s'] + 0.6, JOIN)  # barrel
    # 8T 45° helical (right hand), part of the worm: no spline joint to wear or slip
    helical_body(comp, L['ga'], L['s_g0'], P['worm_gear_face'])
    merge_bodies(comp)
    # the wand shaft + loop are part of the same print (one piece: no joint between worm and wand)
    add_wand(comp, L, L['s_back'])
    merge_bodies(comp)
    # print shaping (the part stands on its thread end): 45° bevel on the gear's downward tooth ends and a 45° cone
    # blending the journal into the gear's root (no flat ledges); 45° chamfers at both thread ends take off the
    # knife-edge thread run-outs (the bottom one also stops elephant's foot)
    ga, jr, sg = L['ga'], P['collar_d'] / 2, L['s_g0']                  # the gear sits on the barrel
    if P['print_chamfer']:
        # 1) 45° bevel on the gear's downward tooth ends (r = rf + (s - s_g0) and inside it stays)
        # 2) the tooth-space floor is raised to one smooth surface: a 45° ramp up from the journal, then 0.3 mm clear of
        #    the pinion's swept envelope (a torus round the gear axis) across the rest of the width, so the mesh is
        #    untouched and there is no ledge anywhere
        # Solid booleans on a copy of the body (revolve features on the curved tooth faces leave sliver bodies).
        tbm = adsk.fusion.TemporaryBRepManager.get()
        rf, ra, gp = ga['rf'], ga['ra'], L['gp']
        old = comp.bRepBodies.item(0)
        body = tbm.copy(old)
        s0, s3 = sg - 0.5, sg + (ra + 2.0 - rf)
        tool = tbm.createCylinderOrCone(P3((0, 0, s0)), (ra + 2.0) / 10, P3((0, 0, s3)), (ra + 2.0) / 10)
        keep = tbm.createCylinderOrCone(P3((0, 0, s0)), (rf - 0.5) / 10, P3((0, 0, s3)), (ra + 2.0) / 10)
        tbm.booleanOperation(tool, keep, adsk.fusion.BooleanTypes.DifferenceBooleanType)
        tbm.booleanOperation(body, tool, adsk.fusion.BooleanTypes.DifferenceBooleanType)
        sc = (L['s_g0'] + L['s_back']) / 2                   # gear center: the pinion crosses here

        def r_top(z):
            line = rf + (z - sg) - 0.02
            d = abs(sc - z)
            safe = L['cd'] - math.sqrt(gp['ra'] ** 2 - d * d) - 0.3 if d < gp['ra'] else ra
            return max(min(line, safe, ra), jr - 0.3)
        # the floor runs the gear's whole width (stopping part-way left a ledge in every tooth space)
        z_lo, z_hi = sg - (rf - jr) - 0.3, L['s_back'] + 0.01
        n = int((z_hi - z_lo) / 0.1) + 1
        zs = [z_lo + (z_hi - z_lo) * k / n for k in range(n + 1)]
        for z0, z1 in zip(zs, zs[1:]):
            seg = tbm.createCylinderOrCone(P3((0, 0, z0)), r_top(z0) / 10, P3((0, 0, z1)), r_top(z1) / 10)
            tbm.booleanOperation(body, seg, adsk.fusion.BooleanTypes.UnionBooleanType)
        add_bodies(comp, [('Worm', body)])
        old.deleteMe()
    ch = 0.6
    for z, sgn in ((-half, 1), (half, -1)):
        revolve_cut(comp, [(w['ra'] - ch, z - sgn * 0.01), (w['ra'] + 0.2, z - sgn * 0.01), (w['ra'] + 0.2, z + sgn * (ch + 0.2))])
    comp.bRepBodies.item(0).name = 'Worm'
    return occ, comp


def revolve_cut(comp, pts_rz, op=None):
    """Cut (or with op=JOIN, add) the ring swept by a (radius, z) polygon around the component's z axis."""
    sk = comp.sketches.add(comp.xZConstructionPlane)
    toS = lambda r, z: sk.modelToSketchSpace(adsk.core.Point3D.create(r / 10.0, 0, z / 10.0))
    lines = sk.sketchCurves.sketchLines
    first = prev = None
    for r, z in pts_rz:
        q = toS(r, z)
        if prev is None:
            prev = q
            continue
        ln = lines.addByTwoPoints(prev, q)
        first = first or ln.startSketchPoint
        prev = ln.endSketchPoint
    lines.addByTwoPoints(prev, first)
    rev = comp.features.revolveFeatures.createInput(sk.profiles.item(0), comp.zConstructionAxis, op or CUT)
    rev.setAngleExtent(False, adsk.core.ValueInput.createByString('360 deg'))
    rev.participantBodies = own_bodies(comp)
    comp.features.revolveFeatures.add(rev)


def add_wand(comp, L, z0):
    """Collar + shaft + teardrop wand loop, added to comp along its z axis from z0 (the worm gear's collar-side face).
    The round shaft blends into the flat loop through a loft (no ball, no neck): from the front the outline runs
    straight on into the teardrop's flanks, from the side it narrows smoothly from Ø6 to the loop's 4 mm."""
    s0 = L['s_back']
    cl, body_end, loop_c = z0 + P['collar_len'], z0 + P['body_end_s'] - s0, z0 + P['loop_s'] - s0
    rc, rb = P['collar_d'] / 2, P['body_d'] / 2
    R, t = P['loop_r_out'], P['loop_t']
    z1 = body_end + P['blend_len']                     # loft from the shaft's end (body_end) to the loop (z1)
    sk = comp.sketches.add(comp.xZConstructionPlane)
    toS = lambda x, z: sk.modelToSketchSpace(adsk.core.Point3D.create(x / 10.0, 0, z / 10.0))
    pts = [toS(0, z0 - 0.3), toS(rc, z0 - 0.3), toS(rc, cl), toS(rb, cl), toS(rb, body_end), toS(0, body_end)]
    lines = sk.sketchCurves.sketchLines
    prev = lines.addByTwoPoints(pts[0], pts[1])
    first = prev.startSketchPoint
    for q in pts[2:]:
        prev = lines.addByTwoPoints(prev.endSketchPoint, q)
    axis_line = lines.addByTwoPoints(prev.endSketchPoint, first)
    rev = comp.features.revolveFeatures.createInput(sk.profiles.item(0), axis_line, NEW)
    rev.setAngleExtent(False, adsk.core.ValueInput.createByString('360 deg'))
    comp.features.revolveFeatures.add(rev)
    # teardrop plate from z1: flanks start at the shaft's width and run tangent onto the ring
    vx, vz = rb, z1 - loop_c
    dv = math.hypot(vx, vz)
    th = math.atan2(vz, vx) + math.acos(R / dv)            # tangent point on the +x side, toward the shaft
    tx, tz = R * math.cos(th), loop_c + R * math.sin(th)
    sk = comp.sketches.add(comp.xZConstructionPlane)
    toS = lambda x, z: sk.modelToSketchSpace(adsk.core.Point3D.create(x / 10.0, 0, z / 10.0))
    lines = sk.sketchCurves.sketchLines
    bottom = lines.addByTwoPoints(toS(-rb, z1), toS(rb, z1))
    right = lines.addByTwoPoints(bottom.endSketchPoint, toS(tx, tz))
    left = lines.addByTwoPoints(toS(-tx, tz), bottom.startSketchPoint)
    sk.sketchCurves.sketchArcs.addByThreePoints(right.endSketchPoint, toS(0, loop_c + R), left.startSketchPoint)
    sk.sketchCurves.sketchCircles.addByCenterRadius(toS(0, loop_c), P['loop_r_in'] / 10.0)
    ring = next(sk.profiles.item(i) for i in range(sk.profiles.count) if sk.profiles.item(i).profileLoops.count == 2)
    inp = comp.features.extrudeFeatures.createInput(ring, NEW)
    inp.setSymmetricExtent(VI(t), True)
    plate = comp.features.extrudeFeatures.add(inp).bodies.item(0)
    top_z = plate.boundingBox.maxPoint.z
    # round every plate edge except the ones in its bottom face (that face is where the blend lands)
    for r in (P['loop_round'], 0.8, 0.6):
        edges = adsk.core.ObjectCollection.create()
        for e in plate.edges:
            if e.boundingBox.maxPoint.z * 10 > z1 + 0.01:
                edges.add(e)
        try:
            fi = comp.features.filletFeatures.createInput()
            fi.addConstantRadiusEdgeSet(edges, VI(r), True)
            comp.features.filletFeatures.add(fi)
            break
        except Exception:
            continue
    plate = next(b for b in own_bodies(comp) if abs(b.boundingBox.maxPoint.z - top_z) < 1e-4
                 and b.boundingBox.minPoint.z * 10 > z1 - 0.01)
    base = min((f for f in plate.faces if abs(f.boundingBox.maxPoint.z - f.boundingBox.minPoint.z) < 1e-4),
               key=lambda f: f.boundingBox.minPoint.z)
    # blend: shaft's end circle -> plate's rounded bottom face, leaving both tangent to what they join
    loft = comp.features.loftFeatures.createInput(NEW)
    sec0 = loft.loftSections.add(circle_profile(comp, body_end, rb))
    sec1 = loft.loftSections.add(base)
    for sec, fn in ((sec0, lambda x: x.setDirectionEndCondition(adsk.core.ValueInput.createByString('0 deg'),
                                                                 adsk.core.ValueInput.createByReal(1.0))),
                    (sec1, lambda x: x.setTangentEndCondition(adsk.core.ValueInput.createByReal(1.0)))):
        try:
            fn(sec)
        except Exception:
            pass
    loft.isSolid = True
    comp.features.loftFeatures.add(loft)


def brep(pr, tbm):
    """TemporaryBRep solid of a gear_geom.Prim."""
    if pr.kind == 'cyl':
        r2 = getattr(pr, 'r2', pr.r)
        return tbm.createCylinderOrCone(P3(pr.p1), pr.r / 10, P3(pr.p2), r2 / 10)
    obb = adsk.core.OrientedBoundingBox3D.create(P3(pr.c), V3(pr.u), V3(pr.w), pr.L / 10, pr.W / 10, pr.H / 10)
    return tbm.createBox(obb)


def color(design, comp, name):
    app = adsk.core.Application.get()
    lib = next((app.materialLibraries.item(i) for i in range(app.materialLibraries.count)
                if app.materialLibraries.item(i).name == 'Fusion Appearance Library'), None)
    if lib is None:
        return
    a = design.appearances.itemByName(name) or design.appearances.addByCopy(lib.appearances.itemByName(name), name)
    for i in range(comp.bRepBodies.count):
        comp.bRepBodies.item(i).appearance = a

