"""ControllerV3 in a fresh document: tray, lid, every part, rail + rod; exact interference check; STL export of tray +
lid; renders with sketches hidden.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v3.py --timeout 1200
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
M = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/ControllerV3/ControllerV3.py'))
C = M.C
STL = os.path.join(REPO, 'hardware/mechanical/stl/v0.4')
tbm = adsk.fusion.TemporaryBRepManager.get()
B = adsk.fusion.BooleanTypes


def P3(x, y, z):
    return adsk.core.Point3D.create(x / 10.0, y / 10.0, z / 10.0)


def bx(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    obb = adsk.core.OrientedBoundingBox3D.create(P3((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
                                                 adsk.core.Vector3D.create(1, 0, 0), adsk.core.Vector3D.create(0, 1, 0),
                                                 (x1 - x0) / 10, (y1 - y0) / 10, (z1 - z0) / 10)
    return tbm.createBox(obb)


def obox(c, u, w, L, W, H):
    obb = adsk.core.OrientedBoundingBox3D.create(P3(*c), adsk.core.Vector3D.create(*u), adsk.core.Vector3D.create(*w),
                                                 L / 10, W / 10, H / 10)
    return tbm.createBox(obb)


def cyl(p1, p2, r):
    return tbm.createCylinderOrCone(P3(*p1), r / 10, P3(*p2), r / 10)


def cone(p1, r1, p2, r2):
    return tbm.createCylinderOrCone(P3(*p1), r1 / 10, P3(*p2), r2 / 10)


def uni(a, *bs):
    for b in bs:
        tbm.booleanOperation(a, b, B.UnionBooleanType)
    return a


def cut(a, *bs):
    for b in bs:
        tbm.booleanOperation(a, b, B.DifferenceBooleanType)
    return a


groups = M.build(tbm, bx, cyl, cone, uni, cut, obox)
L = C['L']
rh, rt = C['rail_w'] / 2, C['rail_wall']
groups['Rail'] = [('Rail floor', bx(-20, L + 20, -rh - rt, rh + rt, -rt, 0)),
                  ('Rail wall room', bx(-20, L + 20, -rh - rt, -rh, -rt, C['rail_h'])),
                  ('Rail wall back', bx(-20, L + 20, rh, rh + rt, -rt, C['rail_h'])),
                  ('Rail lip room', bx(-20, L + 20, -rh, -rh + C['lip_in'], C['rail_h'] - C['lip_h'], C['rail_h'])),
                  ('Rail lip back', bx(-20, L + 20, rh - C['lip_in'], rh, C['rail_h'] - C['lip_h'], C['rail_h'])),
                  ('Tilt rod sweep', cyl((-20, 0, C['rod_z']), (L + 20, 0, C['rod_z']), C['rod'] * math.sqrt(2) / 2))]
groups['Screws'] = [('M3x8', uni(cone((x, y, C['top']), 2.95, (x, y, C['top'] - 1.45), 1.5),
                                 cyl((x, y, C['top'] - 1.4), (x, y, C['top'] - 8), 1.45))) for x, y in M.LID_SCREWS]

own = [(g, nm, b) for g in ('Tray', 'Lid', 'Parts', 'Screws') for nm, b in groups[g]]
own += [('Rail', nm, b) for nm, b in groups['Rail']]


def vol(a, b):
    A, Bb = a.boundingBox, b.boundingBox
    if (A.maxPoint.x <= Bb.minPoint.x or Bb.maxPoint.x <= A.minPoint.x or A.maxPoint.y <= Bb.minPoint.y or
            Bb.maxPoint.y <= A.minPoint.y or A.maxPoint.z <= Bb.minPoint.z or Bb.maxPoint.z <= A.minPoint.z):
        return 0.0
    c = tbm.copy(a)
    tbm.booleanOperation(c, tbm.copy(b), B.IntersectionBooleanType)
    try:
        return c.volume * 1000 if c.faces.count else 0.0
    except Exception:
        return 0.0


def same_part(a, b):
    for k in ('RJ12 1', 'RJ12 2', 'RJ12 3', 'ESP32-C6', 'MCP73871', 'USB-C', 'Battery pins', 'XH plug'):
        if a.startswith(k) and b.startswith(k):
            return True
    return {a, b} in ({'Battery pins', 'XH plug'},)


hits = []
for i in range(len(own)):
    for j in range(i + 1, len(own)):
        gi, ni, bi = own[i]
        gj, nj, bj = own[j]
        if gi == gj and gi in ('Tray', 'Lid', 'Screws', 'Rail'):
            continue
        if same_part(ni, nj) or ('Perfboard' in (ni, nj) and ('header' in ni + nj or 'pins' in ni + nj or 'tape' in ni + nj)):
            continue
        if gi == 'Rail' and gj == 'Rail':
            continue
        v = vol(bi, bj)
        if v > 0.01:
            hits.append('%s / %s: %.2f mm3' % (ni, nj, v))

old = []
for i in range(app.documents.count):
    d = app.documents.item(i)
    try:
        des = adsk.fusion.Design.cast(d.products.itemByProductType('DesignProductType'))
        if des and any(des.allComponents.item(k).name.startswith('C3 ') for k in range(des.allComponents.count)):
            old.append(d)
    except Exception:
        pass
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for d in old:
    d.close(False)
root = design.rootComponent
APPEAR = {'Tray': 'Plastic - Matte (White)', 'Lid': 'Plastic - Matte (White)', 'Parts': 'Plastic - Matte (Black)',
          'Screws': 'Steel - Satin', 'Rail': 'Plastic - Matte (White)'}


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


comps, occs = {}, {}
for g, lst in groups.items():
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = 'C3 ' + g
    comps[g], occs[g] = occ.component, occ
    ap = appearance(APPEAR[g])
    for nm, b in lst:
        bb = occ.component.bRepBodies.add(b)
        bb.name = nm
        if ap:
            bb.appearance = ap
        if g == 'Parts' and (nm.startswith('ESP32') or nm.startswith('MCP') or nm == 'Perfboard'):
            g2 = appearance('Plastic - Glossy (Green)') if nm == 'Perfboard' else appearance('Plastic - Glossy (Blue)')
            if g2:
                bb.appearance = g2
        if g == 'Parts' and nm == '18650':
            g3 = appearance('Plastic - Glossy (Blue)')
            if g3:
                bb.appearance = g3


def round_x_edges(comp, r):
    body = comp.bRepBodies.item(0)
    bbx = body.boundingBox
    picked = adsk.core.ObjectCollection.create()
    for e in body.edges:
        if not isinstance(e.geometry, adsk.core.Line3D) or e.length < 5:
            continue
        a, b = e.startVertex.geometry, e.endVertex.geometry
        if abs(a.y - b.y) > 1e-4 or abs(a.z - b.z) > 1e-4:
            continue
        if abs(abs(a.y) - C['half_w'] / 10) < 0.002 and (abs(a.z - bbx.minPoint.z) < 0.002 or abs(a.z - C['top'] / 10) < 0.002):
            picked.add(e)
    if picked.count == 0:
        return 0
    try:
        inp = comp.features.filletFeatures.createInput()
        inp.addConstantRadiusEdgeSet(picked, adsk.core.ValueInput.createByReal(r / 10), True)
        comp.features.filletFeatures.add(inp)
        return picked.count
    except Exception:
        return -1


fil = {g: round_x_edges(comps[g], C['edge_r']) for g in ('Tray', 'Lid')}
files = []
em = design.exportManager
for g, nm in (('Tray', 'controller_tray'), ('Lid', 'controller_lid')):
    path = os.path.join(STL, nm + '.stl')
    opt = em.createSTLExportOptions(comps[g], path)
    opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    em.execute(opt)
    files.append(path)

ui.activeSelections.clear()
for k in range(design.allComponents.count):
    cc = design.allComponents.item(k)
    for attr in ('isSketchFolderLightBulbOn', 'isConstructionFolderLightBulbOn', 'isOriginFolderLightBulbOn'):
        try:
            setattr(cc, attr, False)
        except Exception:
            pass
vp = app.activeViewport
try:
    vp.visualStyle = adsk.core.VisualStyles.ShadedVisualStyle
except Exception:
    pass
out = os.path.join(REPO, 'docs/renders')


def vis(hide=()):
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        o.isLightBulbOn = not any(h in o.component.name for h in hide)
        for j in range(o.component.bRepBodies.count):
            b = o.component.bRepBodies.item(j)
            if b.name.startswith('Rail'):
                b.opacity = 0.25


def move(g, dz):
    m = adsk.core.Matrix3D.create()
    m.translation = adsk.core.Vector3D.create(0, 0, dz / 10.0)
    occs[g].transform2 = m


def shot(name, eye, target=(L / 2, 0, 15)):
    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
    cam.eye = P3(*eye)
    cam.target = P3(*target)
    cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
    cam.isFitView = True
    vp.camera = cam
    vp.fit()
    p = os.path.join(out, name)
    vp.saveAsImageFile(p, 1800, 1100)
    return p


res = []
vis(hide=('Rail', 'Lid', 'Screws')); res.append(shot('ctrl-v3-open.png', (L / 2 - 160, -170, 190)))
res.append(shot('ctrl-v3-open-b.png', (L / 2 + 170, 150, 190)))
move('Lid', 40); move('Screws', 40)
vis(hide=('Rail',)); res.append(shot('ctrl-v3-exploded.png', (L / 2 - 170, -190, 160)))
move('Lid', 0); move('Screws', 0)
vis(hide=('Rail',)); res.append(shot('ctrl-v3-closed.png', (-120, -160, 120)))
res.append(shot('ctrl-v3-end-b.png', (L + 150, 60, 60)))
vis(); res.append(shot('ctrl-v3-end-a.png', (-200, 0, 20), (0, 0, 18)))
vis(hide=('Lid', 'Screws', 'Tray', 'Rail')); res.append(shot('ctrl-v3-boards-top.png', (L / 2, 0, 300)))
vis(); res.append(shot('ctrl-v3-in-rail.png', (-140, -90, 90)))
vis(hide=('Rail',))
result = {'box': 'L %.1f x W %.1f x H %.1f' % (L, 2 * C['half_w'], C['top']), 'interference': hits or 'none',
          'fillets': fil, 'exported': files, 'renders': res}
