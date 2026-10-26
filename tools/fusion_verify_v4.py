"""Build TiltPartsV4 in a fresh Fusion document and run the functional checks (through FusionBridge):

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_verify_v4.py --timeout 1500

  1. interference between every printed part and everything else (rail included)
  2. worm / worm wheel: free phase + sweep through a full wheel tooth pitch x SWEEP_STEPS (16:1)
  3. bevel pair: free phase + sweep through a full worm revolution (12:10)
  4. minimum distances for the pairs that matter
Set EXPORT = True to also write the STLs to hardware/mechanical/stl/v0.4.
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
for name, default in (('OVERRIDES', {}), ('EXPORT', False), ('SWEEP_STEPS', 16)):
    if name not in globals():
        globals()[name] = default

mod = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltPartsV4/TiltPartsV4.py'))
mod.P.update(OVERRIDES)


def is_generated(doc):
    try:
        d = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
        return d is not None and any(d.allComponents.item(i).name.startswith(('TP ', 'T4 '))
                                     for i in range(d.allComponents.count))
    except Exception:
        return False


old_docs = [app.documents.item(i) for i in range(app.documents.count) if is_generated(app.documents.item(i))]
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for doc in old_docs:
    doc.close(False)
report = mod.build(design, os.path.join(REPO, 'hardware/mechanical/stl/v0.4') if EXPORT else None)
root = design.rootComponent
mm = app.measureManager


def occ(name):
    return next(root.occurrences.item(i) for i in range(root.occurrences.count)
                if root.occurrences.item(i).component.name == mod.PREFIX + name)


B = {}
for i in range(root.occurrences.count):
    o = root.occurrences.item(i)
    for j in range(o.bRepBodies.count):
        B[o.bRepBodies.item(j).name] = o.bRepBodies.item(j)

PRINTED = [n for n in ('Worm', 'Wand shaft', 'Hex key', 'Worm wheel', 'Motor pinion', 'Case left', 'Case right',
                       'Sensor gear') if n in B]
EXPECTED = {frozenset(p) for p in [('Motor pinion', 'N20 shaft'), ('Sensor gear', 'Magnet')]}


def interference(names):
    col = adsk.core.ObjectCollection.create()
    for n in names:
        col.add(B[n])
    res = design.analyzeInterference(design.createInterferenceInput(col))
    out = []
    for k in range(res.count if res is not None else 0):
        r = res.item(k)
        pair = frozenset((r.entityOne.name, r.entityTwo.name))
        if pair in EXPECTED or not (pair & set(PRINTED)):
            continue
        out.append(('%s <-> %s' % tuple(sorted(pair)), round(r.interferenceBody.volume * 1000, 3)))
    return out


def rotated(base, axis, origin, ang):
    r = adsk.core.Matrix3D.create()
    r.setToRotation(ang, axis, adsk.core.Point3D.create(origin.x, origin.y, origin.z))
    m = base.copy()
    m.transformBy(r)
    return m


def overlap(a, b):
    col = adsk.core.ObjectCollection.create()
    col.add(a.bRepBodies.item(0))
    col.add(b.bRepBodies.item(0))
    res = design.analyzeInterference(design.createInterferenceInput(col))
    if res is None:                     # Fusion returns None (not an empty list) when nothing touches
        return 0.0
    return sum(res.item(k).interferenceBody.volume * 1000 for k in range(res.count))


def check_pair(drv_name, drn_name, ratio, drv_span, steps, sign):
    """Turn the driver through drv_span (rad) and the driven gear by sign * angle / ratio; report the worst overlap.
    Also scans the driven gear's phase at the start (backlash)."""
    drv, drn = occ(drv_name), occ(drn_name)
    vb, nb = drv.transform2.copy(), drn.transform2.copy()
    vz, nz = vb.getAsCoordinateSystem()[3], nb.getAsCoordinateSystem()[3]
    vo, no = vb.translation, nb.translation
    worst = 0.0
    for k in range(steps):
        a = drv_span * k / steps
        drv.transform2 = rotated(vb, vz, vo, a)
        drn.transform2 = rotated(nb, nz, no, sign * a / ratio)
        worst = max(worst, overlap(drv, drn))
    drv.transform2, drn.transform2 = vb, nb
    return round(worst, 4)


def phase_free(drn_name, other, pitch):
    """Degrees the driven gear can turn either way from its built phase before touching (backlash)."""
    drn = occ(drn_name)
    nb = drn.transform2.copy()
    nz, no = nb.getAsCoordinateSystem()[3], nb.translation
    free = {}
    for sgn in (1, -1):
        k = 0
        while k < 20:
            drn.transform2 = rotated(nb, nz, no, sgn * pitch * (k + 1) / 40)
            if overlap(drn, occ(other)) > 1e-6:
                break
            k += 1
        free[sgn] = round(math.degrees(pitch * k / 40), 2)
    drn.transform2 = nb
    return free


z_w = mod.P['z_wheel']
start_ww = round(overlap(occ('Worm'), occ('Worm wheel')), 4)
start_bv = round(overlap(occ('Worm'), occ('Motor pinion')), 4)
# worm turns 2 revolutions (wheel moves 2 teeth); wheel turns -angle/16 (cut that way)
ww = {s: check_pair('Worm', 'Worm wheel', z_w, 4 * math.pi, SWEEP_STEPS * 2, s) for s in (1, -1)}
bv = {s: check_pair('Worm', 'Motor pinion', mod.P['z_bevel_motor'] / mod.P['z_bevel_worm'], 2 * math.pi, SWEEP_STEPS, s)
      for s in (1, -1)}
gear = dict(worm_wheel_start=start_ww, worm_wheel_sweep=ww, worm_wheel_free_deg=phase_free('Worm wheel', 'Worm', 2 * math.pi / z_w),
            bevel_start=start_bv, bevel_sweep=bv, pinion_free_deg=phase_free('Motor pinion', 'Worm', 2 * math.pi / mod.P['z_bevel_motor']))

pairs = [('Wand shaft', 'Rail wall room'), ('Wand shaft', 'Rail floor'), ('Wand shaft', 'Case right'),
         ('Wand shaft', 'Case left'), ('Worm', 'Case right'), ('Worm', 'Case left'), ('Worm wheel', 'Case right'),
         ('Worm wheel', 'Case left'), ('Worm wheel', 'Rod'), ('Motor pinion', 'Case left'), ('Motor pinion', 'Case right'),
         ('N20 shaft', 'Worm'), ('N20', 'Rail floor'), ('N20', 'Rail wall room'), ('N20', 'Rod'),
         ('Case right', 'Rod'), ('Case left', 'Rod'), ('Case right', 'Rail floor'), ('Case right', 'Rail wall room'),
         ('Case right', 'Rail wall back'), ('Magnet', 'AS5600 chip'), ('Sensor gear', 'Case left'),
         ('Sensor gear', 'Case right'), ('Sensor gear', 'Worm'), ('Sensor gear', 'Worm wheel'), ('AS5600 board', 'Rod'),
         ('AS5600 board', 'Rail wall back'), ('AS5600 board', 'N20'), ('AS5600 board', 'Case left')]
dist = {}
for a, b in pairs:
    if a in B and b in B:
        dist['%s / %s' % (a, b)] = round(mm.measureMinimumDistance(B[a], B[b]).value * 10, 2)

result = dict(
    build=report.split('\n'),
    interference=interference(list(B.keys())) or 'none',
    gear=gear,
    distances=dist,
    case_top_z=round(max(B['Case right'].boundingBox.maxPoint.z, B['Case left'].boundingBox.maxPoint.z) * 10, 2),
    motor_min_x=round(B['N20'].boundingBox.minPoint.x * 10, 2),
    volumes={n: round(B[n].volume, 2) for n in PRINTED},
)
