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

PRINTED = [n for n in ('Adapter', 'Motor pinion', 'Case left', 'Case right', 'Magnet cap', 'Sensor holder') if n in B]
EXPECTED = {frozenset(p) for p in [('Adapter', 'Worm 6'), ('Motor pinion', 'N20 shaft')]}


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


# --- gear phase + sweep
ad, pn = occ('TP Adapter'), occ('TP Motor pinion')
pbase = pn.transform2.copy()
abase = ad.transform2.copy()
pz = pbase.getAsCoordinateSystem()[3]
az = abase.getAsCoordinateSystem()[3]
porg = pbase.translation
aorg = abase.translation


def rotated(base, axis, origin, ang):
    r = adsk.core.Matrix3D.create()
    r.setToRotation(ang, axis, adsk.core.Point3D.create(origin.x, origin.y, origin.z))
    m = base.copy()
    m.transformBy(r)
    return m


def gear_overlap():
    col = adsk.core.ObjectCollection.create()
    col.add(ad.bRepBodies.item(0))
    col.add(pn.bRepBodies.item(0))
    res = design.analyzeInterference(design.createInterferenceInput(col))
    return sum(res.item(k).interferenceBody.volume * 1000 for k in range(res.count))


z_ad, z_pn = mod.P['z_adapter'], mod.P['z_pinion']
best = None
scan = []
for k in range(30):
    ang = 2 * math.pi / z_pn * k / 30
    pn.transform2 = rotated(pbase, pz, porg, ang)
    v = gear_overlap()
    scan.append(v)
    if best is None or v < best[0]:
        best = (v, ang)
free = [i for i, v in enumerate(scan) if v < 1e-6]
# centre of the zero-overlap window = mid-backlash phase
if free:
    mid = free[len(free) // 2]
    phase = 2 * math.pi / z_pn * mid / 30
else:
    phase = best[1]
backlash_deg = 360.0 / z_pn * len(free) / 30
# sweep: adapter turns a, pinion turns -a * z_ad / z_pn (direction found by trying both)
sweep_res = {}
for sgn in (1, -1):
    worst = 0.0
    for k in range(SWEEP_STEPS):
        a = 2 * math.pi * k / SWEEP_STEPS
        ad.transform2 = rotated(abase, az, aorg, a)
        pn.transform2 = rotated(pbase, pz, porg, phase + sgn * a * z_ad / z_pn)
        worst = max(worst, gear_overlap())
    sweep_res[sgn] = worst
good_sgn = min(sweep_res, key=sweep_res.get)
ad.transform2 = abase
pn.transform2 = rotated(pbase, pz, porg, phase)

pairs = [('Adapter', 'Rail wall room'), ('Adapter', 'Rail floor'), ('Adapter', 'Case right'), ('Adapter', 'Case left'),
         ('Motor pinion', 'Case right'), ('Motor pinion', 'Rail floor'), ('Motor pinion', 'Worm 5'),
         ('Motor pinion', 'Worm 6'), ('N20', 'Rail floor'), ('N20', 'Rail wall room'), ('N20', 'Rod'),
         ('Case right', 'Rod'), ('Case left', 'Rod'), ('Case right', 'Rail floor'), ('Case right', 'Rail wall room'),
         ('Case right', 'Rail wall back'), ('Magnet cap', 'Sensor holder'), ('Magnet cap', 'Case left'),
         ('Magnet', 'AS5600 board'), ('Sensor holder', 'Rail floor'), ('Sensor holder', 'Rail wall room'),
         ('Sensor holder', 'Rail wall back'), ('AS5600 board', 'Rail floor')]
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
    gear=dict(min_overlap_mm3=round(best[0], 4), backlash_deg=round(backlash_deg, 1),
              sweep_worst_mm3=round(sweep_res[good_sgn], 4), sweep_steps=SWEEP_STEPS),
    distances=dist,
    worm_top_z=round(worm_top, 2), case_top_z=round(case_max_z, 2),
    holder_min_x=round(B['Sensor holder'].boundingBox.minPoint.x * 10, 2) if 'Sensor holder' in B else None,
    motor_max_x=round(B['N20'].boundingBox.maxPoint.x * 10, 2),
)
