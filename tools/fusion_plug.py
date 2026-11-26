"""The wall plug: covers a 5/8 in (15.9 mm) hole drilled through a wall or trim for the RJ12 cords, with a U slot the
cords run through. Checks and the print STL.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_plug.py

A thin round cap sits on the wall and hides the drilled edge; a short hollow shank with crush ribs presses into the
hole. The U slot runs the whole height, so the plug slides on from the side after the cords are through. The shank
is short (6 mm) so a plug fits from each side of one sheet of 1/2 in drywall.
Coordinates: Z up from the cap's face (the side you see), Y = -1 toward the slot. Prints as built: face on the bed,
no supports (the face edge's bevel is 45 degrees).
"""
import math
import os

# REPO is set by fusion.py exec
KIT = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/fusion_kit.py'))
STL = os.path.join(REPO, 'hardware/mechanical/stl/plug')
os.makedirs(STL, exist_ok=True)
tbm = adsk.fusion.TemporaryBRepManager.get()
B = adsk.fusion.BooleanTypes

S = {
    'hole': 15.875,       # 5/8 in drill
    'cap_r': 12.5,        # 25 mm cap: covers about 3.8 mm round the hole (inside the bevel)
    'cap_t': 1.6,         # cap thickness (how far it stands off the wall)
    'bevel': 0.8,         # 45 degree bevel round the face edge
    'shank_r': 7.7,       # shank radius: 0.24 under the hole
    'shank_h': 6.0,       # shank length into the hole
    'bore_r': 5.4,        # hollow shank: a 2.3 mm ring that springs in
    'rib_n': 8,           # crush ribs round the shank; the U slot cuts 2 away, so the print has 6
    'rib_r': 0.6,         # rib radius
    'rib_reach': 8.2,     # ribs reach this far out: 0.26 into the hole's wall
    'lead': 1.0,          # lead-in at the shank's tip
    'slot_w': 7.2,        # U slot width: a flat RJ12 cord is about 6.6 wide
    'slot_d': 8.5,        # slot depth in from the shank's side: two flat cords stacked (2 x 3.3) clear its round end
    'cord_w': 6.6,
    'cord_t': 3.3,
}
S['top'] = S['cap_t'] + S['shank_h']


def P3(x, y, z):
    return adsk.core.Point3D.create(x / 10.0, y / 10.0, z / 10.0)


def cone(z0, r0, z1, r1, x=0.0, y=0.0):
    return tbm.createCylinderOrCone(P3(x, y, z0), r0 / 10, P3(x, y, z1), r1 / 10)


def bx(x0, x1, y0, y1, z0, z1):
    obb = adsk.core.OrientedBoundingBox3D.create(P3((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
                                                 adsk.core.Vector3D.create(1, 0, 0), adsk.core.Vector3D.create(0, 1, 0),
                                                 abs(x1 - x0) / 10, abs(y1 - y0) / 10, abs(z1 - z0) / 10)
    return tbm.createBox(obb)


def op(a, b, t):
    tbm.booleanOperation(a, b, t)
    return a


def vol(a, b):
    cc = tbm.copy(a)
    try:
        tbm.booleanOperation(cc, tbm.copy(b), B.IntersectionBooleanType)
        return cc.volume * 1000 if cc.faces.count else 0.0
    except Exception:
        return 0.0


# cap: bevel ring at the face, then straight
plug = cone(0, S['cap_r'] - S['bevel'], S['bevel'], S['cap_r'])
op(plug, cone(S['bevel'], S['cap_r'], S['cap_t'], S['cap_r']), B.UnionBooleanType)
# shank with ribs, then the lead-in cone trims the tip of both
shank = cone(S['cap_t'] - 0.01, S['shank_r'], S['top'], S['shank_r'])
rc = S['rib_reach'] - S['rib_r']
for i in range(S['rib_n']):
    a = 2 * math.pi * (i + 0.5) / S['rib_n']
    op(shank, cone(S['cap_t'] - 0.01, S['rib_r'], S['top'], S['rib_r'], rc * math.cos(a), rc * math.sin(a)),
       B.UnionBooleanType)
tip_r = S['shank_r'] - S['lead']
lead = cone(S['cap_t'] - 0.01, 30, S['top'] - S['lead'], 30)
op(lead, cone(S['top'] - S['lead'] - 0.01, S['rib_reach'] + 0.01, S['top'], tip_r), B.UnionBooleanType)
op(shank, lead, B.IntersectionBooleanType)
op(plug, shank, B.UnionBooleanType)
# hollow shank, open at the back
op(plug, cone(S['cap_t'], S['bore_r'], S['top'] + 1, S['bore_r']), B.DifferenceBooleanType)
# the U slot, whole height: round bottom, open toward -Y
ub = -S['shank_r'] + S['slot_d'] - S['slot_w'] / 2       # center of the U's round end
slot = cone(-1, S['slot_w'] / 2, S['top'] + 1, S['slot_w'] / 2, 0, ub)
op(slot, bx(-S['slot_w'] / 2, S['slot_w'] / 2, ub, -S['cap_r'] - 1, -1, S['top'] + 1), B.UnionBooleanType)
op(plug, slot, B.DifferenceBooleanType)

# ------------------------------------------------------------------ checks
failures = []
# two flat cords stacked in the U, lying on the hole's bottom edge
yb = -S['hole'] / 2
cords = [bx(-S['cord_w'] / 2, S['cord_w'] / 2, yb + k * S['cord_t'] + 0.05, yb + (k + 1) * S['cord_t'],
            -5, S['top'] + 5) for k in (0, 1)]
for k, c in enumerate(cords):
    v = vol(plug, c)
    if v > 0.01:
        failures.append('cord %d runs into the plug: %.2f mm3' % (k + 1, v))
# the shank (not the ribs) clears the hole; the ribs grip it
hole_wall = cone(S['cap_t'], 20, S['top'] + 1, 20)
op(hole_wall, cone(S['cap_t'] - 0.01, S['hole'] / 2, S['top'] + 2, S['hole'] / 2), B.DifferenceBooleanType)
grip = vol(plug, hole_wall)
if grip < 0.2:
    failures.append('the ribs do not grip the hole (%.2f mm3)' % grip)
walls = {
    'shank ring': S['shank_r'] - S['bore_r'],
    'cap overlap past the hole': S['cap_r'] - S['bevel'] - S['hole'] / 2,
}
for k, v in walls.items():
    if v < 0.9:
        failures.append('%s is only %.2f mm' % (k, v))

# ------------------------------------------------------------------ document and export
design = KIT.fresh_document(app, 'plug')
root = design.rootComponent
occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
occ.component.name = 'Wall Plug'
body = occ.component.bRepBodies.add(plug)
body.name = 'Wall plug'
if body.lumps.count != 1:
    failures.append('the plug is in %d pieces' % body.lumps.count)
path = os.path.join(STL, 'wall_plug.stl')
opt = design.exportManager.createSTLExportOptions(occ.component, path)
opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
design.exportManager.execute(opt)
KIT.hide_helpers(design)
q = body.boundingBox
result = {'ok': not failures, 'failures': failures,
          'plug (mm)': 'D %.1f x H %.1f, %.1f g PLA' % ((q.maxPoint.x - q.minPoint.x) * 10, (q.maxPoint.z - q.minPoint.z) * 10,
                                                      body.volume * 1.24),
          'rib grip (mm3)': round(grip, 2), 'walls (mm)': {k: round(v, 2) for k, v in walls.items()},
          'slot (mm)': '%.1f wide, %.1f in from the shank side' % (S['slot_w'], S['slot_d']), 'exported': path}
