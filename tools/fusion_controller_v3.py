"""Fit study for the controller PCB v3 in a fresh Fusion document: the mock-up board, cell, contacts, tray, lid, rail
and rod; exact interference check, stays-inside check, plug-seating check, clearances; pictures in docs/renders.
No print files: the box is finished once the real board exists.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v3.py --timeout 1800

Set PORTS below (3 = full board, 1 = end section sawn off) and SHOTS (False = checks only).
"""
import math
import os

PORTS = 3
SHOTS = True

# REPO, app, ui, adsk and load_script are set by fusion.py exec
KIT = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/fusion_kit.py'))
M = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/ControllerV3/ControllerV3.py'))
C = M.params(PORTS)
PREFIX = 'C3 '
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
    r = max(min(r, (x1 - x0) / 2 - 0.01, (y1 - y0) / 2 - 0.01), 0.05)
    b = uni(bx(x0 + r, x1 - r, y0, y1, z0, z1), bx(x0, x1, y0 + r, y1 - r, z0, z1))
    for xx in (x0 + r, x1 - r):
        for yy in (y0 + r, y1 - r):
            b = uni(b, cyl((xx, yy, z0), (xx, yy, z1), r))
    return b


groups = M.build(bx, cyl, cone, uni, cut, rbox, obox, C)
outline = groups.pop('outline')
L = C['L']
rh, rt, gy = M.FIT.RAIL_W / 2, M.FIT.RAIL_WALL, C['groove_y']
RH = M.FIT.RAIL_H
groups['Rail'] = [('Rail floor', bx(-20, L + 20, gy - rh - rt, gy + rh + rt, -rt, 0)),
                  ('Rail wall room', bx(-20, L + 20, gy - rh - rt, gy - rh, -rt, RH)),
                  ('Rail wall back', bx(-20, L + 20, gy + rh, gy + rh + rt, -rt, RH)),
                  ('Rail lip room', bx(-20, L + 20, gy - rh, gy - rh + M.FIT.LIP_IN, RH - M.FIT.LIP_H, RH)),
                  ('Rail lip back', bx(-20, L + 20, gy + rh - M.FIT.LIP_IN, gy + rh, RH - M.FIT.LIP_H, RH)),
                  ('Tilt rod sweep', cyl((-20, gy, M.FIT.ROD_Z), (L + 20, gy, M.FIT.ROD_Z), M.FIT.ROD_CORNER_R))]

design = KIT.fresh_document(app, 'controller-v3', old_prefixes=(PREFIX,))
root = design.rootComponent

own = [(g, nm, b) for g in ('Tray', 'Lid', 'Board', 'Parts', 'Screws', 'Rail', 'Plugs') for nm, b in groups[g]]


def vol(a, b):
    A, Bb = a.boundingBox, b.boundingBox
    if (A.maxPoint.x <= Bb.minPoint.x or Bb.maxPoint.x <= A.minPoint.x or A.maxPoint.y <= Bb.minPoint.y or
            Bb.maxPoint.y <= A.minPoint.y or A.maxPoint.z <= Bb.minPoint.z or Bb.maxPoint.z <= A.minPoint.z):
        return None
    cc = tbm.copy(a)
    tbm.booleanOperation(cc, tbm.copy(b), B.IntersectionBooleanType)
    try:
        return cc if cc.faces.count and cc.volume * 1000 > 0.01 else None
    except Exception:
        return None


# parts that are meant to touch or pass through each other
MATES = [('RJ12 1', 'RJ12 1'), ('RJ12 2', 'RJ12 2'), ('RJ12 3', 'RJ12 3'), ('ESP', 'ESP'),
         ('M3', 'Board'), ('M3', 'Lid'), ('M3', 'Tray'), ('USB-C plug', 'USB-C socket'), ('Solar plug', 'Solar jack'),
         ('ESP flashing plug', 'Lid')]         # that cable is only plugged in with the lid off


def mated(a, b):
    return any((a.startswith(p) and b.startswith(q)) or (b.startswith(p) and a.startswith(q)) for p, q in MATES)


hits = []
for i in range(len(own)):
    for j in range(i + 1, len(own)):
        gi, ni, bi = own[i]
        gj, nj, bj = own[j]
        if gi == gj and gi in ('Tray', 'Lid', 'Screws', 'Rail', 'Board'):
            continue
        if 'Rail' in (gi, gj) and ({gi, gj} & {'Parts', 'Board', 'Screws', 'Plugs'}):
            continue
        if mated(ni, nj):
            continue
        cc = vol(bi, bj)
        if cc:
            q = cc.boundingBox
            hits.append('%s / %s: %.2f mm3 at X %.1f-%.1f Y %.1f-%.1f Z %.1f-%.1f' % (
                ni, nj, cc.volume * 1000, q.minPoint.x * 10, q.maxPoint.x * 10, q.minPoint.y * 10, q.maxPoint.y * 10, q.minPoint.z * 10, q.maxPoint.z * 10))

pokes = KIT.stays_inside(tbm, [(nm, b) for g, nm, b in own if g not in ('Rail', 'Plugs')], outline, allow=('RJ12',))
# the jacks' fronts are flush inside their openings: check them against the box's outline grown by nothing along X only
for g, nm, b in own:
    if nm.startswith('RJ12') and 'jack' in nm:
        q = b.boundingBox
        if q.minPoint.x * 10 < -0.001 or q.maxPoint.x * 10 > L + 0.001:
            pokes.append('%s reaches past the end wall' % nm)


def gap_up(name_part):
    lid = groups['Lid'][0][1]
    res = []
    for g, nm, b in own:
        if name_part in nm and g in ('Parts', 'Board'):
            for dz in (0.2, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0, 3.0):
                t = adsk.core.Matrix3D.create()
                t.translation = adsk.core.Vector3D.create(0, 0, dz / 10)
                cpy = tbm.copy(b)
                tbm.transform(cpy, t)
                if vol(cpy, lid):
                    res.append('%s: under %.1f' % (nm, dz))
                    break
            else:
                res.append('%s: over 3' % nm)
    return res


gaps = (gap_up('18650') + gap_up('ESP pin tips') + gap_up('RJ12 3 jack') + gap_up('RJ12 1 jack') + gap_up('Cell contact') + gap_up('C 470uF')
        + gap_up('fuse') + gap_up('JST'))

# the rod's sweep against the lid: the groove must clear it
rod = [b for g, nm, b in own if nm == 'Tilt rod sweep'][0]
rod_hit = vol(rod, groups['Lid'][0][1]) or vol(rod, groups['Tray'][0][1])

# printed parts must each be one piece
lumps = {g: groups[g][0][1].lumps.count for g in ('Tray', 'Lid')}


# ------------------------------------------------------------------ can the board be put in?
# The assembly path, walked backwards from seated: tilt end B up about the foot of end wall A, slide the board back out
# of wall A along its own tilted length, then lift it clear. A search over (tilt, slide) finds a way or reports none.
def path_check():
    tray = groups['Tray'][0][1]
    moving = [b for g, nm, b in own if g in ('Board', 'Parts') and '18650' not in nm]
    pivot = P3(C['ia'], 0, C['zt'])

    def pose(theta, d, lift=0.0):
        m = adsk.core.Matrix3D.create()
        m.setToRotation(-math.radians(theta), adsk.core.Vector3D.create(0, 1, 0), pivot)
        t = adsk.core.Matrix3D.create()
        t.translation = adsk.core.Vector3D.create(d * math.cos(math.radians(theta)) / 10, 0, (d * math.sin(math.radians(theta)) + lift) / 10)
        m.transformBy(t)
        return m

    def free(theta, d, lift=0.0):
        m = pose(theta, d, lift)
        for b in moving:
            cpy = tbm.copy(b)
            tbm.transform(cpy, m)
            if vol(cpy, tray):
                return False
        return True

    TS, DS, LS = 0.5, 0.25, 0.25          # steps: tilt (deg), slide (mm), lift (mm)
    if not free(0, 0):
        return 'the seated board touches the tray'
    start = (0, 0, 0)
    seen, queue = {start}, [start]
    while queue:
        it, id_, il = queue.pop(0)
        theta, d, lf = it * TS, id_ * DS, il * LS
        if d >= 2.5 and all(free(theta, d, lf + lift) for lift in (1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 40)):
            return 'ok: end B up %.1f deg, lifted %.2f mm, slid %.2f mm out of end wall A, then lifted clear' % (theta, lf, d)
        for nt, nd, nl in ((it + 1, id_, il), (it - 1, id_, il), (it, id_ + 1, il), (it, id_ - 1, il), (it, id_, il + 1), (it, id_, il - 1)):
            if 0 <= nt <= 24 and 0 <= nd <= 16 and 0 <= nl <= 4 and (nt, nd, nl) not in seen:
                seen.add((nt, nd, nl))
                if free(nt * TS, nd * DS, nl * LS):
                    queue.append((nt, nd, nl))
    names = [nm for g, nm, b in own if g in ('Board', 'Parts') and '18650' not in nm]
    why = []
    for th, d, lf in ((0, 0, 0.25), (0.5, 0, 0.25), (1, 0, 0.25), (2, 0, 0.5), (2, 0.5, 0.5), (2.5, 1.0, 0.5), (3, 2.5, 0.5), (3, 2.5, 3)):
        m = pose(th, d, lf)
        bad = []
        for nm, b in zip(names, moving):
            cpy = tbm.copy(b)
            tbm.transform(cpy, m)
            if vol(cpy, tray):
                bad.append(nm)
        why.append('tilt %.1f slide %.2f lift %.2f: %s' % (th, d, lf, ', '.join(bad) or 'free'))
    return 'no way found to put the board in; ' + ' | '.join(why)


path = path_check()

# ------------------------------------------------------------------ components
APPEAR = {'Tray': 'Plastic - Matte (White)', 'Lid': 'Plastic - Matte (White)', 'Parts': 'Plastic - Matte (Black)', 'Board': 'Plastic - Matte (Green)',
          'Screws': 'Steel - Satin', 'Rail': 'Plastic - Matte (White)', 'Plugs': 'Plastic - Matte (Gray)'}
COLOR = {'ESP32-C6 board': 'Plastic - Glossy (Blue)', '18650 cell': 'Plastic - Glossy (Blue)', 'Cell contact +': 'Steel - Satin', 'Cell contact -': 'Steel - Satin',
         'USB-C socket': 'Steel - Satin'}


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


occs = {}
for g in ('Tray', 'Lid', 'Board', 'Parts', 'Screws', 'Rail', 'Plugs'):
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = PREFIX + g
    occs[g] = occ
    for nm, b in groups[g]:
        bb = occ.component.bRepBodies.add(b)
        bb.name = nm
        a2 = appearance(COLOR.get(nm, APPEAR[g]))
        if a2:
            bb.appearance = a2

# ------------------------------------------------------------------ pictures
res = []
if SHOTS:
    ui.activeSelections.clear()
    KIT.hide_helpers(design)
    vp = app.activeViewport
    try:
        vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
    except Exception:
        pass
    out = os.path.join(REPO, 'docs/renders')
    tag = 'pcb-v3-fit-%dport' % PORTS

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

    def shot(name, eye, target=(L / 2, 0, 12), fit=True, ortho=False, extent=None, up=(0, 0, 1)):
        cam = vp.camera
        cam.cameraType = adsk.core.CameraTypes.OrthographicCameraType if ortho else adsk.core.CameraTypes.PerspectiveCameraType
        cam.eye = P3(*eye)
        cam.target = P3(*target)
        cam.upVector = adsk.core.Vector3D.create(*up)
        cam.isFitView = fit
        vp.camera = cam
        if fit:
            vp.fit()
        if extent:
            cam = vp.camera
            cam.viewExtents = extent
            vp.camera = cam
        p = os.path.join(out, '%s-%s.png' % (tag, name))
        vp.saveAsImageFile(p, 1800, 1100)
        res.append(p)

    vis(hide=('Rail', 'Lid', 'Screws', 'Tray', 'Plugs')); shot('board', (L / 2 - 150, -170, 190))
    vis(hide=('Rail', 'Lid', 'Screws', 'Plugs')); shot('open', (L / 2 - 150, -170, 190))
    shot('open-b', (L / 2 + 160, 150, 190))
    shot('top', (L / 2, 0, 320), target=(L / 2, 0, 0), up=(0, 1, 0))
    move('Lid', 40)
    vis(hide=('Rail', 'Plugs')); shot('exploded', (L / 2 - 170, -190, 170))
    move('Lid', 0)
    vis(hide=('Rail', 'Plugs')); shot('closed', (-120, -160, 120))
    vis(hide=('Rail',)); shot('end-a', (-140, -80, 70), (15, 0, 12))
    vis(hide=('Plugs',)); shot('in-rail-end', (-200, gy, 18), (0, gy, 18), ortho=True, extent=7.5)
    vis(hide=('Plugs',)); shot('in-rail', (-140, -100, 100))
    vis(hide=('Rail', 'Plugs'))

sq = M.facts(C)['leaf_squeeze']
failures = ((['interference: %d pairs' % len(hits)] if hits else []) + (['pokes out of the box: %d bodies' % len(pokes)] if pokes else [])
            + (['the rod touches the box'] if rod_hit else []) + ([] if path.startswith('ok') else ['board cannot be put in: ' + path])
            + (['a printed part is in %s pieces' % lumps] if max(lumps.values()) > 1 else [])
            + (['leaf squeeze out of range: %s' % sq] if min(sq.values()) < 0.8 or max(sq.values()) > 3.4 else []))
result = {'ok': not failures, 'failures': failures, 'ports': PORTS, 'box': 'L %.1f x W %.1f x H %.1f' % (L, C['out_hi'] - C['room_out'], C['top']),
          'interference': hits or 'none', 'pokes out of the box': pokes or 'none', 'rod clears the groove': not rod_hit,
          'putting the board in': path, 'pieces per printed part': lumps,
          'room above (mm, first contact with the lid)': gaps, 'facts': M.facts(C), 'pictures': res}
