"""The Tilt Hub box in a fresh document: the box, mock-ups of the ESP32-C6 and the USB-C adapter, checks (collisions,
the drop-in at the pause, the pinholes over the buttons) and the print STL.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_hub.py --timeout 600
"""
import os

# REPO is set by fusion.py exec
KIT = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/fusion_kit.py'))
M = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/Hub/Hub.py'))
H = M.H
PREFIX = 'Hub '
STL = os.path.join(REPO, 'hardware/mechanical/stl/hub')
os.makedirs(STL, exist_ok=True)
tbm = adsk.fusion.TemporaryBRepManager.get()
B = adsk.fusion.BooleanTypes


def P3(x, y, z):
    return adsk.core.Point3D.create(x / 10.0, y / 10.0, z / 10.0)


def obox(c, u, w, L, W, Hh):
    obb = adsk.core.OrientedBoundingBox3D.create(P3(*c), adsk.core.Vector3D.create(*u), adsk.core.Vector3D.create(*w),
                                                 L / 10, W / 10, Hh / 10)
    return tbm.createBox(obb)


def bx(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    return obox(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (1, 0, 0), (0, 1, 0), x1 - x0, y1 - y0, z1 - z0)


def cyl(p1, p2, r):
    return tbm.createCylinderOrCone(P3(*p1), r / 10, P3(*p2), r / 10)


def uni(a, *bs):
    for b in bs:
        tbm.booleanOperation(a, b, B.UnionBooleanType)
    return a


def cut(a, *bs):
    for b in bs:
        tbm.booleanOperation(a, b, B.DifferenceBooleanType)
    return a


def isect(a, b):
    tbm.booleanOperation(a, b, B.IntersectionBooleanType)
    return a


def rbox(x0, x1, y0, y1, z0, z1, r):
    b = uni(bx(x0 + r, x1 - r, y0, y1, z0, z1), bx(x0, x1, y0 + r, y1 - r, z0, z1))
    for xx in (x0 + r, x1 - r):
        for yy in (y0 + r, y1 - r):
            b = uni(b, cyl((xx, yy, z0), (xx, yy, z1), r))
    return b


def vol(a, b):
    cc = tbm.copy(a)
    tbm.booleanOperation(cc, tbm.copy(b), B.IntersectionBooleanType)
    try:
        return cc.volume * 1000 if cc.faces.count else 0.0
    except Exception:
        return 0.0


def moved(b, dz):
    t = adsk.core.Matrix3D.create()
    t.translation = adsk.core.Vector3D.create(0, 0, dz / 10)
    cpy = tbm.copy(b)
    tbm.transform(cpy, t)
    return cpy


groups = M.build(bx, cyl, uni, cut, isect, rbox, obox)
box = groups['Box'][0][1]
parts = groups['Parts']
failures = []

# 1. nothing collides with the box
for nm, b in parts:
    v = vol(box, b)
    if v > 0.01:
        failures.append('%s runs into the box: %.2f mm3' % (nm, v))
# 2. at the pause the parts drop straight in: lift them out through the open top, 0.5 mm at a time
lower = isect(tbm.copy(box), bx(-5, H['tip'] + 5, -30, 30, -1, H['zp']))
for nm, b in parts:
    for k in range(1, 31):
        v = vol(lower, moved(b, k * 0.5))
        if v > 0.01:
            failures.append('%s cannot drop in (blocked %.1f mm up): %.2f mm3' % (nm, k * 0.5, v))
            break
# 3. nothing stands above the pause height (the nozzle passes over it)
for nm, b in parts:
    zmax = b.boundingBox.maxPoint.z * 10
    if zmax > H['zp'] - H['top_min'] + 0.01:
        failures.append('%s is only %.2f under the pause height' % (nm, H['zp'] - zmax))
# 4. a paper clip (1.2 mm) goes straight down each pinhole onto its button
for n, (x, y) in H['btn'].items():
    if vol(box, cyl((x, y, H['esp_zt'] + 0.1), (x, y, H['top'] + 3), 0.6)) > 0.001:
        failures.append('pinhole over %s is blocked' % n)
# 5. the adapter's body cannot leave: pushed out the front or in toward the ESP it hits the box
body = dict(parts)['Adapter body']
for dx, what in ((1.0, 'pulled out'), (-1.0, 'pushed in')):
    t = adsk.core.Matrix3D.create()
    t.translation = adsk.core.Vector3D.create(dx / 10, 0, 0)
    cpy = tbm.copy(body)
    tbm.transform(cpy, t)
    if vol(box, cpy) < 1.0:
        failures.append('nothing stops the adapter being %s' % what)
# 6. stays-inside check: nothing reaches outside the box's outside shape, except the plug that goes into the charger
failures += KIT.stays_inside(tbm, [('Hub box', box)] + parts, H['outline'], allow=('Adapter plug',))
if abs(H['zp'] / H['layer'] - H['pause_layer']) > 1e-6:
    failures.append('pause height %.2f is not a whole number of layers' % H['zp'])

# ------------------------------------------------------------------ document
design = KIT.fresh_document(app, 'hub', old_prefixes=(PREFIX,))
root = design.rootComponent


def appearance(name):
    a = design.appearances.itemByName(name)
    if a:
        return a
    for i in range(app.materialLibraries.count):
        try:
            src = app.materialLibraries.item(i).appearances.itemByName(name)
        except Exception:
            src = None
        if src:
            return design.appearances.addByCopy(src, name)


APPEAR = {'Box': 'Plastic - Matte (White)', 'Parts': 'Plastic - Matte (Black)'}
COLOR = {'ESP32-C6 board': 'Plastic - Glossy (Blue)', 'Adapter body': 'Steel - Satin', 'Adapter plug': 'Steel - Satin'}
comps = {}
for g, lst in groups.items():
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = PREFIX + g
    comps[g] = occ.component
    for nm, b in lst:
        bb = occ.component.bRepBodies.add(b)
        bb.name = nm
        a = appearance(COLOR.get(nm, APPEAR[g]))
        if a:
            bb.appearance = a

# small chamfer round the bottom and top outline (not the pinholes)
edge_note = 'none'
try:
    body = comps['Box'].bRepBodies.item(0)
    col = adsk.core.ObjectCollection.create()
    for e in body.edges:
        a, b = e.startVertex, e.endVertex
        if a is None or b is None or a == b:
            continue
        za, zb = a.geometry.z * 10, b.geometry.z * 10
        for zz in (0.0, H['top']):
            if abs(za - zz) < 0.01 and abs(zb - zz) < 0.01:
                col.add(e)
    inp = comps['Box'].features.chamferFeatures.createInput2()
    inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(col, adsk.core.ValueInput.createByReal(H['edge'] / 10), False)
    comps['Box'].features.chamferFeatures.add(inp)
    edge_note = '%d edges' % col.count
except Exception as ex:
    edge_note = 'failed: %s' % str(ex)[:100]

path = os.path.join(STL, 'hub_box.stl')
opt = design.exportManager.createSTLExportOptions(comps['Box'], path)
opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
design.exportManager.execute(opt)
ui.activeSelections.clear()
KIT.hide_helpers(design)
bbx = comps['Box'].bRepBodies.item(0).boundingBox
result = {'ok': not failures, 'failures': failures,
          'box (mm)': 'L %.2f x W %.2f x H %.2f' % ((bbx.maxPoint.x - bbx.minPoint.x) * 10, (bbx.maxPoint.y - bbx.minPoint.y) * 10,
                                                     (bbx.maxPoint.z - bbx.minPoint.z) * 10),
          'plug sticks out (mm)': round(H['tip'] - H['L'], 2),
          'pause at (mm)': round(H['zp'], 2), 'room over the adapter at the pause (mm)': round(H['adp_top'], 2), 'rail height (mm)': round(H['rail_h'], 2), 'pause after layer': H['pause_layer'], 'layer (mm)': H['layer'],
          'lumps': comps['Box'].bRepBodies.item(0).lumps.count, 'chamfer': edge_note, 'exported': path}
