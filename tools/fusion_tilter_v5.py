"""Tilter v0.5 (swing-arm clutch) + its sensor module, fresh document: builds TiltPartsV5 and TiltPodV5, checks every
part against every other with the clutch arm in the middle AND at both stops (idlers rolled round the pinion as they
would), checks the spinning rod, exports STLs to hardware/mechanical/stl/v0.5.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_tilter_v5.py --timeout 1800
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
T5 = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltPartsV5/TiltPartsV5.py'))
POD = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltPodV5/TiltPodV5.py'))
STL = os.path.join(REPO, 'hardware/mechanical/stl/v0.5')
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
        if des and any(des.allComponents.item(k).name.startswith(('T5 ', 'T4 ', 'TP ')) for k in range(des.allComponents.count)):
            old.append(d)
    except Exception:
        pass
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for d in old:
    d.close(False)
rep = T5.build(design, STL)
root = design.rootComponent
CL = T5.clutch_layout()
M = CL['M']
notes = []
pm = POD.P['n20_axis']
if math.hypot(pm[0] - M[0], pm[1] - M[1]) > 0.01:
    notes.append('MODULE MOTOR AXIS %s != CLUTCH %s' % (pm, M))

groups = POD.build(tbm, bx, cyl, cone, uni, cut)
groups['Plug'].append(('Tilt rod (on through the module)', bx(-90, -8.33, -2, 2, POD.P['rod_z'] - 2, POD.P['rod_z'] + 2)))

tilter = []                      # (name, body, occurrence-component name)
for i in range(root.occurrences.count):
    o = root.occurrences.item(i)
    for j in range(o.bRepBodies.count):
        b = o.bRepBodies.item(j)
        if b.name in ('Rod', 'Magnet', 'AS5600 board', 'AS5600 chip') or b.name.startswith('Rail'):
            continue
        tilter.append((b.name, tbm.copy(b)))
own = [(g, nm, b) for g in ('Module', 'Inside', 'Screws', 'Plug') for nm, b in groups[g]]



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


def where(a, b):
    c = tbm.copy(a)
    tbm.booleanOperation(c, tbm.copy(b), B.IntersectionBooleanType)
    q = c.boundingBox
    return 'X %.1f..%.1f Y %.1f..%.1f Z %.1f..%.1f' % (q.minPoint.x * 10, q.maxPoint.x * 10, q.minPoint.y * 10,
                                                       q.maxPoint.y * 10, q.minPoint.z * 10, q.maxPoint.z * 10)


def rot_m(ang_deg, cy, cz):
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.radians(ang_deg), adsk.core.Vector3D.create(1, 0, 0), P3(0, cy, cz))
    return m


# 7T phase: the build doesn't set the crossed-helical mesh phase (as v0.4): turn the clutch shaft to the middle of its
# contact-free window against the worm's 8T, and report the free play (backlash) either side
O = CL['O']
ish = next(i for i, t in enumerate(tilter) if t[0] == 'Clutch shaft')
worm_b = next(b for nm, b in tilter if nm == 'Worm')
pitch7 = 360.0 / T5.P['z_pinion']
scan = []
for k in range(52):
    a_ = k * pitch7 / 52
    b2 = tbm.copy(tilter[ish][1])
    tbm.transform(b2, rot_m(a_, O[0], O[1]))
    scan.append((a_, vol(b2, worm_b)))
free = [v <= 0.01 for _, v in scan]
best, run_, start = (0, None), 0, None
for k in range(2 * len(free)):
    if free[k % len(free)]:
        run_ += 1
        if run_ == 1:
            start = k
        if run_ > best[0] and run_ <= len(free):
            best = (run_, start)
    else:
        run_ = 0
if best[1] is None:
    notes.append('7T: NO contact-free phase against the worm (min overlap %.2f mm3)' % min(v for _, v in scan))
    phase7, free7 = min(scan, key=lambda t: t[1])[0], 0.0
else:
    mid = best[1] + (best[0] - 1) / 2.0
    phase7, free7 = (mid % len(free)) * pitch7 / 52, (best[0] - 1) * pitch7 / 52
b2 = tbm.copy(tilter[ish][1])
tbm.transform(b2, rot_m(phase7, O[0], O[1]))
tilter[ish] = ('Clutch shaft', b2)
occ_sh = next(root.occurrences.item(i) for i in range(root.occurrences.count) if root.occurrences.item(i).component.name == 'T5 Clutch shaft')
mt = occ_sh.transform2
mt.transformBy(rot_m(phase7, O[0], O[1]))
occ_sh.transform2 = mt
notes.append('7T mesh: contact-free window %.1f deg of shaft rotation (backlash), set to its middle' % free7)


# pairs that touch by design (fits / meshes)
MATES = [{'Clutch pinion', 'N20 shaft'}, {'Clutch shaft', 'Clutch 12T'}, {'Clutch pinion', 'Clutch arm'},          # pads grip the hub (0.15 interference)
         {'RJ12 board', 'RJ12 jack'}, {'RJ12 board', 'RJ12 pins'}, {'RJ12 jack', 'RJ12 plug'}, {'RJ12 plug', 'White cord'},
         {'DRV8833', 'DRV8833 chip'}, {'DRV8833', 'C 10uF'}, {'AS5600 board', 'AS5600 chip'}, {'N20', 'N20 shaft'}]


def mated(a, b):
    return {a, b} in MATES


CLUTCH = ('Clutch shaft', 'Clutch 12T', 'Clutch pinion', 'Idler A', 'Idler B', 'Clutch arm')


def check(tilter_bodies, label, skip=()):
    hits = []
    for g, na, a in own:                                      # module side vs tilter side
        for nb, b in tilter_bodies:
            if mated(na, nb) or {na, nb} in skip:
                continue
            v = vol(a, b)
            if v > 0.01:
                hits.append('%s: %s / %s: %.2f mm3 at %s' % (label, na, nb, v, where(a, b)))
    for i in range(len(tilter_bodies)):                       # clutch parts vs every tilter body
        for j in range(len(tilter_bodies)):
            na, a = tilter_bodies[i]
            nb, b = tilter_bodies[j]
            if j <= i or not (na in CLUTCH or nb in CLUTCH) or mated(na, nb) or {na, nb} in skip:
                continue
            v = vol(a, b)
            if v > 0.01:
                hits.append('%s: %s / %s: %.2f mm3 at %s' % (label, na, nb, v, where(a, b)))
    return hits


hits = check(tilter, 'neutral')
for i in range(len(own)):                                     # module-side parts vs each other
    for j in range(i + 1, len(own)):
        if own[i][0] == own[j][0] and own[i][0] in ('Module', 'Screws', 'Plug'):
            continue
        if mated(own[i][1], own[j][1]):
            continue
        v = vol(own[i][2], own[j][2])
        if v > 0.01:
            hits.append('neutral: %s / %s: %.2f mm3 at %s' % (own[i][1], own[j][1], v, where(own[i][2], own[j][2])))


# ---------------- the arm at its two stops: arm + idlers rotated about the motor axis, idlers rolled on the pinion
def rot(body, ang_deg, cy, cz):
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.radians(ang_deg), adsk.core.Vector3D.create(1, 0, 0), P3(0, cy, cz))
    tbm.transform(body, m)
    return body


zr = T5.C['z_pin'] / T5.C['z_idl']
sw = math.degrees(CL['swing'])
stop_hits = {}
for sgn, eng in ((1, 'Idler B'), (-1, 'Idler A')):
    alpha = sgn * sw
    moved = []
    for nm, b in tilter:
        b2 = tbm.copy(b)
        if nm in ('Idler A', 'Idler B'):
            p = CL['A'] if nm == 'Idler A' else CL['B']
            rot(b2, alpha * zr, p[0], p[1])
            rot(b2, alpha, M[0], M[1])
        elif nm == 'Clutch arm':
            rot(b2, alpha, M[0], M[1])
        moved.append((nm, b2))
    # the engaged idler meshes the 12T (tooth phase not modeled): judged by its center distance below, not by volume
    lab = 'stop (%s engaged)' % eng
    stop_hits[lab] = check(moved, lab, skip=[{eng, 'Clutch 12T'}])
    # contact with the stop post: should be ~0 (touching)
    post = [b for g, nm, b in own if g == 'Module'][0]
    arm2 = [b for nm, b in moved if nm == 'Clutch arm'][0]
    stop_hits[lab].append('arm vs module (stop contact) %.3f mm3' % vol(arm2, post))

# center distances (analytic)
dist = lambda p, q: math.hypot(p[0] - q[0], p[1] - q[1])
cd = {'pinion-12T (no mesh: tips apart)': round(CL['d'] - CL['gp']['ra'] - CL['go']['ra'], 3),
      'idler-12T at neutral, tip gap A/B': (round(dist(CL['A'], O) - CL['gi']['ra'] - CL['go']['ra'], 3),
                                             round(dist(CL['B'], O) - CL['gi']['ra'] - CL['go']['ra'], 3)),
      'idler-12T at stop, center distance (b=%.3f)' % CL['b']: (round(dist(CL['A_on'], O), 3), round(dist(CL['B_on'], O), 3)),
      'idler-12T standard center distance (no cd_extra)': round(CL['gi']['rp'] + CL['go']['rp'], 3),
      'far idler at the other stop, tip gap to 12T': (round(dist(CL['A_far'], O) - CL['gi']['ra'] - CL['go']['ra'], 3),
                                                      round(dist(CL['B_far'], O) - CL['gi']['ra'] - CL['go']['ra'], 3)),
      'arm swing to each stop (deg)': round(sw, 2)}

# rod spinning: its sweep vs the clutch parts and the module
sweep = cyl((-90, 0, POD.P['rod_z']), (-8.4, 0, POD.P['rod_z']), POD.P['rod'] * math.sqrt(2) / 2)
rod_hits = ['%s: %.2f' % (nm, vol(sweep, b)) for nm, b in tilter if nm in CLUTCH and vol(sweep, b) > 0.01]
rod_hits += ['%s: %.2f' % (nm, vol(sweep, b)) for g, nm, b in own if g != 'Plug' and vol(sweep, b) > 0.01]

# ---------------- components + module STL
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


comps = {}
for g, lst in groups.items():
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = 'T5 ' + g
    comps[g] = occ.component
    ap = appearance(APPEAR[g])
    for nm, b in lst:
        bb = occ.component.bRepBodies.add(b)
        bb.name = nm
        if ap:
            bb.appearance = ap
files = list(rep['files'])
em = design.exportManager
path = os.path.join(STL, 'sensor_module.stl')
opt = em.createSTLExportOptions(comps['Module'], path)
opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
em.execute(opt)
files.append(path)

result = {'clutch': rep['CL'], 'center distances (mm)': cd, 'module': POD.summary(), 'notes': notes,
          'interference (neutral)': hits, 'interference at the stops': stop_hits, 'rod sweep': rod_hits,
          'exported': [os.path.basename(f) for f in files]}
