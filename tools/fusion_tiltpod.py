"""Tilter v0.4 + the RJ12 / driver pod, in a fresh document: interference check of every pod body against every tilter
body (case halves, worm, gears, N20, AS5600, rail) and the rod's sweep; STL export of the pod; renders.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_tiltpod.py --timeout 1500
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
T4 = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltPartsV4/TiltPartsV4.py'))
POD = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltPod/TiltPod.py'))
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
T4.build(design)
root = design.rootComponent

groups = POD.build(tbm, bx, cyl, uni, cut)
# rod continuing on the pod side (only matters if the blind's rod runs on past the tilter here)
obb = adsk.core.OrientedBoundingBox3D.create(P3(-35, 0, POD.P['rod_z']), adsk.core.Vector3D.create(1, 0, 0),
                                             adsk.core.Vector3D.create(0, math.cos(math.pi / 4), math.sin(math.pi / 4)),
                                             6.0, 0.4, 0.4)
sweep = cyl((-65, 0, POD.P['rod_z']), (-8.4, 0, POD.P['rod_z']), POD.P['rod'] * math.sqrt(2) / 2)

# tilter bodies (world space: T4 occurrences are placed with transforms)
tilter = []
for i in range(root.occurrences.count):
    o = root.occurrences.item(i)
    for j in range(o.bRepBodies.count):
        b = o.bRepBodies.item(j)
        if b.name in ('Rod', 'N20 shaft', 'Magnet'):
            continue
        tilter.append(('T4 ' + b.name, tbm.copy(b)))      # occurrence proxies are already in world space

pod = [(nm, b) for g in ('Pod tray', 'Pod lid', 'Pod parts', 'Pod plug') for nm, b in groups[g]]


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


hits = []
for na, a in pod:
    for nb, b in tilter + [('rod sweep', sweep)]:
        v = vol(a, b)
        if v > 0.01:
            hits.append('%s / %s: %.2f mm3' % (na, nb, v))
for i in range(len(pod)):
    for j in range(i + 1, len(pod)):
        if {pod[i][0], pod[j][0]} in ({'RJ12 board', 'RJ12 jack'}, {'RJ12 jack', 'RJ12 plug'}, {'RJ12 plug', 'White cord'},
                                      {'DRV8833 PCB', 'DRV8833 chip'}, {'DRV8833 PCB', 'C 10uF'}, {'RJ12 board', 'RJ12 jack pins'}):
            continue
        v = vol(pod[i][1], pod[j][1])
        if v > 0.01:
            hits.append('%s / %s: %.2f mm3' % (pod[i][0], pod[j][0], v))
# the AS5600 board vs the rod sweep (existing tilter, matters only if the rod continues on this side)
as_board = next(b for n, b in tilter if n.endswith('AS5600 board'))
v_as = vol(as_board, sweep)

APPEAR = {'Pod tray': 'Plastic - Matte (White)', 'Pod lid': 'Plastic - Translucent Matte (Blue)',
          'Pod parts': 'Plastic - Matte (Black)', 'Pod plug': 'Plastic - Matte (White)'}


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


comps = {}
for g, lst in groups.items():
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = 'T4 ' + g
    comps[g] = occ.component
    ap = appearance(APPEAR[g])
    for nm, b in lst:
        bb = occ.component.bRepBodies.add(b)
        bb.name = nm
        if ap:
            bb.appearance = ap

out_stl = os.path.join(REPO, 'hardware/mechanical/stl/v0.4')
em = design.exportManager
files = []
for g, nm in (('Pod tray', 'pod_tray'), ('Pod lid', 'pod_lid')):
    path = os.path.join(out_stl, nm + '.stl')
    opt = em.createSTLExportOptions(comps[g], path)
    opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    em.execute(opt)
    files.append(path)

vp = app.activeViewport
try:
    vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
except Exception:
    pass
out = os.path.join(REPO, 'docs/renders')


def vis(hide=()):
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        o.isLightBulbOn = not any(h in o.component.name for h in hide)
    for i in range(root.occurrences.count):
        c = root.occurrences.item(i).component
        for j in range(c.bRepBodies.count):
            b = c.bRepBodies.item(j)
            if b.name.startswith('Rail'):
                b.isLightBulbOn = 'Rail' not in hide


def shot(name, orient, ortho=False):
    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.OrthographicCameraType if ortho else adsk.core.CameraTypes.PerspectiveCameraType
    cam.viewOrientation = getattr(adsk.core.ViewOrientations, orient)
    cam.isFitView = True
    vp.camera = cam
    vp.fit()
    p = os.path.join(out, name)
    vp.saveAsImageFile(p, 1800, 1000)
    return p


res = []
vis(hide=('Rail', 'Pod lid')); res.append(shot('pod-open.png', 'IsoTopLeftViewOrientation'))
vis(hide=('Rail', 'Pod lid', 'Pod plug')); res.append(shot('pod-top.png', 'TopViewOrientation', True))
vis(hide=('Rail',)); res.append(shot('pod-closed.png', 'IsoTopLeftViewOrientation'))
vis(hide=('Rail', 'Pod lid', 'Pod parts', 'Pod plug')); res.append(shot('pod-tray.png', 'IsoTopLeftViewOrientation'))
vis(); res.append(shot('pod-end.png', 'LeftViewOrientation', True))
vis(hide=('Rail',))
result = {'summary': POD.summary(), 'interference': hits or 'none',
          'AS5600 board vs rod sweep (if the rod continues on this side)': round(v_as, 3),
          'exported': files, 'renders': res}
