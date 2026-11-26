"""The solar housing in a fresh document: one flat tray for three 70 x 70 mm panels in a row, wired in parallel.
Checks (panels and wires fit, stays-inside) and the print STL.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_solar.py --timeout 600

The panels lie face up in one long pocket, butted edge to edge, with their faces flush with the rim. The rim face
takes double-sided tape and sticks flat on the window, so the panels sit right against the glass. Behind the panels
a 10 mm channel runs the whole length for the solder bumps and the red and black wires, and leaves through a notch
in the right end. Coordinates: X along the row, Y across (+Y = the panels' top edge, where the bumps are),
Z up from the back. The back is open under each panel, inside a 5 mm glue ledge, to keep it light.
The part prints as built: back on the bed, everything open upward, no supports.
"""
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
    'fit': 0.2,           # clearance round the row, each side (snug)
    'rim': 6.0,           # rim width all round: room for double-sided tape
    'back': 1.2,          # back skin under the channel
    'chan_d': 2.2,        # channel depth under the panels (wires 1.8 tall + 0.4)
    'chan_y0': 10.0,      # channel from 10 to 20 mm below the panels' top edge (bumps measured 11 to 19)
    'chan_y1': 20.0,
    'corner': 3.0,        # outside corner radius
    'relief': 1.0,        # round relief in each pocket corner, so the square panel corners seat
    'ledge': 5.0,         # glue ledge under each panel's edges; the back is open inside it (saves weight)
    'win_gap': 3.0,       # floor kept beside the channel
    'win_r': 3.0,         # window corner radius
    'wire_d': 1.8,
    'bump_h': 1.2,        # mock solder bump height (under the wires' 1.8)
}
S['pl'] = S['n'] * S['panel'] + 2 * S['fit']             # pocket length
S['pw'] = S['panel'] + 2 * S['fit']                      # pocket width
S['L'] = S['pl'] + 2 * S['rim']
S['W'] = S['pw'] + 2 * S['rim']
S['z_floor'] = S['back'] + S['chan_d']                   # panels rest here
S['top'] = S['z_floor'] + S['panel_t']                   # rim face = panel face
S['yt'] = S['panel'] / 2                                 # panels' top edge (Y)
S['cy0'], S['cy1'] = S['yt'] - S['chan_y1'], S['yt'] - S['chan_y0']
assert S['cy0'] - S['win_gap'] > -S['panel'] / 2 + S['ledge'] + 10


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


L2, W2, pl2, pw2 = S['L'] / 2, S['W'] / 2, S['pl'] / 2, S['pw'] / 2
outline = rbox(-L2, L2, -W2, W2, 0, S['top'], S['corner'])
housing = tbm.copy(outline)
# the panel pocket, with a round relief in each corner
pocket = bx(-pl2, pl2, -pw2, pw2, S['z_floor'], S['top'] + 1)
for xx in (-pl2, pl2):
    for yy in (-pw2, pw2):
        op(pocket, cyl((xx, yy, S['z_floor']), (xx, yy, S['top'] + 1), S['relief']), B.UnionBooleanType)
op(housing, pocket, B.DifferenceBooleanType)
# the wire channel under the whole row, and the exit notch through the right end (open to the window face)
op(housing, bx(-pl2, L2 + 1, S['cy0'], S['cy1'], S['back'], S['top'] + 1), B.DifferenceBooleanType)

# a window through the back under each panel, inside its glue ledge and clear of the channel
for i in range(S['n']):
    x0 = -S['pl'] / 2 + S['fit'] + i * S['panel']
    op(housing, rbox(x0 + S['ledge'], x0 + S['panel'] - S['ledge'], -S['panel'] / 2 + S['ledge'], S['cy0'] - S['win_gap'],
                     -1, S['z_floor'] + 0.01, S['win_r']), B.DifferenceBooleanType)

# mock-ups: the panels, a solder bump on each, the red and black wires along the channel and out of the notch
parts = []
for i in range(S['n']):
    x0 = -S['pl'] / 2 + S['fit'] + i * S['panel']
    parts.append(('Panel %d' % (i + 1), bx(x0, x0 + S['panel'], -S['panel'] / 2, S['panel'] / 2, S['z_floor'], S['top'])))
    xc = x0 + S['panel'] / 2
    parts.append(('Bump %d' % (i + 1), bx(xc - 6, xc + 6, S['yt'] - 19, S['yt'] - 11, S['z_floor'] - S['bump_h'], S['z_floor'])))
zw = S['back'] + S['wire_d'] / 2 + 0.05
for nm, yy in (('Wire red', S['cy1'] - 1.6), ('Wire black', S['cy0'] + 1.6)):
    parts.append((nm, cyl((-pl2 + 20, yy, zw), (L2 + 15, yy, zw), S['wire_d'] / 2)))

failures = []
for nm, b in parts:
    v = vol(housing, b)
    if v > 0.01:
        failures.append('%s runs into the housing: %.2f mm3' % (nm, v))
failures += KIT.stays_inside(tbm, [('Solar housing', housing)] + parts, outline, allow=('Wire',))
side_wall = W2 - S['cy1']
if side_wall < 1.5:
    failures.append('the rim beside the channel is only %.2f mm' % side_wall)

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
for g, lst, look in (('Housing', [('Solar housing', housing)], 'Plastic - Matte (White)'),
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

hb = comps['Housing'].bRepBodies.item(0)
if hb.lumps.count != 1:
    failures.append('the housing is in %d pieces' % hb.lumps.count)
path = os.path.join(STL, 'solar_housing.stl')
opt = design.exportManager.createSTLExportOptions(comps['Housing'], path)
opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
design.exportManager.execute(opt)
KIT.hide_helpers(design)
q = hb.boundingBox
result = {'ok': not failures, 'failures': failures,
          'housing (mm)': 'L %.2f x W %.2f x H %.2f' % ((q.maxPoint.x - q.minPoint.x) * 10, (q.maxPoint.y - q.minPoint.y) * 10,
                                                        (q.maxPoint.z - q.minPoint.z) * 10),
          'pocket (mm)': '%.1f x %.1f x %.1f deep' % (S['pl'], S['pw'], S['panel_t']),
          'channel (mm)': 'Y %.1f..%.1f, %.1f deep under the panels' % (S['cy0'], S['cy1'], S['chan_d']),
          'rim beside the channel (mm)': round(side_wall, 2),
          'volume (cm3)': round(hb.volume, 1), 'PLA (g)': round(hb.volume * 1.24), 'lumps': hb.lumps.count, 'exported': path}
