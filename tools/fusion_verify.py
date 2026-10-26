"""Rebuild TiltParts with parameter overrides inside Fusion and run every functional check.

Run through FusionBridge:  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_verify.py
Set OVERRIDES / EXPORT at the top (or prepend `OVERRIDES = {...}` to the code sent over the bridge).

Checks:
  1. interference between every printed part and everything else (rail included); expected overlaps between
     simplified reference bodies are filtered out
  2. minimum distances for the pairs that matter
  3. gear mesh: pinion phase that gives zero overlap, then a sweep turning both gears together through a full
     adapter revolution (8:7 ratio) looking for any contact
  4. wall above the worm's top pocket (case top vs pocket top)
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
try:
    OVERRIDES
except NameError:
    OVERRIDES = {}
try:
    EXPORT
except NameError:
    EXPORT = False
try:
    SWEEP_STEPS
except NameError:
    SWEEP_STEPS = 16

mod = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltParts/TiltParts.py'))
mod.P.update(OVERRIDES)


def is_generated(doc):
    try:
        d = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
        return d is not None and any(d.allComponents.item(i).name.startswith(mod.PREFIX)
                                     for i in range(d.allComponents.count))
    except Exception:
        return False


# fresh document every run (rebuilding in one design slows Fusion down), closing only our own generated docs
old_docs = [app.documents.item(i) for i in range(app.documents.count) if is_generated(app.documents.item(i))]
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for doc in old_docs:
    doc.close(False)
report = mod.build(design, os.path.join(REPO, 'hardware/mechanical/stl') if EXPORT else None)
root = design.rootComponent
mm = app.measureManager


def occ(name):
    return next(root.occurrences.item(i) for i in range(root.occurrences.count)
                if root.occurrences.item(i).component.name == name)


B = {}
for i in range(root.occurrences.count):
    o = root.occurrences.item(i)
    for j in range(o.bRepBodies.count):
        B[o.bRepBodies.item(j).name] = o.bRepBodies.item(j)

PRINTED = [n for n in ('Adapter', 'Motor pinion', 'Case left', 'Case right', 'Rod gear', 'Sensor gear',
                        'Sensor case left', 'Sensor case right') if n in B]
EXPECTED = {frozenset(p) for p in [('Adapter', 'Worm 6'), ('Motor pinion', 'N20 shaft'), ('Sensor gear', 'Magnet')]}


def interference(names):
    col = adsk.core.ObjectCollection.create()
    for n in names:
        col.add(B[n])
    res = design.analyzeInterference(design.createInterferenceInput(col))
    out = []
    for k in range(res.count):
        r = res.item(k)
        pair = frozenset((r.entityOne.name, r.entityTwo.name))
        if pair in EXPECTED or not (pair & set(PRINTED)):
            continue
        out.append(('%s <-> %s' % tuple(sorted(pair)), round(r.interferenceBody.volume * 1000, 3)))
    return out


# --- gear phase + full-revolution sweep, for each gear pair


def rotated(base, axis, origin, ang):
    r = adsk.core.Matrix3D.create()
    r.setToRotation(ang, axis, adsk.core.Point3D.create(origin.x, origin.y, origin.z))
    m = base.copy()
    m.transformBy(r)
    return m


def check_pair(big_name, small_name, z_big, z_small, steps):
    big, small = occ(big_name), occ(small_name)
    bbase, sbase = big.transform2.copy(), small.transform2.copy()
    bz, sz = bbase.getAsCoordinateSystem()[3], sbase.getAsCoordinateSystem()[3]
    bo, so = bbase.translation, sbase.translation

    def overlap():
        col = adsk.core.ObjectCollection.create()
        col.add(big.bRepBodies.item(0))
        col.add(small.bRepBodies.item(0))
        res = design.analyzeInterference(design.createInterferenceInput(col))
        return sum(res.item(k).interferenceBody.volume * 1000 for k in range(res.count))

    scan = []
    for k in range(30):
        small.transform2 = rotated(sbase, sz, so, 2 * math.pi / z_small * k / 30)
        scan.append(overlap())
    free = [i for i, v in enumerate(scan) if v < 1e-6]
    phase = 2 * math.pi / z_small * (free[len(free) // 2] if free else scan.index(min(scan))) / 30
    worst = {}
    for sgn in (1, -1):
        w = 0.0
        for k in range(steps):
            a = 2 * math.pi * k / steps
            big.transform2 = rotated(bbase, bz, bo, a)
            small.transform2 = rotated(sbase, sz, so, phase + sgn * a * z_big / z_small)
            w = max(w, overlap())
        worst[sgn] = w
    big.transform2 = bbase
    small.transform2 = rotated(sbase, sz, so, phase)
    return dict(min_overlap_mm3=round(min(scan), 4), backlash_deg=round(360.0 / z_small * len(free) / 30, 1),
                sweep_worst_mm3=round(min(worst.values()), 4), sweep_steps=steps)


gear = check_pair('TP Adapter', 'TP Motor pinion', mod.P['z_adapter'], mod.P['z_pinion'], SWEEP_STEPS)
sensor_gears = check_pair('TP Rod gear', 'TP Sensor gear', mod.P['sm_z_rod'], mod.P['sm_z_sensor'], 12)

pairs = [('Adapter', 'Rail wall room'), ('Adapter', 'Rail floor'), ('Adapter', 'Case right'), ('Adapter', 'Case left'),
         ('Motor pinion', 'Case right'), ('Motor pinion', 'Rail floor'), ('Motor pinion', 'Worm 5'),
         ('Motor pinion', 'Worm 6'), ('N20', 'Rail floor'), ('N20', 'Rail wall room'), ('N20', 'Rod'),
         ('Case right', 'Rod'), ('Case left', 'Rod'), ('Case right', 'Rail floor'), ('Case right', 'Rail wall room'),
         ('Case right', 'Rail wall back'), ('Magnet', 'AS5600 board'), ('Rod gear', 'Sensor case right'),
         ('Sensor gear', 'Sensor case right'), ('Sensor gear', 'Sensor case left'), ('Rod gear', 'Rod'),
         ('Sensor case left', 'Rail floor'), ('Sensor case left', 'Rail wall back'), ('AS5600 board', 'Rail floor'),
         ('AS5600 board', 'Rail wall back'), ('Sensor case right', 'N20')]
dist = {}
for a, b in pairs:
    if a in B and b in B:
        dist['%s / %s' % (a, b)] = round(mm.measureMinimumDistance(B[a], B[b]).value * 10, 2)

# wall above the worm: distance from the worm reference (pin + threads) to the case top plane
top_z = mod.P['case_top']
worm_top = max(B['Worm 0'].boundingBox.maxPoint.z, B['Worm 1'].boundingBox.maxPoint.z) * 10
case_max_z = max(B['Case right'].boundingBox.maxPoint.z, B['Case left'].boundingBox.maxPoint.z) * 10

result = dict(
    params={k: mod.P[k] for k in ('worm_angle', 'motor_rot', 'pinion_gap', 'adapter_face', 'spline_clear')},
    build=report.split('\n'),
    interference=interference(list(B.keys())) or 'none',
    gear=gear, sensor_gears=sensor_gears,
    distances=dist,
    worm_top_z=round(worm_top, 2), case_top_z=round(case_max_z, 2),
    motor_max_x=round(B['N20'].boundingBox.maxPoint.x * 10, 2),
)
