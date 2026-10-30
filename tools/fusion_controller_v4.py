"""ControllerV4 in a fresh document: tray, lid, every part, rail + rod; exact interference check; STL export of tray +
lid; renders with sketches hidden.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v4.py --timeout 1200
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
M = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/ControllerV4/ControllerV4.py'))
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


def rbox(x0, x1, y0, y1, z0, z1, r):
    """Box with its four vertical edges rounded (r)."""
    r = max(min(r, (x1 - x0) / 2 - 0.01, (y1 - y0) / 2 - 0.01), 0.05)
    b = uni(bx(x0 + r, x1 - r, y0, y1, z0, z1), bx(x0, x1, y0 + r, y1 - r, z0, z1))
    for xx in (x0 + r, x1 - r):
        for yy in (y0 + r, y1 - r):
            b = uni(b, cyl((xx, yy, z0), (xx, yy, z1), r))
    return b


groups = M.build(tbm, bx, cyl, cone, uni, cut, rbox)
L = C['L']
rh, rt = C['rail_w'] / 2, C['rail_wall']
groups['Rail'] = [('Rail floor', bx(-20, L + 20, -rh - rt, rh + rt, -rt, 0)),
                  ('Rail wall room', bx(-20, L + 20, -rh - rt, -rh, -rt, C['rail_h'])),
                  ('Rail wall back', bx(-20, L + 20, rh, rh + rt, -rt, C['rail_h'])),
                  ('Rail lip room', bx(-20, L + 20, -rh, -rh + C['lip_in'], C['rail_h'] - C['lip_h'], C['rail_h'])),
                  ('Rail lip back', bx(-20, L + 20, rh - C['lip_in'], rh, C['rail_h'] - C['lip_h'], C['rail_h'])),
                  ('Tilt rod sweep', cyl((-20, 0, C['rod_z']), (L + 20, 0, C['rod_z']), C['rod'] * math.sqrt(2) / 2))]
groups['Screws'] = [('M3x8', uni(cone((x, y, C['top']), 2.95, (x, y, C['top'] - 1.45), 1.5),
                                 cyl((x, y, C['top'] - 1.4), (x, y, C['top'] - 8), 1.45))) for x, y in M.PILLARS]

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
        if {ni, nj} == {'USB-C board', 'USB-C socket'}:
            continue
        if same_part(ni, nj) or ('Perfboard' in (ni, nj) and ('header' in ni + nj or 'pins' in ni + nj or 'tape' in ni + nj)):
            continue
        if gi == 'Rail' and gj == 'Rail':
            continue
        v = vol(bi, bj)
        if v > 0.01:
            hits.append('%s / %s: %.2f mm3' % (ni, nj, v))

# USB-C board fitting: it slides in flat along its posts, socket first into the window, front edge into the wall pocket
tray_b = groups['Tray'][0][1]
usb = [b for nm, b in groups['Parts'] if nm in ('USB-C board', 'USB-C socket')]
slide = {}
for d in (0, 0.5, 1, 1.5, 2, 3, 5):
    t = adsk.core.Matrix3D.create()
    t.translation = adsk.core.Vector3D.create(-d / 10, 0, 0)
    vs = []
    for b in usb:
        cpy = tbm.copy(b)
        tbm.transform(cpy, t)
        vs.append(round(vol(cpy, tray_b), 2))
    slide[d] = vs

old = []
for i in range(app.documents.count):
    d = app.documents.item(i)
    try:
        des = adsk.fusion.Design.cast(d.products.itemByProductType('DesignProductType'))
        if des and any(des.allComponents.item(k).name.startswith('C4 ') for k in range(des.allComponents.count)):
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
    occ.component.name = 'C4 ' + g
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


def on_outline(x, y):
    """Is (x, y) (cm) on the box's outer rounded-rectangle outline?"""
    L_, hw, r = C['L'] / 10, C['half_w'] / 10, C['corner_r'] / 10
    if abs(abs(y) - hw) < 0.003 and r - 0.003 <= x <= L_ - r + 0.003:
        return True
    if (abs(x) < 0.003 or abs(x - L_) < 0.003) and abs(y) <= hw - r + 0.003:
        return True
    for cx in (r, L_ - r):
        for cy in (hw - r, -(hw - r)):
            if abs(math.hypot(x - cx, y - cy) - r) < 0.003 and abs(x - cx) > 0 and \
                    ((x < cx) == (cx < L_ / 2)) and ((y > cy) == (cy > 0)):
                return True
    return False


def round_edges(comp, z_big, r_big, z_small, r_small, groove=False):
    """Fillet the outline edges at height z_big (r_big) and z_small (r_small, the parting-line reveal), plus the groove's
    two top edges on the lid."""
    body = comp.bRepBodies.item(0)
    sets = {r_big: adsk.core.ObjectCollection.create(), r_small: adsk.core.ObjectCollection.create()}
    for e in body.edges:
        a, b = e.startVertex, e.endVertex
        if a is None or b is None:
            continue
        a, b = a.geometry, b.geometry
        mid = e.evaluator.getPointAtParameter((e.evaluator.getParameterExtents()[1] + e.evaluator.getParameterExtents()[2]) / 2)[1]
        for zz, rr in ((z_big, r_big), (z_small, r_small)):
            if abs(a.z - zz / 10) < 0.002 and abs(b.z - zz / 10) < 0.002:
                if on_outline(mid.x, mid.y):
                    sets[rr].add(e)
                elif groove and zz == z_big and isinstance(e.geometry, adsk.core.Line3D) and \
                        abs(abs(mid.y) - C['groove_hw'] / 10) < 0.002:
                    sets[rr].add(e)
    done = {}
    for rr, col in sets.items():
        if col.count == 0:
            continue
        try:
            inp = comp.features.filletFeatures.createInput()
            inp.addConstantRadiusEdgeSet(col, adsk.core.ValueInput.createByReal(rr / 10), True)
            comp.features.filletFeatures.add(inp)
            done[rr] = col.count
        except Exception as ex:
            done[rr] = 'failed: %s' % str(ex)[:80]
    return done


fil = {'Tray': round_edges(comps['Tray'], C['floor_z'], C['edge_r'], C['zl'], 0.6),
       'Lid': round_edges(comps['Lid'], C['top'], C['edge_r'], C['zl'], 0.6, groove=True)}
files = []
em = design.exportManager
for g, nm in (('Tray', 'controller_v4_tray'), ('Lid', 'controller_v4_lid')):
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
vis(hide=('Rail', 'Lid', 'Screws')); res.append(shot('ctrl-v4-open.png', (L / 2 - 160, -170, 190)))
res.append(shot('ctrl-v4-open-b.png', (L / 2 + 170, 150, 190)))
move('Lid', 40); move('Screws', 40)
vis(hide=('Rail',)); res.append(shot('ctrl-v4-exploded.png', (L / 2 - 170, -190, 160)))
move('Lid', 0); move('Screws', 0)
vis(hide=('Rail',)); res.append(shot('ctrl-v4-closed.png', (-120, -160, 120)))
res.append(shot('ctrl-v4-end-b.png', (L + 150, 60, 60)))
vis(); res.append(shot('ctrl-v4-end-a.png', (-200, 0, 20), (0, 0, 18)))
vis(hide=('Lid', 'Screws', 'Tray', 'Rail')); res.append(shot('ctrl-v4-boards-top.png', (L / 2, 0, 300)))
vis(); res.append(shot('ctrl-v4-in-rail.png', (-140, -90, 90)))
vis(hide=('Rail',))
result = {'usb slide-in (mm back from home: [board, socket] overlap with the tray)': slide, 'box': 'L %.1f x W %.1f x H %.1f' % (L, 2 * C['half_w'], C['top']), 'interference': hits or 'none',
          'fillets': fil, 'exported': files, 'renders': res}
