"""PCB v3 concept in the rail: board + every part as datasheet-sized blocks, a minimal shell (tray + lid with the round
rod groove, plug-shaped openings), rail + rod; interference check; renders. Concept only - not the case design.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_pcb_v3_concept.py --timeout 900
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
M = load_script(os.path.join(REPO, 'hardware/pcb/v3/concept.py'))
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


def rbox(x0, x1, y0, y1, z0, z1, r):
    b = uni(bx(x0 + r, x1 - r, y0, y1, z0, z1), bx(x0, x1, y0 + r, y1 - r, z0, z1))
    for xx in (x0 + r, x1 - r):
        for yy in (y0 + r, y1 - r):
            b = uni(b, cyl((xx, yy, z0), (xx, yy, z1), r))
    return b


L, (yo0, yo1), (yi0, yi1) = M.L, M.Y_OUT, M.Y_IN
fz, zl, top, zt, zb = M.FLOOR, M.ZL, M.TOP, M.ZT, M.BOARD['zb']
X0, X1 = M.X0, M.X1

parts = []
board = bx(X0, X1, M.BOARD['y0'], M.BOARD['y1'], zb, zt)
for hx, hy in M.HOLES:
    board = cut(board, cyl((hx, hy, zb - 1), (hx, hy, zt + 1), 1.6))
parts.append(('PCB v3', board))
for nm, p in M.P.items():
    if p[0] == 'box':
        parts.append((nm, bx(*p[1:])))
    elif p[0] == 'cylx':
        _, x0, x1, yc, zc, r = p
        parts.append((nm, cyl((x0, yc, zc), (x1, yc, zc), r)))
    else:
        _, xc, yc, z0, z1, r = p
        parts.append((nm, cyl((xc, yc, z0), (xc, yc, z1), r)))


def groove(off, x0, x1):
    R = M.GROOVE_R + off
    return uni(cyl((x0, 0, M.GROOVE_ZC), (x1, 0, M.GROOVE_ZC), R), bx(x0, x1, -R, R, M.GROOVE_ZC, M.GROOVE_ZC + 20))


# minimal shell: tray (bosses under the 4 holes, end-wall openings) + lid (channel round the groove)
tray = cut(rbox(0, L, yo0, yo1, 0, zl, 4.0), rbox(M.END_T, L - M.END_T, yi0, yi1, fz, zl + 1, 2.0))
for hx, hy in M.HOLES:
    tray = uni(tray, cyl((hx, hy, 0.3), (hx, hy, zb), 3.5))
for xa, xb in ((-1, M.END_T + 0.01), (L - M.END_T - 0.01, L + 1)):
    tray = cut(tray, groove(M.GROOVE_T + 0.15, xa, xb))
for nm, (ex, yc, s) in M.RJ.items():                       # plug-shaped openings (as V5)
    xa, xb = (-1, M.END_T + 0.01) if s > 0 else (L - M.END_T - 0.01, L + 1)
    tray = cut(tray, bx(xa, xb, yc - 5.08, yc + 5.08, zt + 1.45, zt + 8.8), bx(xa, xb, yc - 2.5, yc + 2.5, zt + 0.3, zt + 1.5))
tray = cut(tray, bx(-1, M.END_T + 0.01, M.UYC - 4.7, M.UYC + 4.7, zt - 0.8, zt + 2.9))          # USB-C
tray = cut(tray, cyl((-1, M.SYC, zt + 6.5), (M.END_T + 0.01, M.SYC, zt + 6.5), 3.6))             # solar jack barrel
lid = uni(rbox(0, L, yo0, yo1, zl, top, 4.0), cut(groove(M.GROOVE_T, 0, L), bx(-1, L + 1, -20, 20, top, top + 30)))
lid = cut(lid, groove(0, -1, L + 1))
rh = 55.5 / 2
rail = [('Rail floor', bx(-20, L + 20, -rh - 2, rh + 2, -2, 0)), ('Rail wall room', bx(-20, L + 20, -rh - 2, -rh, -2, 36.5)),
        ('Rail wall back', bx(-20, L + 20, rh, rh + 2, -2, 36.5)),
        ('Tilt rod sweep', cyl((-20, 0, M.ROD_Z), (L + 20, 0, M.ROD_Z), M.ROD * math.sqrt(2) / 2))]


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


SAME = (('ESP', 'ESP'), ('18650', '18650'), ('PCB v3', ''))
hits = []
allp = parts + [('Tray', tray), ('Lid', lid)] + rail
for i in range(len(allp)):
    for j in range(i + 1, len(allp)):
        a, b = allp[i][0], allp[j][0]
        if (a.startswith('ESP') and b.startswith('ESP')) or (a.startswith('18650') and b.startswith('18650')):
            continue
        if 'PCB v3' in (a, b) or (a.startswith('Rail') and b.startswith('Rail')):
            continue
        if a.startswith('Rail') or b.startswith('Rail'):
            if not ({a, b} & {'Tray', 'Lid'}):
                continue
        v = vol(allp[i][1], allp[j][1])
        if v > 0.01:
            hits.append('%s / %s: %.2f mm3' % (a, b, v))

old = []
for i in range(app.documents.count):
    d = app.documents.item(i)
    try:
        des = adsk.fusion.Design.cast(d.products.itemByProductType('DesignProductType'))
        if des and any(des.allComponents.item(k).name.startswith('V3 ') for k in range(des.allComponents.count)):
            old.append(d)
    except Exception:
        pass
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for d in old:
    d.close(False)
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


COL = [('PCB', 'Plastic - Glossy (Green)'), ('18650 cell', 'Plastic - Glossy (Blue)'), ('18650 holder', 'Plastic - Matte (Black)'),
       ('ESP32', 'Plastic - Glossy (Blue)'), ('Charger', 'Plastic - Glossy (Red)'), ('Solar', 'Plastic - Glossy (Yellow)')]
occs = {}
for g, lst in (('Parts', parts), ('Tray', [('Tray', tray)]), ('Lid', [('Lid', lid)]), ('Rail', rail)):
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = 'V3 ' + g
    occs[g] = occ
    for nm, b in lst:
        bb = occ.component.bRepBodies.add(b)
        bb.name = nm
        ap = 'Plastic - Matte (White)' if g in ('Tray', 'Lid', 'Rail') else next((v for k, v in COL if nm.startswith(k)), 'Plastic - Matte (Black)')
        a = appearance(ap)
        if a:
            bb.appearance = a
        if g == 'Rail':
            bb.opacity = 0.25
vp = app.activeViewport
out = os.path.join(REPO, 'docs/renders')


def vis(show):
    for g, o in occs.items():
        o.isLightBulbOn = g in show


def shot(name, eye, target, fit=True):
    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
    cam.eye = P3(*eye); cam.target = P3(*target)
    cam.upVector = adsk.core.Vector3D.create(0, 0, 1); cam.isFitView = fit
    vp.camera = cam
    if fit:
        vp.fit()
    p = os.path.join(out, name)
    vp.saveAsImageFile(p, 1800, 1100)
    return p


res = []
vis(('Parts',)); res.append(shot('pcb-v3-board.png', (L / 2 - 120, -140, 150), (L / 2, 0, 5)))
res.append(shot('pcb-v3-board-b.png', (L / 2 + 130, 120, 140), (L / 2, 0, 5)))
vis(('Parts', 'Tray')); res.append(shot('pcb-v3-in-tray.png', (L / 2 - 120, -140, 150), (L / 2, 0, 5)))
vis(('Parts', 'Tray', 'Lid', 'Rail')); res.append(shot('pcb-v3-in-rail.png', (-120, -110, 90), (L / 2, 0, 10)))
vis(('Tray', 'Lid', 'Parts')); res.append(shot('pcb-v3-case-end-a.png', (-140, -90, 70), (25, 0, 12), fit=False))
res.append(shot('pcb-v3-case-end-b.png', (L + 140, 90, 70), (L - 25, 0, 12), fit=False))
vis(('Parts', 'Tray', 'Lid'))
result = {'case': 'L %.1f x W %.1f x H %.1f' % (L, yo1 - yo0, top), 'interference': hits or 'none', 'renders': res}
