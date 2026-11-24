"""The Tilt Hub box in a fresh document: the box, mock-ups of the ESP32-C6 and the USB-C adapter, checks (collisions,
the drop-in at the pause, the pinholes over the buttons) and the print STL.
Then run tools/bambu_hub.py for the two-color Bambu Studio project.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_hub.py --timeout 600
"""
import math
import os
import tempfile

# REPO is set by fusion.py exec
KIT = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/fusion_kit.py'))
M = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/Hub/Hub.py'))
H = M.H
PREFIX = 'Hub '
WORDMARK = True                        # 'tilt' engraved in the bed face beside the three slats
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


def cone(p1, r1, p2, r2):
    return tbm.createCylinderOrCone(P3(*p1), r1 / 10, P3(*p2), r2 / 10)


groups = M.build(bx, cyl, uni, cut, isect, rbox, obox, cone)
box = groups['Box'][0][1]
parts = groups['Parts']
failures = []

# 1. nothing collides with the box
for nm, b in parts:
    v = vol(box, b)
    if v > 0.01:
        failures.append('%s runs into the box: %.2f mm3' % (nm, v))
# 2. at the pause the parts go in nose first: tilted, the plug slides out through the lip's hole, then the back drops.
# Poses: the finished position turned by a degrees about the hole (back end up), then pulled back b mm along the plug.
# A way in = a chain of free poses, each next to the last, from one that lifts straight out to the finished position.
lower = isect(tbm.copy(box), bx(-5, H['tip'] + 5, -30, 30, -1, H['zp']))
allp = tbm.copy(parts[0][1])
for nm, b in parts[1:]:
    tbm.booleanOperation(allp, tbm.copy(b), B.UnionBooleanType)
PIV = P3(H['lip_x0'] + H['lip'] / 2, 0, H['zc'])
A_MAX, B_STEP, B_N = 20, 0.125, 60                     # degrees; mm; b up to 7.5 (plug clear of the lip)


def posed(a, b, dz=0.0):
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.radians(a), adsk.core.Vector3D.create(0, 1, 0), PIV)
    ar = math.radians(a)
    t = adsk.core.Matrix3D.create()
    t.translation = adsk.core.Vector3D.create(-math.cos(ar) * b / 10, 0, (math.sin(ar) * b + dz) / 10)
    m.transformBy(t)
    cpy = tbm.copy(allp)
    tbm.transform(cpy, m)
    return cpy


_free = {}


def free(i, j):
    if (i, j) not in _free:
        _free[(i, j)] = vol(lower, posed(i, j * B_STEP)) < 0.01
    return _free[(i, j)]


def lifts_out(i, j):
    return all(vol(lower, posed(i, j * B_STEP, dz)) < 0.01 for dz in (1, 2, 3, 4, 6, 8, 10, 14))


way_in = None
if not free(0, 0):
    failures.append('the parts do not fit in their finished position')
else:
    seen, todo = {(0, 0): None}, [(0, 0)]
    while todo and way_in is None:
        cur = todo.pop(0)
        if cur[1] == B_N and lifts_out(*cur):
            way_in = []
            while cur is not None:
                way_in.append(cur)
                cur = seen[cur]
            break
        for di, dj in ((0, 1), (1, 0), (-1, 0), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            nx = (cur[0] + di, cur[1] + dj)
            if 0 <= nx[0] <= A_MAX and 0 <= nx[1] <= B_N and nx not in seen and free(*nx):
                seen[nx] = cur
                todo.append(nx)
    if way_in is None:
        failures.append('no way in: the parts cannot slide in through the lip and drop (tried up to %d deg)' % A_MAX)
# 3. nothing stands above the pause height (the nozzle passes over it)
for nm, b in parts:
    zmax = b.boundingBox.maxPoint.z * 10
    if zmax > H['zp'] - H['top_min'] + 0.01:
        failures.append('%s is only %.2f under the pause height' % (nm, H['zp'] - zmax))
# 4. a paper clip (1.2 mm) goes straight in through each pinhole onto its button
for n, (x, y) in H['btn'].items():
    if vol(box, cyl((x, y, -3), (x, y, H['esp_face'] - 0.1), 0.6)) > 0.001:
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

# 7. walls: the hollow inside (without the pinholes) is nowhere nearer the outside than WALL_MIN. The lip in front of
# the adapter is thinner on purpose (H['lip']) and is left out
WALL_MIN = 1.0
wall_note = 'not measured'
try:
    hollow = tbm.copy(H['outline'])
    tbm.booleanOperation(hollow, tbm.copy(box), B.DifferenceBooleanType)
    tbm.booleanOperation(hollow, bx(H['x_in'] - 1, H['L'] - WALL_MIN - 0.05, -30, 30, H['fz'] - 0.01, H['zp'] + 0.01), B.IntersectionBooleanType)
    for x, y in H['btn'].values():
        tbm.booleanOperation(hollow, cyl((x, y, -1), (x, y, H['tube_top'] + 0.02), H['pin_d'] / 2 + 0.05), B.DifferenceBooleanType)
    # grow test: the hollow moved WALL_MIN any way sideways, up or down must stay inside the outside shape
    worst = 0.0
    for k in range(16):
        ang = math.pi * k / 8
        for dz in (0,):
            t = adsk.core.Matrix3D.create()
            t.translation = adsk.core.Vector3D.create(math.cos(ang) * WALL_MIN / 10, math.sin(ang) * WALL_MIN / 10, 0)
            cpy = tbm.copy(hollow)
            tbm.transform(cpy, t)
            tbm.booleanOperation(cpy, tbm.copy(H['outline']), B.DifferenceBooleanType)
            worst = max(worst, cpy.volume * 1000 if cpy.faces.count else 0.0)
    for dz in (WALL_MIN, -WALL_MIN):
        t = adsk.core.Matrix3D.create()
        t.translation = adsk.core.Vector3D.create(0, 0, dz / 10)
        cpy = tbm.copy(hollow)
        tbm.transform(cpy, t)
        tbm.booleanOperation(cpy, tbm.copy(H['outline']), B.DifferenceBooleanType)
        worst = max(worst, cpy.volume * 1000 if cpy.faces.count else 0.0)
    wall_note = 'all %.1f or more' % WALL_MIN
    if worst > 0.01:
        wall_note = 'thin'
        failures.append('a wall is under %.1f mm (%.2f mm3 breaks out when the hollow is moved that far)' % (WALL_MIN, worst))
except Exception as ex:
    wall_note = 'failed: %s' % str(ex)[:80]

# ------------------------------------------------------------------ document
design = KIT.fresh_document(app, 'hub', old_prefixes=(PREFIX,))
root = design.rootComponent


def text_tool(text, size, depth):
    """A solid of the text, to cut into the bed face (z = 0): it starts at x = H['text_x'], runs toward the plug and is
    centered on y = 0. The text is made flat on the XY plane (reads right from above), then turned over about X, a
    plain rotation, so it reads right when you look at the bed face with the plug to the right."""
    sk = root.sketches.add(root.xYConstructionPlane)
    ti = sk.sketchTexts.createInput2(text, size / 10)
    ti.setAsMultiLine(adsk.core.Point3D.create(0, 0, 0), adsk.core.Point3D.create(6, 2, 0),
                      adsk.core.HorizontalAlignments.LeftHorizontalAlignment, adsk.core.VerticalAlignments.BottomVerticalAlignment, 0)
    try:
        ti.fontName = 'Arial Rounded MT Bold'
    except Exception:
        pass
    tx = sk.sketchTexts.add(ti)
    ei = root.features.extrudeFeatures.createInput(tx, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal((depth + 0.02) / 10))
    root.features.extrudeFeatures.add(ei)
    made = [root.bRepBodies.item(k) for k in range(root.bRepBodies.count)]
    tool = tbm.copy(made[0])
    for b in made[1:]:
        tbm.booleanOperation(tool, tbm.copy(b), B.UnionBooleanType)
    for b in made:
        b.deleteMe()
    sk.deleteMe()
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.pi, adsk.core.Vector3D.create(1, 0, 0), adsk.core.Point3D.create(0, 0, 0))
    tbm.transform(tool, m)
    q = tool.boundingBox
    t = adsk.core.Matrix3D.create()
    t.translation = adsk.core.Vector3D.create(H['text_x'] / 10 - q.minPoint.x, -(q.minPoint.y + q.maxPoint.y) / 2, -0.002 - q.minPoint.z)
    tbm.transform(tool, t)
    return tool


# the name on the bed face, beside the three slats
eng = 'off'
if WORDMARK:
    try:
        # (the document is empty here: the text is made first, then the box is added)
        tool = text_tool('tilt', H['text_size'], H['mark_depth'])
        q = tool.boundingBox
        eng = 'X %.1f..%.1f Y %.1f..%.1f' % (q.minPoint.x * 10, q.maxPoint.x * 10, q.minPoint.y * 10, q.maxPoint.y * 10)
        if q.maxPoint.x * 10 > H['L'] - 2.0:
            failures.append('the word runs too near the front edge (to X %.1f)' % (q.maxPoint.x * 10))
        tbm.booleanOperation(box, tool, B.DifferenceBooleanType)
        fill = isect(tbm.copy(tool), bx(0, H['L'], -30, 30, 0, H['mark_depth']))      # the word's share of the inlay
        tbm.booleanOperation(groups['Mark'][0][1], fill, B.UnionBooleanType)
    except Exception as ex:
        eng = 'failed: %s' % str(ex)[:120]
        failures.append('the word could not be engraved')


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


APPEAR = {'Box': 'Plastic - Matte (White)', 'Mark': 'Plastic - Matte (Blue)', 'Parts': 'Plastic - Matte (Black)'}
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
            # only the outline: an edge of an outside wall (a face that runs most of the box's height), not the mark's
            if abs(za - zz) < 0.01 and abs(zb - zz) < 0.01 and any(
                    (f.boundingBox.maxPoint.z - f.boundingBox.minPoint.z) * 10 > H['top'] - 0.1 for f in e.faces):
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
# the inlay for a two-color print, same coordinates as the box. It is only an input for tools/bambu_hub.py, which packs
# box + inlay into hub_box_multicolor.3mf, so it goes to the temporary folder, not the repo
mark_path = os.path.join(tempfile.gettempdir(), 'tilt_hub_box_mark.stl')
opt = design.exportManager.createSTLExportOptions(comps['Mark'], mark_path)
opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
design.exportManager.execute(opt)
mb = comps['Mark'].bRepBodies.item(0)
if vol(tbm.copy(comps['Box'].bRepBodies.item(0)), tbm.copy(mb)) > 0.01:
    failures.append('the inlay runs into the box')
ui.activeSelections.clear()
KIT.hide_helpers(design)
bbx = comps['Box'].bRepBodies.item(0).boundingBox
result = {'ok': not failures, 'failures': failures,
          'box (mm)': 'L %.2f x W %.2f x H %.2f' % ((bbx.maxPoint.x - bbx.minPoint.x) * 10, (bbx.maxPoint.y - bbx.minPoint.y) * 10,
                                                     (bbx.maxPoint.z - bbx.minPoint.z) * 10),
          'plug sticks out (mm)': round(H['tip'] - H['L'], 2),
          'pause at (mm)': round(H['zp'], 2), 'room over the adapter at the pause (mm)': round(H['adp_top'], 2), 'floor (mm)': round(H['fz'], 2), 'rails to the ESP face (mm)': round(H['esp_face'] - H['rail_top'], 3), 'roof over the ESP back (mm)': round(H['zp'] - H['esp_back'], 2), 'web (mm)': round(H['web_x1'] - H['web_x0'], 2), 'pause after layer': H['pause_layer'], 'layer (mm)': H['layer'],
          'way in': ('tilt up to %d deg, %d steps' % (max(a for a, _ in way_in), len(way_in))) if way_in else None,
          'walls': wall_note, 'wordmark': eng, 'lumps': comps['Box'].bRepBodies.item(0).lumps.count, 'chamfer': edge_note, 'inlay': '%.1f mm3, %d pieces, Z %.2f..%.2f' % (mb.volume * 1000, mb.lumps.count, mb.boundingBox.minPoint.z * 10, mb.boundingBox.maxPoint.z * 10),
          'exported': [path, mark_path]}
