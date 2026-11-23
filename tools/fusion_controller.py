"""The controller box in a fresh document: the PCB's own 3D export (KiCad STEP, every part on it), tray, lid, mock-ups of the
parts the export doesn't have (RJ12 jacks, ESP32-C6, plugs, 18650, the Adafruit 6092 charger), rail + rod;
exact interference check and stays-inside check (the result's `ok` is False when either fails); print-ready STL export of tray and lid (turned top face down). Renders only with RENDERS = True.

  K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
  $K pcb export step --subst-models -f -o hardware/pcb/controller/3d/controller.step hardware/pcb/controller/controller.kicad_pcb
  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller.py --timeout 1800
"""
import math
import os

# REPO is set by fusion.py exec
KIT = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/fusion_kit.py'))
M = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/Controller/Controller.py'))
C = M.C
PREFIX = 'C5 '                         # component names (old documents are found by it)
TRAY_TEXT = 'BLINDS CONTROLLER\nV5'      # engraved under the tray
LID_TEXT = 'V5 LID'                    # engraved under the lid
STEP = os.path.join(REPO, 'hardware/pcb/controller/3d/controller.step')
STL = os.path.join(REPO, 'hardware/mechanical/stl/controller')
os.makedirs(STL, exist_ok=True)
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
    """Box centered at c (mm) with its length along unit vector u and width along w."""
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
    r = max(min(r, (x1 - x0) / 2 - 0.01, (y1 - y0) / 2 - 0.01), 0.05)
    b = uni(bx(x0 + r, x1 - r, y0, y1, z0, z1), bx(x0, x1, y0 + r, y1 - r, z0, z1))
    for xx in (x0 + r, x1 - r):
        for yy in (y0 + r, y1 - r):
            b = uni(b, cyl((xx, yy, z0), (xx, yy, z1), r))
    return b


groups = M.build(bx, cyl, cone, uni, cut, rbox, obox)
L = C['L']
rh, rt, gy = C['rail_w'] / 2, C['rail_wall'], C['groove_y']      # the rail, centered on the box (and its groove)
groups['Rail'] = [('Rail floor', bx(-20, L + 20, gy - rh - rt, gy + rh + rt, -rt, 0)),
                  ('Rail wall room', bx(-20, L + 20, gy - rh - rt, gy - rh, -rt, C['rail_h'])),
                  ('Rail wall back', bx(-20, L + 20, gy + rh, gy + rh + rt, -rt, C['rail_h'])),
                  ('Rail lip room', bx(-20, L + 20, gy - rh, gy - rh + C['lip_in'], C['rail_h'] - C['lip_h'], C['rail_h'])),
                  ('Rail lip back', bx(-20, L + 20, gy + rh - C['lip_in'], gy + rh, C['rail_h'] - C['lip_h'], C['rail_h'])),
                  ('Tilt rod sweep', cyl((-20, gy, C['rod_z']), (L + 20, gy, C['rod_z']), C['rod'] * math.sqrt(2) / 2))]
groups['Screws'] = [('M3x%.0f %d' % (l, k), uni(cone((x, y, C['floor_z']), 2.95, (x, y, C['floor_z'] + 1.6), 1.45),
                                                 cyl((x, y, C['floor_z'] + 1.55), (x, y, C['floor_z'] + l), 1.45)))
                    for k, (x, y, l) in enumerate(M.SCREWS)]

# ------------------------------------------------------------------ fresh document, PCB export placed in the box
design = KIT.fresh_document(app, 'controller', old_prefixes=(PREFIX,))
root = design.rootComponent
im = app.importManager
im.importToTarget(im.createSTEPImportOptions(STEP), root)
pcb_occ = root.occurrences.item(root.occurrences.count - 1)
pcb_occ.component.name = PREFIX + 'PCB (KiCad export)'
# STEP (x, y, z) -> box: X = -y + pcb_x, Y = x + pcb_y, Z = z + zb  (a quarter turn about Z)
m = adsk.core.Matrix3D.create()
m.setWithCoordinateSystem(P3(C['pcb_x'], C['pcb_y'], C['zb']), adsk.core.Vector3D.create(0, 1, 0),
                          adsk.core.Vector3D.create(-1, 0, 0), adsk.core.Vector3D.create(0, 0, 1))
pcb_occ.transform2 = m
notes = []


def proxies(o):
    yield o
    for k in range(o.childOccurrences.count):
        yield from proxies(o.childOccurrences.item(k))


def box_y(o):
    bb = o.boundingBox
    return (bb.minPoint.y + bb.maxPoint.y) * 5


natives = {pcb_occ.component.occurrences.item(k).name: pcb_occ.component.occurrences.item(k)
           for k in range(pcb_occ.component.occurrences.count)}
for k in range(pcb_occ.childOccurrences.count):
    o = pcb_occ.childOccurrences.item(k)
    n = natives.get(o.name)
    if o.name.startswith('Fuse'):
        n.isLightBulbOn = False                              # all three fuses are folded (mock-ups in Parts)
        notes.append('fuse folded (%s)' % o.name)
    elif o.name.startswith('CP_Radial'):
        n.isLightBulbOn = False                              # generic short model: replaced by the 8 x 11.5 mock-up
        notes.append('C9 shown at its real 11.5 mm height')

step_bodies = []                                             # (name, temp body in box coordinates)
for o in proxies(pcb_occ):
    if not o.isLightBulbOn or (o != pcb_occ and not o.isVisible):
        continue
    for j in range(o.bRepBodies.count):
        b = o.bRepBodies.item(j)
        if b.isVisible:
            step_bodies.append(('PCB:' + o.name, tbm.copy(b)))
# the board's jack edge is trimmed by hand, 3-4 mm. Check the worst case for end wall A: the shortest trim
for n, b in step_bodies:
    if 'controller_PCB' in n or n == 'PCB:board':
        tbm.booleanOperation(b, bx(C['pcb_x'] - 5, C['pcb_x'] + C['pcb_trim'][0], -40, 40, -5, 40), B.DifferenceBooleanType)
board_bb = [b for n, b in step_bodies if 'controller_PCB' in n or n == 'PCB:board']
bb0 = board_bb[0].boundingBox if board_bb else None

# ------------------------------------------------------------------ interference
own = [(g, nm, b) for g in ('Tray', 'Lid', 'Parts', 'Screws', 'Rail', 'Wires') for nm, b in groups[g]]
own += [('PCB', nm, b) for nm, b in step_bodies]


def vol(a, b):
    A, Bb = a.boundingBox, b.boundingBox
    if (A.maxPoint.x <= Bb.minPoint.x or Bb.maxPoint.x <= A.minPoint.x or A.maxPoint.y <= Bb.minPoint.y or
            Bb.maxPoint.y <= A.minPoint.y or A.maxPoint.z <= Bb.minPoint.z or Bb.maxPoint.z <= A.minPoint.z):
        return 0.0
    cc = tbm.copy(a)
    tbm.booleanOperation(cc, tbm.copy(b), B.IntersectionBooleanType)
    try:
        return cc.volume * 1000 if cc.faces.count else 0.0
    except Exception:
        return 0.0


MATES = [('Harness', 'Charger pad'), ('Charger screw', 'Tray'), ('J4 battery plug', 'B2B_XH'), ('J5 charger plug', 'B6B_XH'), ('F1 folded', 'controller_PCB'), ('F2 folded', 'controller_PCB'), ('F3 folded', 'controller_PCB'),
         ('ESP32-C6 spacer', 'PinSocket_1x10'), ('RJ12', 'controller_PCB'), ('RJ12', 'PCB:board'),
         ('Screws', 'controller_PCB'), ('ESP32-C6', 'ESP32-C6'),
         ('Charger', 'Charger'), ('J8', 'J8'), ('RJ12 1', 'RJ12 1'), ('RJ12 2', 'RJ12 2'), ('RJ12 3', 'RJ12 3'),
         ('J4 battery plug', 'J4 battery plug'), ('J5 charger plug', 'J5 charger plug')]


def mated(a, b):
    for p, q in MATES:
        if (a.startswith(p) and q in b) or (b.startswith(p) and q in a):
            return True
    return False


hits = []
for i in range(len(own)):
    for j in range(i + 1, len(own)):
        gi, ni, bi = own[i]
        gj, nj, bj = own[j]
        if gi == gj and gi in ('Tray', 'Lid', 'Screws', 'Rail', 'PCB'):
            continue
        if 'Rail' in (gi, gj) and ({gi, gj} & {'Parts', 'PCB', 'Screws', 'Wires'}):
            continue
        if mated(ni, nj) or ('Screws' in (gi, gj) and ('PCB' in (gi, gj) or 'Lid' in (gi, gj))):
            continue
        v = vol(bi, bj)
        if v > 0.01:
            cc = tbm.copy(bi)
            tbm.booleanOperation(cc, tbm.copy(bj), B.IntersectionBooleanType)
            q = cc.boundingBox
            hits.append('%s / %s: %.2f mm3 at X %.1f-%.1f Y %.1f-%.1f Z %.1f-%.1f' % (
                ni, nj, v, q.minPoint.x * 10, q.maxPoint.x * 10, q.minPoint.y * 10, q.maxPoint.y * 10, q.minPoint.z * 10, q.maxPoint.z * 10))


# stays-inside check: no printed part, component, screw or wire may reach outside the box's outside shape
# (the solar cable is meant to: it leaves through its opening)
pokes = KIT.stays_inside(tbm, [(nm, b) for g, nm, b in own if g != 'Rail'], C['outline'], allow=('Solar cable',))


# clearances to the lid (closest approach upward) for the tight spots
def gap_up(name_part):
    lid = groups['Lid'][0][1]
    res = []
    for g, nm, b in own:
        if name_part in nm and g in ('Parts', 'PCB', 'Wires'):
            for dz in (0.2, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0, 3.0):
                t = adsk.core.Matrix3D.create()
                t.translation = adsk.core.Vector3D.create(0, 0, dz / 10)
                cpy = tbm.copy(b)
                tbm.transform(cpy, t)
                if vol(cpy, lid) > 0.001:
                    res.append('%s: %.1f' % (nm, dz))
                    break
            else:
                res.append('%s: >3' % nm)
    return res


gaps = gap_up('Harness') + gap_up('Cell lead') + gap_up('ESP32-C6') + gap_up('RJ12 2 jack') + gap_up('C9') + gap_up(' folded') + gap_up('Charger terminal') + gap_up('Charger screw') + gap_up('J4') + gap_up('18650')

# ------------------------------------------------------------------ components
APPEAR = {'Tray': 'Plastic - Matte (White)', 'Lid': 'Plastic - Matte (White)', 'Parts': 'Plastic - Matte (Black)',
          'Screws': 'Steel - Satin', 'Rail': 'Plastic - Matte (White)', 'Wires': 'Plastic - Glossy (Red)'}


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


COLOR = {'ESP32-C6 board': 'Plastic - Glossy (Blue)', '18650': 'Plastic - Glossy (Blue)', 'Charger board': 'Plastic - Glossy (Blue)'}
comps, occs = {}, {}
for g, lst in groups.items():
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = PREFIX + g
    comps[g], occs[g] = occ.component, occ
    ap = appearance(APPEAR[g])
    for nm, b in lst:
        if b is None:
            continue
        bb = occ.component.bRepBodies.add(b)
        bb.name = nm
        a2 = appearance(COLOR.get(nm, APPEAR[g]))
        if a2:
            bb.appearance = a2
occs['PCB'] = pcb_occ


def on_outline(x, y):
    L_, ylo, yhi, r = C['L'] / 10, C['room_out'] / 10, C['out_hi'] / 10, C['corner_r'] / 10
    a0_ = C['a0'] / 10
    if (abs(y - ylo) < 0.003 or abs(y - yhi) < 0.003) and a0_ + r - 0.003 <= x <= L_ - r + 0.003:
        return True
    if (abs(x - a0_) < 0.003 or abs(x - L_) < 0.003) and ylo + r - 0.003 <= y <= yhi - r + 0.003:
        return True
    for cx in (a0_ + r, L_ - r):
        for cy in (yhi - r, ylo + r):
            if abs(math.hypot(x - cx, y - cy) - r) < 0.003 and ((x < cx) == (cx < L_ / 2)) and ((y > cy) == (cy > (ylo + yhi) / 2)):
                return True
    return False


def round_edges(comp, z_big, r_big, z_small, r_small, groove=False):
    body = comp.bRepBodies.item(0)
    sets = {r: adsk.core.ObjectCollection.create() for r in (r_big, r_small) if r is not None}
    for e in body.edges:
        a, b = e.startVertex, e.endVertex
        if a is None or b is None:
            continue
        a, b = a.geometry, b.geometry
        ev = e.evaluator
        ext = ev.getParameterExtents()
        mid = ev.getPointAtParameter((ext[1] + ext[2]) / 2)[1]
        for zz, rr in ((z_big, r_big), (z_small, r_small)):
            if rr is None:
                continue
            if abs(a.z - zz / 10) < 0.002 and abs(b.z - zz / 10) < 0.002:
                if on_outline(mid.x, mid.y):
                    sets[rr].add(e)
                elif groove and zz == z_big and isinstance(e.geometry, adsk.core.Line3D) and \
                        abs(abs(mid.y - C['groove_y'] / 10) - C['groove_top_hw'] / 10) < 0.002:
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


# no rounding where the lid meets the tray (it shows as a groove round the box): only the bottom and top edges
# (the long edges are beveled in Controller.py; the tray's end edges get a small round that ends on the bevels)
fil = {'Tray': round_edges(comps['Tray'], C['floor_z'], 0.8, C['zl'], None),
       'Lid': round_edges(comps['Lid'], C['top'], C['edge_r'], C['zl'], None, groove=True)}


def engrave(comp, z, lines, xc, yc, w, h, size=0.32):
    """Engrave text 0.4 deep into the body's downward-facing face at height z, sketched ON that face, so it reads
    right when you look at that face (from below)."""
    try:
        body = comp.bRepBodies.item(0)
        face = None
        for f in body.faces:
            g = f.geometry
            if isinstance(g, adsk.core.Plane) and abs(g.origin.z * 10 - z) < 0.01 and f.evaluator.getNormalAtPoint(f.pointOnFace)[1].z < -0.99:
                ok, prm = f.evaluator.getParameterAtPoint(P3(xc, yc, z))
                if ok and f.evaluator.isParameterOnFace(prm):
                    face = f
                    break
        if face is None:
            return 'failed: no face at the text'
        sk = comp.sketches.add(face)
        a = sk.modelToSketchSpace(P3(xc - w / 2, yc - h / 2, z))
        b = sk.modelToSketchSpace(P3(xc + w / 2, yc + h / 2, z))
        ti = sk.sketchTexts.createInput2(lines, size)
        ti.setAsMultiLine(adsk.core.Point3D.create(min(a.x, b.x), min(a.y, b.y), 0),
                          adsk.core.Point3D.create(max(a.x, b.x), max(a.y, b.y), 0),
                          adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
                          adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
        tx = sk.sketchTexts.add(ti)
        v0 = body.volume
        for d in (adsk.fusion.ExtentDirections.NegativeExtentDirection, adsk.fusion.ExtentDirections.PositiveExtentDirection):
            try:
                ei = comp.features.extrudeFeatures.createInput(tx, adsk.fusion.FeatureOperations.CutFeatureOperation)
                ei.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(0.04)), d)
                ei.participantBodies = [body]
                comp.features.extrudeFeatures.add(ei)
                if comp.bRepBodies.item(0).volume < v0 - 1e-6:
                    return 'ok'
            except Exception:
                pass
        return 'failed: cut did not remove material'
    except Exception as ex:
        return 'failed: %s' % str(ex)[:120]


eng = {'Tray': engrave(comps['Tray'], C['floor_z'], TRAY_TEXT, L / 2, 0, 110, 18, 0.6),
       'Lid': engrave(comps['Lid'], C['zl'], LID_TEXT, 100, -17, 30, 10, 0.5)}
files = []
# print files, each lying the way it prints with its lowest face on Z 0: tray floor down, lid turned over (top face down)
flip = adsk.core.Matrix3D.create()
flip.setToRotation(math.pi, adsk.core.Vector3D.create(1, 0, 0), P3(0, 0, C['top'] / 2))      # lid: top face to Z 0
lid_print = tbm.copy(comps['Lid'].bRepBodies.item(0))
tbm.transform(lid_print, flip)
main_doc = app.activeDocument
for nm, body in (('controller_tray', tbm.copy(comps['Tray'].bRepBodies.item(0))), ('controller_lid', lid_print)):
    cdoc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)      # its own throwaway document
    cdes = adsk.fusion.Design.cast(app.activeProduct)
    cdes.designType = adsk.fusion.DesignTypes.DirectDesignType
    cdes.rootComponent.bRepBodies.add(body)
    path = os.path.join(STL, nm + '.stl')
    opt = cdes.exportManager.createSTLExportOptions(cdes.rootComponent, path)
    opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    cdes.exportManager.execute(opt)
    files.append(path)
    cdoc.close(False)
    main_doc.activate()

# ------------------------------------------------------------------ renders
ui.activeSelections.clear()
KIT.hide_helpers(design)
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
    mm = adsk.core.Matrix3D.create()
    mm.translation = adsk.core.Vector3D.create(0, 0, dz / 10.0)
    occs[g].transform2 = mm


RENDERS = False   # the doc renders: turn on only when the pictures need refreshing (each run is slower with them)


def shot(name, eye, target=(L / 2, 0, 12), fit=True):
    if not RENDERS:
        return None
    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
    cam.eye = P3(*eye)
    cam.target = P3(*target)
    cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
    cam.isFitView = fit
    vp.camera = cam
    if fit:
        vp.fit()
    p = os.path.join(out, name)
    vp.saveAsImageFile(p, 1800, 1100)
    return p


res = []
vis(hide=('Rail', 'Lid', 'Screws')); res.append(shot('controller-open.png', (L / 2 - 170, -190, 200)))
res.append(shot('controller-open-b.png', (L / 2 + 180, 160, 200)))
res.append(shot('controller-top.png', (L / 2, 0, 320)))
vis(hide=('Rail', 'Lid', 'Screws', 'Wires')); res.append(shot('controller-bay.png', (L + 60, 90, 120), (145, 5, 8)))
move('Lid', 45)
vis(hide=('Rail', 'Wires')); res.append(shot('controller-exploded.png', (L / 2 - 180, -200, 170)))
move('Lid', 0)
vis(hide=('Rail', 'Wires')); res.append(shot('controller-closed.png', (-130, -170, 120)))
res.append(shot('controller-end-b.png', (L + 150, -95, 70), (L - 25, 0, 14), fit=False))
res.append(shot('controller-under.png', (L / 2 - 120, -150, -160)))
cam = vp.camera
cam.cameraType = adsk.core.CameraTypes.OrthographicCameraType
cam.eye = P3(92, 9, -300)
cam.target = P3(92, 9, 0)
cam.upVector = adsk.core.Vector3D.create(0, 1, 0)
cam.isFitView = False
vp.camera = cam
cam = vp.camera
cam.viewExtents = 8.0
vp.camera = cam
if RENDERS:
    res.append(os.path.join(out, 'controller-bottom-text.png')); vp.saveAsImageFile(res[-1], 1400, 800)
cam.eye = P3(146, 0, 220)
cam.target = P3(L, 0, 10)
cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
cam.eye = P3(L + 80, 0, 12)
cam.target = P3(L, 0, 12)
cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
cam.viewExtents = 5.0
vp.camera = cam
if RENDERS:
    res.append(os.path.join(out, 'controller-end-b-flat.png')); vp.saveAsImageFile(res[-1], 1400, 800)
res.append(shot('controller-end-a.png', (-150, -95, 70), (25, 0, 14), fit=False))
vis(hide=('Rail', 'Wires', 'Tray', 'PCB', 'Parts', 'Screws')); res.append(shot('controller-lid-under.png', (L / 2 - 100, -140, -170)))
vis(); res.append(shot('controller-in-rail.png', (-140, -90, 90)))
vis(hide=('Rail', 'Wires')); res.append(shot('controller-port.png', (-45, -40, 22), (0, -10, 10), fit=False))
vis(hide=('Lid', 'Rail', 'Wires', 'Screws', 'PCB', 'Parts')); res.append(shot('controller-tray.png', (L / 2 - 150, -170, 200)))


def only(prefixes):
    """Show just the bodies whose names start with one of the prefixes (Parts / Wires); hide everything else."""
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        o.isLightBulbOn = o.component.name in (PREFIX + 'Parts', PREFIX + 'Wires')
        for j in range(o.component.bRepBodies.count):
            b = o.component.bRepBodies.item(j)
            b.isLightBulbOn = b.name.startswith(prefixes)


only(('Charger', 'Harness')); res.append(shot('controller-charger-sub.png', (L - 130, -150, 140), (146, 10, 8)))
for i in range(root.occurrences.count):
    o = root.occurrences.item(i)
    for j in range(o.component.bRepBodies.count):
        o.component.bRepBodies.item(j).isLightBulbOn = True
vis(hide=('Rail', 'Lid', 'Screws')); res.append(shot('controller-bay-top.png', (146, 0, 260), (146, 0, 0)))
vis(hide=('Rail', 'Wires'))
failures = (['interference: %d pairs' % len(hits)] if hits else []) + (['pokes out of the box: %d bodies' % len(pokes)] if pokes else [])
result = {'ok': not failures, 'failures': failures, 'pokes out of the box': pokes or 'none', 'box': 'L %.1f x W %.1f x H %.1f' % (C['box_l'], C['out_hi'] - C['room_out'], C['top']), 'notes': notes,
          'pcb board bbox (mm)': [round(v * 10, 2) for v in (bb0.minPoint.x, bb0.maxPoint.x, bb0.minPoint.y, bb0.maxPoint.y, bb0.minPoint.z, bb0.maxPoint.z)] if bb0 else None,
          'step bodies': len(step_bodies), 'interference': hits or 'none', 'room above (mm, first contact with lid)': gaps,
          'wire lengths (mm)': C.get('wire_lengths'), 'fillets': fil, 'engraving': eng, 'exported': files, 'renders': [r for r in res if r]}
