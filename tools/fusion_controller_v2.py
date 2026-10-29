"""Fresh ControllerV2 build in its own document: hole-accurate perfboard, every part from ControllerV2.layout(), case,
rail; exact interference check with Fusion's B-rep booleans; renders to docs/renders/ctrl-v2-*.png.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v2.py --timeout 900
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
L = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/ControllerV2/ControllerV2.py'))
PREFIX = 'C2 '
C = L.C
tbm = adsk.fusion.TemporaryBRepManager.get()
UNION = adsk.fusion.BooleanTypes.UnionBooleanType
DIFF = adsk.fusion.BooleanTypes.DifferenceBooleanType
INTER = adsk.fusion.BooleanTypes.IntersectionBooleanType


def P3(x, y, z):
    return adsk.core.Point3D.create(x / 10.0, y / 10.0, z / 10.0)


def bx(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    obb = adsk.core.OrientedBoundingBox3D.create(P3((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
                                                 adsk.core.Vector3D.create(1, 0, 0), adsk.core.Vector3D.create(0, 1, 0),
                                                 (x1 - x0) / 10.0, (y1 - y0) / 10.0, (z1 - z0) / 10.0)
    return tbm.createBox(obb)


def cyl(p1, p2, r):
    return tbm.createCylinderOrCone(P3(*p1), r / 10.0, P3(*p2), r / 10.0)


def uni(a, *bs):
    for b in bs:
        tbm.booleanOperation(a, b, UNION)
    return a


def cut(a, *bs):
    for b in bs:
        tbm.booleanOperation(a, b, DIFF)
    return a


parts, geo = L.layout()
X, Y = L.X, L.Y
LO, E = L.LO, L.E_IN
hw, w, fl = C['half_w'], C['wall'], C['floor']
iw = hw - w
zl = C['top'] - C['lid']
gw = C['groove_hw'] + C['groove_wall']

# ------------------------------------------------------------------ bodies from the layout
groups = {}
owner = {}


def add(group, name, body, part=None):
    groups.setdefault(group, []).append((name, body))
    owner[name] = part or name


for p in parts:
    g = p.group
    for b in p.boxes:
        body = bx(*b[1:])
        if 'jack' in b[0] and 'pins' not in b[0]:                      # hollow mouth for the plug
            gj = next(r for r in geo['rj'] if r['n'] == int(b[0].split()[1]))
            zc = C['hung_z1'] + C['rj_jh'] / 2 - 0.5
            f = gj['jface']
            cut(body, bx(f - gj['s'] * 14.0, f + gj['s'] * 1.0, gj['yc'] - C['rj_mouth_w'] / 2, gj['yc'] + C['rj_mouth_w'] / 2,
                         zc - C['rj_mouth_h'] / 2, zc + C['rj_mouth_h'] / 2))
        if b[0] == 'USB-C socket':
            u = geo['usb']
            cut(body, bx(u['front'] - 6.5, u['front'] + 1, u['yc'] - 4.2, u['yc'] + 4.2, C['hung_z1'] + 0.35, C['hung_z1'] + 2.9))
        if b[0].endswith('board') and b[0].startswith('RJ12'):              # its two mounting holes
            gj = next(r for r in geo['rj'] if r['n'] == int(b[0].split()[1]))
            for hx, hy in gj['holes']:
                cut(body, cyl((hx, hy, C['hung_z0'] - 1), (hx, hy, C['hung_z1'] + 1), 1.5))
        add(g, b[0], body, p.name)
    for nm, p1, p2, r in p.cyls:
        add(g, nm, cyl(p1, p2, r), p.name)
    pin_bodies = []
    for i, m, lab in p.pins:
        x, y = X(i), Y(m)
        if p.side == 'top':                                              # header pins up from a hanging board / top parts
            z0 = C['hung_z0'] - 1.0 if p.group == 'Breakouts' else C['pb_z'] - 0.8
            z1 = C['pb_top'] + 1.2
        else:
            z0, z1 = C['pb_z'] - 1.2, C['mod_z'] + 2.2
        pin_bodies.append(bx(x - 0.32, x + 0.32, y - 0.32, y + 0.32, z0, z1))
    if pin_bodies:
        add(g, p.name + ' pins', uni(pin_bodies[0], *pin_bodies[1:]), p.name)

# perfboard: the cut outline, drilled at every hole
board = None
for i0, i1, m0, m1 in L.BOARD:
    r = bx(X(i0) - 1.27, X(i1) + 1.27, Y(m0) - 1.27, Y(m1) + 1.27, C['pb_z'], C['pb_top'])
    board = r if board is None else uni(board, r)
drill = None
for (i, m) in L.HOLES:
    h = cyl((X(i), Y(m), C['pb_z'] - 1), (X(i), Y(m), C['pb_top'] + 1), 0.5)
    drill = h if drill is None else uni(drill, h)
cut(board, drill)
add('Perfboard', 'Perfboard', board)

# battery
add('Battery', '18650 pack', cyl((C['bat_x0'], C['bat_y'], C['bat_z']), (C['bat_x1'], C['bat_y'], C['bat_z']), C['bat_d'] / 2))
add('Battery', '18650 lead', cyl((C['bat_x1'], C['bat_y'], C['bat_z'] + 3), (C['bat_x1'] + 2.0, C['bat_y'], C['bat_z'] + 3), 1.4))

# ------------------------------------------------------------------ case
tray = cut(bx(0, LO, -hw, hw, 0, zl), bx(w, E, -iw, iw, fl, 40))
tray = cut(tray, bx(-1, LO + 1, -gw, gw, C['groove_top'] - C['lid'], 40))
jz0, jz1 = C['hung_z1'], C['hung_z1'] + C['rj_jh']
for g in geo['rj']:
    xw = (-1, w + 1) if g['end'] == 'A' else (E - 1, LO + 1)
    tray = cut(tray, bx(xw[0], xw[1], g['yc'] - C['rj_jw'] / 2 - 0.3, g['yc'] + C['rj_jw'] / 2 + 0.3, jz0 - 0.3, jz1 + 0.3))
    for hx, hy in g['holes']:
        tray = uni(tray, cyl((hx, hy, fl - 0.1), (hx, hy, C['hung_z0']), 2.4),
                   cyl((hx, hy, C['hung_z0'] - 0.1), (hx, hy, C['hung_z1'] + 1.2), 1.3))
u = geo['usb']
uzc = C['hung_z1'] + 1.63
tray = cut(tray, bx(E - 1, LO + 1, u['yc'] - 4.8, u['yc'] + 4.8, uzc - 2.0, uzc + 2.0))
for yy in (u['y'][0] + 0.2, u['y'][1] - 2.2):                               # rails under the USB-C board's ends
    tray = uni(tray, bx(u['back'] + 0.5, u['back'] + 5.0, yy, yy + 2.0, fl - 0.1, C['hung_z0']))
tray = cut(tray, bx(E - 1, LO + 1, -18.75, -15.25, 12.0, 40))             # solar lead slot, open at the top
for sx in (C['bat_x0'] + 6, C['bat_x1'] - 10):                            # battery saddles
    s = cut(bx(sx, sx + 4, -iw, C['bat_y'] + 8.0, fl - 0.1, C['bat_z'] - 3.0),
            cyl((sx - 1, C['bat_y'], C['bat_z']), (sx + 5, C['bat_y'], C['bat_z']), C['bat_d'] / 2 + 0.2))
    tray = uni(tray, s)
for xx in (X(15) + 1.27, X(29) + 1.27):                                   # posts under the strip, between hole rows
    tray = uni(tray, bx(xx - 0.6, xx + 0.6, Y(0) - 1.2, Y(0) + 1.0, fl - 0.1, C['pb_z']),
               bx(xx - 0.6, xx + 0.6, Y(8) - 1.0, Y(8) + 1.2, fl - 0.1, C['pb_z']))
for sx in (LO * 0.3, LO * 0.7):                                           # snap windows
    for s in (-1, 1):
        tray = cut(tray, bx(sx - 4, sx + 4, s * (iw - 0.5), s * (hw + 1), zl - 2.2, zl - 0.6))
add('Case tray', 'Case tray', tray)

lid = bx(0, LO, -hw, hw, zl, C['top'])
for s in (-1, 1):
    lid = uni(lid, bx(6, LO - 6, s * (iw - 0.1), s * (iw - 0.9), zl - 3.5, zl + 0.1))
    for sx in (LO * 0.3, LO * 0.7):
        lid = uni(lid, bx(sx - 3.5, sx + 3.5, s * (iw - 0.1), s * (iw + 0.35), zl - 2.0, zl - 0.8))
for g in geo['rj']:                                                       # hold-downs: jacks, battery
    fx = g['jface'] - g['s'] * 7.0
    lid = uni(lid, bx(fx - 2, fx + 2, g['yc'] - 3, g['yc'] + 3, jz1 + 0.1, zl + 0.1))
for fx in (C['bat_x0'] + 18, C['bat_x1'] - 22):
    lid = uni(lid, bx(fx, fx + 4, C['bat_y'] - 2, C['bat_y'] + 2, C['bat_z'] + C['bat_d'] / 2 + 0.1, zl + 0.1))
lid = cut(lid, bx(-1, LO + 1, -gw, gw, C['groove_top'] - C['lid'], 40))
lid = uni(lid, bx(0, LO, -gw, gw, C['groove_top'] - C['lid'], C['groove_top']))
for s in (-1, 1):
    lid = uni(lid, bx(0, LO, s * C['groove_hw'], s * gw, C['groove_top'] - C['lid'], C['top']))
add('Case lid', 'Case lid', lid)

# ------------------------------------------------------------------ rail + plugs
rh, rt = C['rail_w'] / 2, C['rail_wall']
x0r, x1r = -25.0, LO + 25.0
for nm, b in (('Rail floor', bx(x0r, x1r, -rh - rt, rh + rt, -rt, 0)),
              ('Rail wall room', bx(x0r, x1r, -rh - rt, -rh, -rt, C['rail_h'])),
              ('Rail wall back', bx(x0r, x1r, rh, rh + rt, -rt, C['rail_h'])),
              ('Rail lip room', bx(x0r, x1r, -rh, -rh + C['lip_in'], C['rail_h'] - C['lip_h'], C['rail_h'])),
              ('Rail lip back', bx(x0r, x1r, rh - C['lip_in'], rh, C['rail_h'] - C['lip_h'], C['rail_h']))):
    add('Rail', nm, b)
obb = adsk.core.OrientedBoundingBox3D.create(P3((x0r + x1r) / 2, 0, C['rod_z']), adsk.core.Vector3D.create(1, 0, 0),
                                             adsk.core.Vector3D.create(0, math.cos(math.pi / 4), math.sin(math.pi / 4)),
                                             (x1r - x0r) / 10, C['rod'] / 10, C['rod'] / 10)
add('Rail', 'Tilt rod', tbm.createBox(obb))
sweep = cyl((x0r, 0, C['rod_z']), (x1r, 0, C['rod_z']), C['rod'] * math.sqrt(2) / 2)

for g in geo['rj']:
    zc = C['hung_z1'] + C['rj_jh'] / 2 - 0.5
    f, s = g['jface'], g['s']
    plug = bx(f - s * 12.5, f + s * 9.0, g['yc'] - C['rj_mouth_w'] / 2 + 0.15, g['yc'] + C['rj_mouth_w'] / 2 - 0.15,
              zc - C['rj_mouth_h'] / 2 + 0.15, zc + C['rj_mouth_h'] / 2 - 0.15)
    xo = f + s * 9.0
    cord = bx(xo, xo + s * 40, g['yc'] - 3.3, g['yc'] + 3.3, zc - 1.5, zc + 1.5)
    add('Plugs', 'RJ12 plug %d' % g['n'], plug)
    add('Plugs', 'White cord %d' % g['n'], cord)
add('Plugs', 'USB-C plug', uni(bx(u['front'] - 6.4, LO + 0.5, u['yc'] - 4.15, u['yc'] + 4.15, uzc - 1.25, uzc + 1.25),
                               bx(LO + 0.5, LO + 15.5, u['yc'] - 6, u['yc'] + 6, uzc - 3.25, uzc + 3.25)))
add('Plugs', 'Solar lead', cyl((E - 6, -17.0, 13.6), (LO + 30, -17.0, 13.6), 1.2))

# ------------------------------------------------------------------ interference (exact), then add to a new document
check = [(g, nm, b) for g, lst in groups.items() if g != 'Rail' for nm, b in lst]
check += [('Rail', nm, b) for nm, b in groups['Rail'] if nm != 'Tilt rod'] + [('Sweep', 'Rod sweep', sweep)]
hits = []
for a in range(len(check)):
    for b in range(a + 1, len(check)):
        ga, na, ba = check[a]
        gb, nb, bb = check[b]
        if ga == gb and ga not in ('Breakouts', 'Modules', 'Passives'):
            continue
        if owner.get(na) == owner.get(nb):
            continue
        A, B = ba.boundingBox, bb.boundingBox
        if (A.maxPoint.x <= B.minPoint.x or B.maxPoint.x <= A.minPoint.x or A.maxPoint.y <= B.minPoint.y or
                B.maxPoint.y <= A.minPoint.y or A.maxPoint.z <= B.minPoint.z or B.maxPoint.z <= A.minPoint.z):
            continue
        c = tbm.copy(ba)
        tbm.booleanOperation(c, tbm.copy(bb), INTER)
        try:
            v = c.volume * 1000 if c.faces.count else 0.0
        except Exception:
            v = 0.0
        if v > 0.01:
            hits.append('%s / %s: %.2f mm3' % (na, nb, v))

old = [app.documents.item(i) for i in range(app.documents.count)]
old = [d for d in old if any(c.name.startswith(PREFIX) for c in
                             [adsk.fusion.Design.cast(d.products.itemByProductType('DesignProductType')).allComponents.item(k)
                              for k in range(adsk.fusion.Design.cast(d.products.itemByProductType('DesignProductType')).allComponents.count)])]
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for d in old:
    d.close(False)
root = design.rootComponent
APPEAR = {'Rail': 'Plastic - Matte (White)', 'Case tray': 'Plastic - Matte (White)',
          'Case lid': 'Plastic - Translucent Matte (Blue)', 'Perfboard': 'Plastic - Glossy (Green)',
          'Modules': 'Plastic - Glossy (Blue)', 'Breakouts': 'Plastic - Matte (Black)', 'Passives': 'Plastic - Glossy (Yellow)',
          'Battery': 'Plastic - Glossy (Blue)', 'Plugs': 'Plastic - Matte (White)'}


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
    return None


for gname, lst in groups.items():
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = PREFIX + gname
    ap = appearance(APPEAR.get(gname, 'Plastic - Matte (White)'))
    for nm, b in lst:
        bb = occ.component.bRepBodies.add(b)
        bb.name = nm
        if ap:
            bb.appearance = ap

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


def rail(mode):
    for i in range(root.occurrences.count):
        c = root.occurrences.item(i).component
        if c.name.endswith('Rail'):
            for j in range(c.bRepBodies.count):
                b = c.bRepBodies.item(j)
                b.isLightBulbOn = mode != 'hide'
                b.opacity = 0.3 if mode == 'ghost' and not b.name.startswith('Tilt') else 1.0


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
vis(); rail('ghost'); res.append(shot('ctrl-v2-in-rail.png', 'IsoTopRightViewOrientation'))
vis(); rail('show'); res.append(shot('ctrl-v2-end.png', 'RightViewOrientation', True))
vis(hide=('Case lid',)); rail('hide'); res.append(shot('ctrl-v2-open.png', 'IsoTopRightViewOrientation'))
res.append(shot('ctrl-v2-open-left.png', 'IsoTopLeftViewOrientation'))
vis(hide=('Case lid', 'Case tray', 'Plugs')); rail('hide'); res.append(shot('ctrl-v2-board-top.png', 'TopViewOrientation', True))
vis(hide=('Case lid', 'Case tray', 'Plugs', 'Battery')); res.append(shot('ctrl-v2-board-iso.png', 'IsoTopRightViewOrientation'))
res.append(shot('ctrl-v2-board-under.png', 'IsoBottomRightViewOrientation'))
res.append(shot('ctrl-v2-board-side.png', 'BackViewOrientation', True))
vis(); rail('ghost')
lines, used = L.report(parts)
result = {'layout': lines, 'fusion interference': hits or 'none', 'renders': res}
