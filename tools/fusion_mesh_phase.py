import math
root = design.rootComponent
occ = lambda n: next(root.occurrences.item(i) for i in range(root.occurrences.count) if root.occurrences.item(i).component.name == n)
ad, pn = occ('TP Adapter'), occ('TP Motor pinion')
base = pn.transform2.copy()
axis_pt = base.translation   # pinion local origin on its axis
zc = base.getAsCoordinateSystem()[3]
def interf():
    col = adsk.core.ObjectCollection.create()
    col.add(ad.bRepBodies.item(0)); col.add(pn.bRepBodies.item(0))
    inp = design.createInterferenceInput(col)
    r = design.analyzeInterference(inp)
    return sum(r.item(k).interferenceBody.volume * 1000 for k in range(r.count))
best = None
rows = []
for k in range(0, 52):
    ang = math.radians(k * (360.0 / 7) / 51)
    rot = adsk.core.Matrix3D.create()
    rot.setToRotation(ang, zc, adsk.core.Point3D.create(axis_pt.x, axis_pt.y, axis_pt.z))
    m = base.copy(); m.transformBy(rot)
    pn.transform2 = m
    v = interf()
    rows.append(round(v, 2))
    if best is None or v < best[0]:
        best = (v, k, m)
pn.transform2 = best[2]
result = {'min_mm3': round(best[0], 3), 'step': best[1], 'scan': rows}
