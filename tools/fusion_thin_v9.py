"""Thin-wall scan of the built tilter (run after tools/fusion_tilter_v9.py, on the open document).

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_thin_v9.py --timeout 1500

For each housing part it takes points all over the surface (about every 2 mm), shoots a ray straight into the
material from each and measures how far it is to the other side. Spots thinner than LIMIT are grouped by place and
listed with their thinnest reading and their area. Knife edges (two faces meeting at an angle) are not walls and are
skipped: only faces that are roughly parallel count.
"""
import json
import math

LIMIT = 1.0          # mm
STEP = 2.0           # mm between sample points
PARTS = ['Tray', 'Lid', 'Bearing shell', 'Motor shell', 'Case left', 'Case right']

design = adsk.fusion.Design.cast(app.activeProduct)
root = design.rootComponent
P3, V3 = adsk.core.Point3D.create, adsk.core.Vector3D.create
out = {}
for i in range(root.occurrences.count):
    comp = root.occurrences.item(i).component
    name = comp.name.split(' ', 1)[-1] if comp.name[:1] == 'T' and ' ' in comp.name else comp.name
    if name not in PARTS or not comp.bRepBodies.count:
        continue
    body = comp.bRepBodies.item(0)
    calc = body.meshManager.createMeshCalculator()
    calc.setQuality(adsk.fusion.TriangleMeshQualityOptions.NormalQualityTriangleMesh)
    mesh = calc.calculate()
    xyz, idx = mesh.nodeCoordinatesAsDouble, mesh.nodeIndices
    spots = {}
    rays = 0
    for t in range(0, len(idx), 3):
        a, b, c = [(xyz[3 * k] * 10, xyz[3 * k + 1] * 10, xyz[3 * k + 2] * 10) for k in idx[t:t + 3]]
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2]); v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        if ln < 1e-6:
            continue
        area = ln / 2
        n = (n[0] / ln, n[1] / ln, n[2] / ln)
        k = max(1, min(8, int(math.sqrt(area * 2) / STEP)))
        pts = [((i_ + 1 / 3) / k, (j_ + 1 / 3) / k) for i_ in range(k) for j_ in range(k - i_)]
        for s_, t_ in pts:
            p = (a[0] + u[0] * s_ + v[0] * t_, a[1] + u[1] * s_ + v[1] * t_, a[2] + u[2] * s_ + v[2] * t_)
            o = P3((p[0] - n[0] * 0.02) / 10, (p[1] - n[1] * 0.02) / 10, (p[2] - n[2] * 0.02) / 10)
            hp = adsk.core.ObjectCollection.create()
            faces = comp.findBRepUsingRay(o, V3(-n[0], -n[1], -n[2]), adsk.fusion.BRepEntityTypes.BRepFaceEntityType, -1.0, False, hp)
            rays += 1
            if not faces.count:
                continue
            h = hp.item(0)
            d = math.sqrt((h.x * 10 - p[0]) ** 2 + (h.y * 10 - p[1]) ** 2 + (h.z * 10 - p[2]) ** 2)
            if d >= LIMIT or d < 0.03:
                continue
            ok, fn = faces.item(0).evaluator.getNormalAtPoint(h)
            if not ok or (fn.x * n[0] + fn.y * n[1] + fn.z * n[2]) > -0.85:      # not a wall: an edge between two angled faces
                continue
            key = (round(p[0] / 4), round(p[1] / 4), round(p[2] / 4))
            sp = spots.setdefault(key, [9.9, 0.0, p, p])
            sp[0] = min(sp[0], d); sp[1] += area / len(pts)
            sp[2] = tuple(min(x, y) for x, y in zip(sp[2], p)); sp[3] = tuple(max(x, y) for x, y in zip(sp[3], p))
    rows = []
    for sp in sorted(spots.values(), key=lambda s: s[0]):
        if sp[1] < 0.3:
            continue
        rows.append('%.2f mm thick, %.1f mm2, X %.1f..%.1f Y %.1f..%.1f Z %.1f..%.1f' % (sp[0], sp[1], sp[2][0], sp[3][0], sp[2][1], sp[3][1], sp[2][2], sp[3][2]))
    out[name] = dict(rays=rays, thin=rows[:400])
print(json.dumps(out, indent=1))
