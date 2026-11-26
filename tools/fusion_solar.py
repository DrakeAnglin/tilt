"""The solar housing in a fresh document: a tray for three 70 x 70 mm panels in a row (wired in parallel) and an end
cap. Checks (panels slide in, parts fit, stays-inside) and the two print STLs.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_solar.py --timeout 600

The panels slide in from the right end, face up, under a 45 degree lip along the top and bottom edges, and butt edge
to edge. The cap then closes the right end: it drops onto two round puzzle tabs on the tray's rails and locks along X.
Taped to the glass with the tray, it cannot lift off. Tape goes on the window
face of the solid left end and of the cap, so the housing sticks flat on the window. Behind the panels a 10 mm channel
runs the whole length for the solder bumps and the red and black wires; they leave through a small slot in the cap.
A mirrored set (cap and wires at the left end) is exported too.
Coordinates: X along the row (cap at +X), Y across (+Y = the panels' top edge, where the bumps are), Z up from the
back. Both parts print as built: back on the bed, the lips at 45 degrees, no supports.
"""
import math
import os

# REPO is set by fusion.py exec
KIT = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/fusion_kit.py'))
STL = os.path.join(REPO, 'hardware/mechanical/stl/solar')
os.makedirs(STL, exist_ok=True)
tbm = adsk.fusion.TemporaryBRepManager.get()
B = adsk.fusion.BooleanTypes

S = {
    'panel': 70.0,        # panel side (measured 70 x 70)
    'panel_t': 1.8,       # panel thickness (measured)
    'n': 3,               # panels in the row
    'fit': 0.1,           # clearance each side across the row: 0.2 in all (top to bottom)
    'play': -0.05,        # the lip's 45 degree underside meets the wall 0.05 under the panel face, so a centered
                          # panel has only fit + play = 0.05 room under the lip (front to back): snug, no rocking
    'rail': 6.0,          # top and bottom rails, outside the panels (their ends carry the puzzle tabs)
    'pad': 15.0,          # tape pad at each end: the solid left end and the cap
    'lip': 1.2,           # the lip reaches this far in over each panel edge, its underside at 45 degrees
    'lip_tip': 0.65,      # lip thickness at its inner edge
    'back': 1.2,          # back skin under the channel
    'chan_d': 2.2,        # channel depth under the panels (wires 1.8 tall + 0.4)
    'chan_y0': 10.0,      # channel from 10 to 20 mm below the panels' top edge (bumps measured 11 to 19)
    'chan_y1': 20.0,
    'exit_w': 4.4,        # wire exit in the cap: two 1.8 wires side by side + room
    'open_back': False,   # True: a window through the back under each panel (lighter, but the panel backs show)
    'ledge': 5.0,         # with open_back: floor kept under each panel's edges
    'win_gap': 3.0,       # floor kept beside the channel
    'corner': 3.0,        # outside corner radius (the four outer corners only)
    'tab_y': 37.45,       # puzzle tab center line (|Y|)
    'tab_neck': 2.4,      # neck width
    'tab_neck_len': 2.0,
    'tab_d': 4.4,         # round head
    'tab_fit': 0.15,      # socket clearance each side
    'wire_d': 1.8,
    'bump_h': 1.2,        # mock solder bump height (under the wires' 1.8)
}
S['pl'] = S['n'] * S['panel'] + S['fit']                 # slot length: left wall to the cap
S['pw'] = S['panel'] + 2 * S['fit']                      # slot width
S['W'] = S['pw'] + 2 * S['rail']
S['x0'] = -S['pl'] / 2                                   # left wall (inside)
S['xj'] = S['pl'] / 2                                    # tray end = cap face
S['xl'], S['xr'] = S['x0'] - S['pad'], S['xj'] + S['pad']
S['z_floor'] = S['back'] + S['chan_d']                   # panels rest here
S['z_pt'] = S['z_floor'] + S['panel_t']                  # panel face
S['z_lip'] = S['z_pt'] + S['play']                       # where the 45 degree underside meets the wall
S['top'] = S['z_lip'] + S['lip'] + S['lip_tip']          # window face
S['yt'] = S['panel'] / 2                                 # panels' top edge (Y)
S['cy0'], S['cy1'] = S['yt'] - S['chan_y1'], S['yt'] - S['chan_y0']
assert S['cy0'] - S['win_gap'] > -S['panel'] / 2 + S['ledge'] + 10


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


def op(a, b, t):
    tbm.booleanOperation(a, b, t)
    return a


def rbox(x0, x1, y0, y1, z0, z1, r):
    b = op(bx(x0 + r, x1 - r, y0, y1, z0, z1), bx(x0, x1, y0 + r, y1 - r, z0, z1), B.UnionBooleanType)
    for xx in (x0 + r, x1 - r):
        for yy in (y0 + r, y1 - r):
            op(b, cyl((xx, yy, z0), (xx, yy, z1), r), B.UnionBooleanType)
    return b


def vol(a, b):
    cc = tbm.copy(a)
    try:
        tbm.booleanOperation(cc, tbm.copy(b), B.IntersectionBooleanType)
        return cc.volume * 1000 if cc.faces.count else 0.0
    except Exception:
        return 0.0


W2, pw2 = S['W'] / 2, S['pw'] / 2
outline = rbox(S['xl'], S['xr'], -W2, W2, 0, S['top'], S['corner'])
X_END = S['xr'] + 1


def slot(x1):
    """The panels' way in, from the left wall to x1: the groove under the lips, the opening between them, and the
    45 degree wedge under each lip (wall at Y = +-pw2, Z = z_lip, rising inward)."""
    s = bx(S['x0'], x1, -pw2, pw2, S['z_floor'], S['z_lip'])
    op(s, bx(S['x0'], x1, -(pw2 - S['lip']), pw2 - S['lip'], S['z_floor'], S['top'] + 1), B.UnionBooleanType)
    c = 1 / math.sqrt(2)
    for sg in (1, -1):
        # a big box whose face is the 45 degree plane through (Y = sg*pw2, Z = z_lip), lying on the inner, lower side
        n = (0, -sg * c, -c)                              # into the wedge side
        p = (0, sg * pw2 + n[1] * 10, S['z_lip'] + n[2] * 10)
        big = obox(((S['x0'] + x1) / 2, p[1], p[2]), (1, 0, 0), (0, sg * c, -c), x1 - S['x0'], 40, 20)
        wedge = op(big, bx(S['x0'], x1, sg * pw2, sg * (pw2 - S['lip']), S['z_lip'] - 0.01, S['top'] + 1),
                   B.IntersectionBooleanType)
        op(s, wedge, B.UnionBooleanType)
    return s


body = tbm.copy(outline)
op(body, slot(X_END), B.DifferenceBooleanType)
# the wire channel under the whole row, open at the right end
op(body, bx(S['x0'], X_END, S['cy0'], S['cy1'], S['back'], S['z_floor'] + 0.01), B.DifferenceBooleanType)
# a square window through the back under each panel, inside its ledge and clear of the channel
for i in range(S['n'] if S['open_back'] else 0):
    xa = S['x0'] + i * S['panel']
    op(body, bx(xa + S['ledge'], xa + S['panel'] - S['ledge'], -S['panel'] / 2 + S['ledge'], S['cy0'] - S['win_gap'],
                -1, S['z_floor'] + 0.01), B.DifferenceBooleanType)
# split: the tray and the cap
tray = op(tbm.copy(body), bx(S['xl'] - 1, S['xj'], -W2 - 1, W2 + 1, -1, S['top'] + 1), B.IntersectionBooleanType)
cap = op(tbm.copy(outline), bx(S['xj'], S['xr'] + 1, -W2 - 1, W2 + 1, -1, S['top'] + 1), B.IntersectionBooleanType)
# the cap's wire exit: just wide enough for the two wires, in line with the channel, open on the back so the wires
# drop in before the cap goes on
ey = (S['cy0'] + S['cy1']) / 2
op(cap, bx(S['xj'] - 1, X_END, ey - S['exit_w'] / 2, ey + S['exit_w'] / 2, -1, S['back'] + S['wire_d'] + 0.4),
   B.DifferenceBooleanType)
# the puzzle joint: a round tab on the end of each rail, a matching socket in the cap (grown by tab_fit)


def tab(sg, grow):
    y = sg * S['tab_y']
    hx = S['xj'] + S['tab_neck_len'] + S['tab_d'] / 2
    t = bx(S['xj'] - (1 if grow else 0), hx, y - S['tab_neck'] / 2 - grow, y + S['tab_neck'] / 2 + grow,
           -1 if grow else 0, S['top'] + (1 if grow else 0))
    op(t, cyl((hx, y, -1 if grow else 0), (hx, y, S['top'] + (1 if grow else 0)), S['tab_d'] / 2 + grow), B.UnionBooleanType)
    return t


for sg in (1, -1):
    op(tray, tab(sg, 0), B.UnionBooleanType)
    op(cap, tab(sg, S['tab_fit']), B.DifferenceBooleanType)

# mock-ups: the panels, a solder bump on each, the red and black wires along the channel and out of the cap
parts = []
for i in range(S['n']):
    xa = S['x0'] + i * S['panel']
    parts.append(('Panel %d' % (i + 1), bx(xa, xa + S['panel'], -S['panel'] / 2, S['panel'] / 2, S['z_floor'], S['z_pt'])))
    xc = xa + S['panel'] / 2
    parts.append(('Bump %d' % (i + 1), bx(xc - 6, xc + 6, S['yt'] - 19, S['yt'] - 11, S['z_floor'] - S['bump_h'], S['z_floor'])))
zw = S['back'] + S['wire_d'] / 2 + 0.05
for nm, yy in (('Wire red', ey + 1.1), ('Wire black', ey - 1.1)):
    parts.append((nm, cyl((S['x0'] + 20, yy, zw), (S['xr'] + 15, yy, zw), S['wire_d'] / 2)))

failures = []
for nm, b in parts:
    for what, solid in (('tray', tray), ('cap', cap)):
        v = vol(solid, b)
        if v > 0.01:
            failures.append('%s runs into the %s: %.2f mm3' % (nm, what, v))
if vol(tray, cap) > 0.01:
    failures.append('the cap runs into the tray')
# the way in: each panel with its bump slides in from beyond the right end to its place
for nm, b in parts:
    if nm.startswith(('Panel', 'Bump')):
        q = b.boundingBox
        sweep = bx(q.minPoint.x * 10, S['xr'] + 80, q.minPoint.y * 10, q.maxPoint.y * 10, q.minPoint.z * 10, q.maxPoint.z * 10)
        v = vol(tray, sweep)
        if v > 0.01:
            failures.append('%s cannot slide in from the end: %.2f mm3 in the way' % (nm, v))
# the lip holds the panels down: lifted 0.4 mm, a panel hits the lips
lifted = bx(S['x0'], S['x0'] + S['panel'], -S['panel'] / 2, S['panel'] / 2, S['z_floor'] + 0.4, S['z_pt'] + 0.4)
# the cap is locked along X: pulled 0.5 mm off the end, it hits the tabs
pulled = tbm.copy(cap)
mv = adsk.core.Matrix3D.create()
mv.translation = adsk.core.Vector3D.create(0.05, 0, 0)
tbm.transform(pulled, mv)
if vol(tray, pulled) < 1.0:
    failures.append('the puzzle tabs do not hold the cap')
if vol(tray, lifted) < 1.0:
    failures.append('the lips do not hold the panels down')
# no rocking: a centered panel lifted 0.1 mm already touches both lips
nudged = bx(S['x0'], S['x0'] + S['panel'], -S['panel'] / 2, S['panel'] / 2, S['z_floor'] + 0.1, S['z_pt'] + 0.1)
if vol(tray, nudged) <= 0.0:
    failures.append('a panel can rock: 0.1 mm lift does not reach the lips')
room = S['fit'] + S['play']
if room < 0.02:
    failures.append('only %.2f mm under the lips: the panels may not slide in' % room)
failures += KIT.stays_inside(tbm, [('Solar tray', tray), ('Solar cap', cap)] + parts, outline, allow=('Wire',))
walls = {
    'socket to the outside': W2 - S['tab_y'] - S['tab_d'] / 2 - S['tab_fit'],
    'socket to the wire exit': S['tab_y'] - S['tab_d'] / 2 - S['tab_fit'] - ((S['cy0'] + S['cy1']) / 2 + S['exit_w'] / 2),
    'beside the channel': W2 - S['cy1'],
}
for k, v in walls.items():
    if v < 0.9:
        failures.append('wall %s is only %.2f mm' % (k, v))

# ------------------------------------------------------------------ document
design = KIT.fresh_document(app, 'solar')
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


comps = {}
for g, lst, look in (('Tray', [('Solar tray', tray)], 'Plastic - Matte (White)'),
                     ('Cap', [('Solar cap', cap)], 'Plastic - Matte (White)'),
                     ('Parts', parts, 'Plastic - Matte (Black)')):
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = 'Solar ' + g
    comps[g] = occ.component
    for nm, b in lst:
        bb = occ.component.bRepBodies.add(b)
        bb.name = nm
        col = 'Plastic - Glossy (Red)' if nm == 'Wire red' else ('Plastic - Glossy (Blue)' if nm.startswith('Panel') else look)
        a = appearance(col)
        if a:
            bb.appearance = a

exported, info = [], {}
for g, fn in (('Tray', 'solar_tray.stl'), ('Cap', 'solar_cap.stl')):
    b = comps[g].bRepBodies.item(0)
    if b.lumps.count != 1:
        failures.append('the %s is in %d pieces' % (g.lower(), b.lumps.count))
    path = os.path.join(STL, fn)
    opt = design.exportManager.createSTLExportOptions(comps[g], path)
    opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    design.exportManager.execute(opt)
    exported.append(path)
    q = b.boundingBox
    info[g.lower() + ' (mm)'] = 'L %.2f x W %.2f x H %.2f, %d g PLA' % (
        (q.maxPoint.x - q.minPoint.x) * 10, (q.maxPoint.y - q.minPoint.y) * 10, (q.maxPoint.z - q.minPoint.z) * 10,
        round(b.volume * 1.24))
# the flipped set: the same tray and cap mirrored end for end, so the cap and the wires are at the left end (the
# channel stays along the panels' top edge). Mirroring cannot add an overhang or a thin wall: the checks hold.
flip = adsk.core.Matrix3D.create()
flip.setCell(0, 0, -1)
occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
occ.component.name = 'Solar Flipped'
occ.isLightBulbOn = False
for nm, b, fn in (('Solar tray (wires left)', tray, 'solar_tray_wires_left.stl'),
                  ('Solar cap (wires left)', cap, 'solar_cap_wires_left.stl')):
    m = tbm.copy(b)
    tbm.transform(m, flip)
    sub = occ.component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    sub.component.name = nm
    bb = sub.component.bRepBodies.add(m)
    bb.name = nm
    if abs(bb.volume - b.volume) > 0.001 or bb.lumps.count != 1:
        failures.append('%s did not mirror cleanly' % nm)
    path = os.path.join(STL, fn)
    opt = design.exportManager.createSTLExportOptions(sub.component, path)
    opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    design.exportManager.execute(opt)
    exported.append(path)
old = os.path.join(STL, 'solar_housing.stl')
if os.path.exists(old):
    os.remove(old)
KIT.hide_helpers(design)
result = dict({'ok': not failures, 'failures': failures,
               'housing (mm)': '%.1f x %.1f x %.2f' % (S['xr'] - S['xl'], S['W'], S['top']),
               'panel face below the window face (mm)': round(S['top'] - S['z_pt'], 2),
               'panel room (mm)': 'top to bottom %.2f in all, front to back %.2f' % (2 * S['fit'], S['fit'] + S['play']),
               'walls (mm)': {k: round(v, 2) for k, v in walls.items()}, 'exported': exported}, **info)
