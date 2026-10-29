"""Tilter v0.4 + drive housing (TiltPod), fresh document: rebuilds the tilter (case STLs re-exported: the housing's two
bolts are new case bolts), checks every housing / cover / inside part against every tilter body and each other, exports
housing + cover STLs, renders with sketches hidden.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_tiltpod.py --timeout 1500
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
T4 = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltPartsV4/TiltPartsV4.py'))
POD = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltPod/TiltPod.py'))
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


old = []
for i in range(app.documents.count):
    d = app.documents.item(i)
    try:
        des = adsk.fusion.Design.cast(d.products.itemByProductType('DesignProductType'))
        if des and any(des.allComponents.item(k).name.startswith(('T4 ', 'TP ')) for k in range(des.allComponents.count)):
            old.append(d)
    except Exception:
        pass
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for d in old:
    d.close(False)
t4_report = T4.build(design, STL)
root = design.rootComponent

groups = POD.build(tbm, bx, cyl, cone, uni, cut)
groups['Plug'].append(('Tilt rod (on through the module)', bx(-80, -8.33, -2, 2, POD.P['rod_z'] - 2, POD.P['rod_z'] + 2)))
tilter = []
for i in range(root.occurrences.count):
    o = root.occurrences.item(i)
    for j in range(o.bRepBodies.count):
        b = o.bRepBodies.item(j)
        if b.name not in ('Rod', 'N20 shaft', 'Magnet', 'AS5600 board', 'AS5600 chip'):   # the module carries the board now
            tilter.append(('T4 ' + b.name, tbm.copy(b)))            # occurrence proxies: already in world space
own = [(g, nm, b) for g in ('Module', 'Inside', 'Screws', 'Plug') for nm, b in groups[g]]
sweep = cyl((-80, 0, POD.P['rod_z']), (-8.4, 0, POD.P['rod_z']), POD.P['rod'] * math.sqrt(2) / 2)


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


SAME = [{'RJ12 board', 'RJ12 jack'}, {'RJ12 board', 'RJ12 pins'}, {'RJ12 jack', 'RJ12 plug'}, {'RJ12 plug', 'White cord'},
        {'DRV8833', 'DRV8833 chip'}, {'DRV8833', 'C 10uF'}, {'AS5600 board', 'AS5600 chip'}]
hits = []
for g, na, a in own:
    for nb, b in tilter:
        v = vol(a, b)
        if v > 0.01:
            hits.append('%s / %s: %.2f mm3' % (na, nb, v))
for i in range(len(own)):
    for j in range(i + 1, len(own)):
        if own[i][0] == own[j][0] and own[i][0] in ('Module', 'Screws', 'Plug'):
            continue
        if {own[i][1], own[j][1]} in SAME:
            continue
        v = vol(own[i][2], own[j][2])
        if v > 0.01:
            hits.append('%s / %s: %.2f mm3' % (own[i][1], own[j][1], v))
rod_hits = []
for g, na, a in own:
    v = vol(a, sweep)
    if v > 0.01:
        rod_hits.append('%s: %.2f mm3' % (na, v))

APPEAR = {'Module': 'Plastic - Matte (White)', 'Inside': 'Plastic - Matte (Black)',
          'Screws': 'Steel - Satin', 'Plug': 'Plastic - Matte (White)'}


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
    occ.component.name = 'T4 ' + g
    comps[g], occs[g] = occ.component, occ
    ap = appearance(APPEAR[g])
    for nm, b in lst:
        bb = occ.component.bRepBodies.add(b)
        bb.name = nm
        if ap:
            bb.appearance = ap
def round_x_edges(comp, r, min_len):
    """Fillet the outline's edges that run along X (rounded long edges, like the tilter case)."""
    body = comp.bRepBodies.item(0)
    bb = body.boundingBox
    picked = adsk.core.ObjectCollection.create()
    for e in body.edges:
        if not isinstance(e.geometry, adsk.core.Line3D) or e.length < min_len:
            continue
        a, b = e.startVertex.geometry, e.endVertex.geometry
        if abs(a.y - b.y) > 1e-4 or abs(a.z - b.z) > 1e-4:
            continue
        if abs(a.y - bb.minPoint.y) < 0.02 or abs(a.y - bb.maxPoint.y) < 0.02 or abs(a.z - bb.minPoint.z) < 0.02 \
                or abs(a.z - bb.maxPoint.z) < 0.02:
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


fillets = {'Module': round_x_edges(comps['Module'], POD.P['edge_r'], 0.5)}

files = []
em = design.exportManager
for g, nm in (('Module', 'sensor_module'),):
    path = os.path.join(STL, nm + '.stl')
    opt = em.createSTLExportOptions(comps[g], path)
    opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    em.execute(opt)
    files.append(path)
for old_stl in ('pod_tray.stl', 'pod_lid.stl', 'drive_housing.stl', 'drive_cover.stl', 'print/drive_housing.stl',
                'print/drive_cover.stl'):
    try:
        os.remove(os.path.join(STL, old_stl))
    except OSError:
        pass

# ---------------- renders: sketches, construction geometry and origins hidden
ui.activeSelections.clear()
for k in range(design.allComponents.count):
    c = design.allComponents.item(k)
    for attr in ('isSketchFolderLightBulbOn', 'isConstructionFolderLightBulbOn', 'isOriginFolderLightBulbOn',
                 'isJointsFolderLightBulbOn'):
        try:
            setattr(c, attr, False)
        except Exception:
            pass
    for s in range(c.sketches.count):
        c.sketches.item(s).isLightBulbOn = False
vp = app.activeViewport
try:
    vp.visualStyle = adsk.core.VisualStyles.ShadedVisualStyle
except Exception:
    pass
out = os.path.join(REPO, 'docs/renders')


def vis(hide=(), ghost=()):
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        o.isLightBulbOn = not any(h in o.component.name for h in hide)
        for j in range(o.component.bRepBodies.count):
            b = o.component.bRepBodies.item(j)
            if b.name.startswith('Rail'):
                b.isLightBulbOn = 'Rail' not in hide
                b.opacity = 0.25
            elif o.component.name.startswith('T4 REF'):
                b.opacity = 1.0
                if b.name.startswith('AS5600'):              # the module carries the board now
                    b.isLightBulbOn = False
            else:
                b.opacity = 0.35 if any(gh in o.component.name for gh in ghost) else 1.0


def move(g, dx):
    m = adsk.core.Matrix3D.create()
    m.translation = adsk.core.Vector3D.create(dx / 10.0, 0, 0)
    occs[g].transform2 = m


def shot(name, orient, ortho=False, eye=None):
    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.OrthographicCameraType if ortho else adsk.core.CameraTypes.PerspectiveCameraType
    if eye:
        cam.eye = P3(*eye)
        cam.target = P3(-10, 0, 18)
        cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
    else:
        cam.viewOrientation = getattr(adsk.core.ViewOrientations, orient)
    cam.isFitView = True
    vp.camera = cam
    vp.fit()
    p = os.path.join(out, name)
    vp.saveAsImageFile(p, 1800, 1100)
    return p


res = []
EYE = (-260, -170, 140)                      # from the module end, room side, above
EYE_OPEN = (120, -190, 150)                  # into the module's open face
vis(hide=('Rail', 'Plug')); res.append(shot('module-closed.png', None, eye=EYE))
vis(hide=('Rail',)); res.append(shot('module-plugged.png', None, eye=EYE))
move('Module', -45); move('Inside', -45)
vis(hide=('Rail', 'Plug', 'Screws')); res.append(shot('module-exploded.png', None, eye=(-150, -230, 160)))
move('Module', 0); move('Inside', 0)
for i in range(root.occurrences.count):                 # module alone, from its open face
    o = root.occurrences.item(i)
    o.isLightBulbOn = o.component.name in ('T4 Module', 'T4 Inside')
res.append(shot('module-open-face.png', None, eye=EYE_OPEN))
vis(hide=('Rail', 'Plug', 'Screws'), ghost=('Module', 'Case left', 'Case right')); res.append(shot('module-xray.png', None, eye=(-200, 170, 160)))
vis(); res.append(shot('module-in-rail.png', None, eye=(-260, -60, 90)))
vis(hide=('Rail', 'Plug'))
result = {'summary': POD.summary(), 'interference': hits or 'none',
          'rod sweep (only if the rod runs on past the tilter on this side)': rod_hits or 'clear',
          'fillets (edges)': fillets, 'tilter': t4_report.split('\n'), 'exported': files, 'renders': res}
