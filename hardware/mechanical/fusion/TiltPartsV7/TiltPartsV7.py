"""TiltPartsV7: v0.6's planetary differential with a 4-stage motor train (88:1 from the N20 to the rod, was 21:1).

  wand  -- worm -- 16T worm wheel (free on the rod) -- hex -- RING cup (30T inside)            (unchanged)
  motor -- 9T -- P1 (20T/9T) -- R1 (27T/15T) -- P2 (21T/9T) -- 27T -- SUN (14T)
  rod   -- CARRIER (square bore) with 4 planets (8T) on steel dowels

Two axes only: P (one M3 bolt, P1 and P2 turn free on it) and the rod's (R1 turns on a fixed tube that is part of
the motor plate, the sun piece in the bearing plate). Ring cup, planets, sun piece, worm wheel, lid: as v0.6.

Global coordinates as TiltPartsV4 (mm): X along the rod, Y across (-Y room side), Z up from the rail floor.
"""

import importlib.util
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('tp4_for_v7', os.path.join(_HERE, '..', 'TiltPartsV4', 'TiltPartsV4.py'))
T4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T4)
adsk = T4.adsk
P = T4.P
PREFIX = 'T7 '
T4.PREFIX = PREFIX
B = adsk.fusion.BooleanTypes

RZ = P['rod_z']
A = -P['slab_half']                       # lid outer face
G = dict(
    m=0.8, zs=14, zp=8, zr=30, n_planets=4, shift=0.1,     # planets +0.1, sun -0.1, ring +0.1 (8T: no undercut)
    m2=1.0, z27=27, z9b=9, z20=20, z9=9, z15=15, z21=21, shift2=0.3,   # 15T +0.3 / 21T -0.3
    ring_ro=14.5, floor_t=3.5, disc_t=3.0, disc_r=11.0, planet_face=4.3, gap=0.3,
    hex_R=7.2, hex_clear=0.15, lid_bore_clear=0.15,
    hub_r=4.2, hub_end_x=-2.0, wheel_bore_hub=4.4, wheel_bore_rod=3.2,
    pin_d=2.0, pin_len=5.9, pin_press=0.025, pin_pocket=3.0, planet_bore_clear=0.1,
    sun_bore=3.3, journal_clear=0.15,
    wall_t=3.0, face_a=5.0, face_b=3.5, face_c=3.5, face_d=3.0, plate_t=3.2,
    tube_r=5.0, tube_bore=3.3, tube_clear=0.15, shoulder_r=6.5,
    boss_r=3.4, axle_boss_r=3.0, insert_r=2.0, insert_len=6.7, m3_r=1.7, axle_bore=1.65,
    cluster_y=-14.5, motor_z=6.0,
    lid_bolts=((-23.0, 27.0), (22.45, 27.58)),
    plate_bolts=((14.0, 4.6), (-23.0, 27.0)),         # the second one shares the lid bolt's boss
    bolt_len=25.0,
)
g = G
# X stations (toward -X)
X = {}
X['floor0'] = A - 0.4
X['floor1'] = X['floor0'] - g['floor_t']
X['disc0'] = X['floor1'] - 0.2
X['disc1'] = X['disc0'] - g['disc_t']
X['pl0'] = X['disc1'] - 0.2
X['pl1'] = X['pl0'] - g['planet_face']
X['wall0'] = X['pl1'] - g['gap']
X['wall1'] = X['wall0'] - g['wall_t']
X['a0'] = X['wall1'] - g['gap']
X['a1'] = X['a0'] - g['face_a']
X['b0'] = X['a1'] - g['gap']
X['b1'] = X['b0'] - g['face_b']
X['c0'] = X['b1'] - g['gap']
X['c1'] = X['c0'] - g['face_c']
X['d0'] = X['c1'] - g['gap']
X['d1'] = X['d0'] - g['face_d']
X['plate0'] = X['d1'] - g['gap']
X['plate1'] = X['plate0'] - g['plate_t']


def gear(z, m, x=0.0):
    d = T4.spur(z, m)
    d['x'] = x
    d['ra'] = d['rp'] + (0.8 + x) * m
    d['rf'] = d['rp'] - (1.25 - x) * m
    return d


GS, GP, GR = gear(g['zs'], g['m'], -g['shift']), gear(g['zp'], g['m'], g['shift']), gear(g['zr'], g['m'], g['shift'])
G27, G9B = gear(g['z27'], g['m2']), gear(g['z9b'], g['m2'])
G20, G9 = gear(g['z20'], g['m']), gear(g['z9'], g['m'])
G15, G21 = gear(g['z15'], g['m2'], g['shift2']), gear(g['z21'], g['m2'], -g['shift2'])
GR['tip'] = GR['rp'] - (0.8 - g['shift']) * g['m']        # internal: teeth point inward
GR['root'] = GR['rp'] + (1.25 + g['shift']) * g['m']
R_ORBIT = GS['rp'] + GP['rp']
CD1 = G27['rp'] + G9B['rp']                               # rod - cluster
CD2 = G20['rp'] + G9['rp']                                # cluster - motor
CL = (g['cluster_y'], RZ - math.sqrt(CD1 ** 2 - g['cluster_y'] ** 2))
MO = (CL[0] + math.sqrt(CD2 ** 2 - (CL[1] - g['motor_z']) ** 2), g['motor_z'])
ROD = (0.0, RZ)


def profile(d, rot=0.0, backlash=None, internal=False):
    """Outline of an external gear (or, internal=True, of the tooth SPACES of an internal one: the cutter shape)."""
    bl = P['backlash'] if backlash is None else backlash
    half = (math.pi / 2 + 2 * d['x'] * math.tan(d['at'])) / d['z']
    if internal:
        return T4.involute_teeth(d['z'], d['rp'], d['rb'], d['root'], d['tip'], d['at'], half + bl / 2 / d['rp'], rot=rot)
    return T4.involute_teeth(d['z'], d['rp'], d['rb'], d['ra'], d['rf'], d['at'], half - bl / 2 / d['rp'], rot=rot)


def phases():
    """Tooth phases (rad, in the YZ plane from +Y toward +Z) that make every mesh sit tooth-in-space as built."""
    ps, pp = 2 * math.pi / g['zs'], 2 * math.pi / g['zp']
    rot_s = ps / 2
    planets = []
    for k in range(g['n_planets']):
        phi = 2 * math.pi * k / g['n_planets']
        u = (phi - rot_s) / ps                            # sun's tooth phase toward this planet (0 = tooth)
        planets.append((phi, phi + math.pi - (u + 0.5) * pp))
    psi1 = math.atan2(CL[1] - ROD[1], CL[0] - ROD[0])
    psi2 = math.atan2(MO[1] - CL[1], MO[0] - CL[0])
    return dict(sun=rot_s, ring=0.0, planets=planets, g27=psi1, g9b=psi1 + math.pi + math.pi / g['z9b'],
                g15=psi1, g21=psi1 + math.pi + math.pi / g['z21'],
                g20=psi2, g9=psi2 + math.pi + math.pi / g['z9'])


# ------------------------------------------------------------------ solids in global coordinates
class Shop:
    """Makes TemporaryBRep solids in global mm: prisms (a YZ outline pulled along X), cylinders along X, boxes."""

    def __init__(self, root):
        self.tbm = adsk.fusion.TemporaryBRepManager.get()
        self.occ, self.comp = T4.new_component(root, 'scratch')
        m = adsk.core.Matrix3D.create()                  # sketch (x, y, z) -> global (X = -z, Y = x, Z = -y)
        m.setWithCoordinateSystem(T4.P3((0, 0, 0)), T4.V3((0, 1, 0)), T4.V3((0, 0, -1)), T4.V3((-1, 0, 0)))
        self.m = m

    def prism(self, pts_yz, xa, xb):
        hi, lo = max(xa, xb), min(xa, xb)
        sk = self.comp.sketches.add(T4.offset_plane(self.comp, -hi))
        T4.polyline(sk, [(y, -z) for y, z in pts_yz])
        f = T4.extrude(self.comp, T4.largest_profile(sk), hi - lo, T4.NEW)
        b = self.tbm.copy(f.bodies.item(0))
        self.tbm.transform(b, self.m)
        return b

    def gear(self, d, c, rot, xa, xb, **kw):
        return self.prism([(c[0] + px, c[1] + py) for px, py in profile(d, rot, **kw)], xa, xb)

    def cyl(self, c, r, xa, xb, r2=None):
        return self.tbm.createCylinderOrCone(T4.P3((xa, c[0], c[1])), r / 10, T4.P3((xb, c[0], c[1])), (r if r2 is None else r2) / 10)

    def box(self, xa, xb, y0, y1, z0, z1):
        return T4.box_minmax(min(xa, xb), max(xa, xb), y0, y1, z0, z1).brep(self.tbm)

    def U(self, a, *bs):
        for b in bs:
            self.tbm.booleanOperation(a, b, B.UnionBooleanType)
        return a

    def D(self, a, *bs):
        for b in bs:
            self.tbm.booleanOperation(a, b, B.DifferenceBooleanType)
        return a

    def done(self):
        self.occ.deleteMe()


def ngon(c, R, n, a0=0.0):
    return [(c[0] + R * math.cos(a0 + 2 * math.pi * k / n), c[1] + R * math.sin(a0 + 2 * math.pi * k / n)) for k in range(n)]


def hex_a0():
    """The wheel's hex has a corner along the wheel-local x axis (= layout n)."""
    n = T4.layout()['n']
    return math.atan2(n[2], n[1])


def planet_centers():
    return [(ROD[0] + R_ORBIT * math.cos(phi), ROD[1] + R_ORBIT * math.sin(phi)) for phi, _ in phases()['planets']]


def make_parts(S):
    """Every new printed part as {name: body}, in place."""
    ph = phases()
    out = {}
    # ring cup: floor with the hex socket (wheel's hex), 30T inside, open toward -X
    cup = S.cyl(ROD, g['ring_ro'], X['floor0'], X['pl1'])
    S.D(cup, S.gear(GR, ROD, ph['ring'], X['floor1'], X['pl1'] - 1, internal=True),
        S.prism(ngon(ROD, g['hex_R'] + g['hex_clear'], 6, hex_a0()), X['floor0'] + 1, X['floor1'] - 1))
    out['Ring cup'] = cup
    # carrier: disc + long hub (inside the wheel's bore) with the square bore, 4 dowel pockets
    car = S.U(S.cyl(ROD, g['disc_r'], X['disc0'], X['disc1']), S.cyl(ROD, g['hub_r'], X['disc0'], g['hub_end_x']))
    h = (P['rod'] + P['rod_clear']) / 2
    S.D(car, S.box(g['hub_end_x'] + 1, X['disc1'] - 1, -h, h, RZ - h, RZ + h))
    for pc in planet_centers():
        S.D(car, S.cyl(pc, g['pin_d'] / 2 - g['pin_press'], X['disc1'] - 1, X['disc1'] + g['pin_pocket']))
    out['Carrier'] = car
    for k, (pc, (_, rot)) in enumerate(zip(planet_centers(), ph['planets'])):
        pl = S.gear(GP, pc, rot, X['pl0'], X['pl1'])
        S.D(pl, S.cyl(pc, g['pin_d'] / 2 + g['planet_bore_clear'], X['pl0'] + 1, X['pl1'] - 1))
        out['Planet %d' % (k + 1)] = pl
    # sun piece: 14T + journal (runs in the bearing plate) + 27T
    sun = S.U(S.gear(GS, ROD, ph['sun'], X['pl0'], X['pl1'] - 0.1),
              S.cyl(ROD, GS['ra'], X['pl1'], X['a0'] - 0.01),
              S.gear(G27, ROD, ph['g27'], X['a0'], X['a1']))
    S.D(sun, S.cyl(ROD, g['sun_bore'], X['pl0'] + 1, X['a1'] - 1))
    out['Sun + 27T'] = sun
    # P2 (sun side): 9T on the sun piece's 27T, 21T on R1's 15T
    p2 = S.U(S.gear(G9B, CL, ph['g9b'], X['a0'], X['b0'] - 0.01), S.gear(G21, CL, ph['g21'], X['b0'], X['b1']))
    S.D(p2, S.cyl(CL, g['axle_bore'], X['a0'] + 1, X['b1'] - 1))
    out['P2 21T/9T'] = p2
    # R1: 15T + 27T, free on the motor plate's tube
    r1 = S.U(S.gear(G15, ROD, ph['g15'], X['b0'], X['c0'] - 0.01), S.gear(G27, ROD, ph['g27'], X['c0'], X['c1']))
    S.D(r1, S.cyl(ROD, g['tube_r'] + g['tube_clear'], X['b0'] + 1, X['c1'] - 1))
    out['R1 27T/15T'] = r1
    # P1 (motor side): 9T on R1's 27T, 20T on the motor pinion
    p1 = S.U(S.gear(G9B, CL, ph['g9b'], X['c0'], X['d0'] - 0.01), S.gear(G20, CL, ph['g20'], X['d0'], X['d1']))
    S.D(p1, S.cyl(CL, g['axle_bore'], X['c0'] + 1, X['d1'] - 1))
    out['P1 20T/9T'] = p1
    # motor pinion, D-bore on the N20's flat
    pin = S.gear(G9, MO, ph['g9'], X['d0'], X['d1'])
    r = P['n20_shaft_d'] / 2 + 0.05
    fx = P['n20_flat'] - P['n20_shaft_d'] / 2 + 0.05
    dpts = [(MO[0] + min(r * math.cos(t), fx), MO[1] + r * math.sin(t)) for t in [2 * math.pi * i / 48 for i in range(48)]]
    S.D(pin, S.prism(dpts, X['d0'] + 1, X['d1'] - 1))
    out['Motor pinion 9T'] = pin
    out['Bearing plate'] = bearing_plate(S)
    out['Motor plate'] = motor_plate(S)
    return out


def bearing_plate(S):
    w0, w1 = X['wall0'], X['wall1']
    hw = P['case_w'] / 2 - 0.4
    b = S.U(S.box(w0, w1, -hw, hw, 0.6, 33.3), S.cyl(ROD, 10.5, w0, w1))
    for c in g['lid_bolts'] + g['plate_bolts']:
        S.U(b, S.cyl(c, g['boss_r'], w0, A))
    S.U(b, S.cyl(CL, g['axle_boss_r'], w0, w0 + 4.2))
    S.D(b, S.cyl(ROD, GS['ra'] + g['journal_clear'], w0 + 1, w1 - 1))
    for c in g['lid_bolts']:                              # inserts pressed in from the lid end of each boss
        S.D(b, S.cyl(c, g['insert_r'], A + 1, A - g['insert_len'] - 0.3), S.cyl(c, g['m3_r'], A, A - 8.4))
    for c in g['plate_bolts']:                            # inserts pressed in from the plate's -X face
        S.D(b, S.cyl(c, g['insert_r'], w1 - 1, w1 + g['insert_len'] + 0.3), S.cyl(c, g['m3_r'], w1, X['plate1'] + g['bolt_len'] + 0.8))
    S.D(b, S.cyl(CL, g['insert_r'], w1 - 1, w1 + g['insert_len'] + 0.3), S.cyl(CL, g['m3_r'], w1, w0 + 5))
    return b


def motor_plate(S):
    p0, p1 = X['plate0'], X['plate1']
    hw = P['case_w'] / 2 - 0.4
    b = S.box(p0, p1, -hw, 17.6, 0.6, 30.6)
    S.U(b, S.cyl(ROD, g['tube_r'], p0, X['b0']), S.cyl(ROD, g['shoulder_r'], p0, X['d0']))   # R1's axle + thrust shoulder
    for c in g['plate_bolts']:
        S.U(b, S.cyl(c, g['boss_r'], p0, X['wall1']))     # standoffs up to the bearing plate
    S.D(b, S.cyl(ROD, g['tube_bore'], X['b0'] + 1, p1 - 1), S.cyl(MO, 2.6, p0 + 1, p1 - 1))
    for sg in (-1, 1):                                    # N20 gearbox screws (M1.6 x 4), heads sunk under the gears
        c = (MO[0] + sg * P['n20_screw_spacing'] / 2, MO[1])
        S.D(b, S.cyl(c, 0.95, p0 + 1, p1 - 1), S.cyl(c, 1.75, p0 + 1, p0 - 1.4))
    for c in g['plate_bolts'] + (CL,):
        S.D(b, S.cyl(c, g['m3_r'], X['wall1'] + 1, p1 - 1), S.cyl(c, 3.1, p1 - 0.01, p1 + 1.4, g['m3_r']))
    return b


def ref_parts(S):
    out = {}
    out['Rod'] = S.box(-75, 40, -2, 2, RZ - 2, RZ + 2)
    f = X['plate1']
    gb = S.box(f, f - P['n20_gbx'], MO[0] - 6, MO[0] + 6, MO[1] - 5, MO[1] + 5)
    can = S.cyl(MO, 6, f - P['n20_gbx'], f - P['n20_gbx'] - P['n20_motor'])
    S.tbm.booleanOperation(can, S.box(f, f - 40, MO[0] - 7, MO[0] + 7, MO[1] - 5, MO[1] + 5), B.IntersectionBooleanType)
    out['N20'] = S.U(gb, can, S.cyl(MO, 4.5, f - P['n20_gbx'] - P['n20_motor'], f - P['n20_gbx'] - P['n20_motor'] - 1))
    out['N20 shaft'] = S.cyl(MO, 1.5, f, f + P['n20_shaft_len'])
    for k, pc in enumerate(planet_centers()):
        out['Dowel %d' % (k + 1)] = S.cyl(pc, 1.0, X['disc1'] + g['pin_pocket'], X['disc1'] + g['pin_pocket'] - g['pin_len'])
    for k, c in enumerate(g['lid_bolts']):
        out['Case bolt %d' % (k + 1)] = S.cyl(c, 1.5, P['main_half'], P['main_half'] - g['bolt_len'])
    for k, c in enumerate(g['plate_bolts'] + (CL,)):
        out['Plate bolt %d' % (k + 1)] = S.cyl(c, 1.5, f, f + g['bolt_len'])
    w2, hh, t = P['rail_w'] / 2, P['rail_h'], P['rail_wall']
    out['Rail floor'] = S.box(-75, 40, -w2 - t, w2 + t, -t, 0)
    out['Rail wall room'] = S.box(-75, 40, -w2 - t, -w2, 0, hh)
    out['Rail wall back'] = S.box(-75, 40, w2, w2 + t, 0, hh)
    out['Rail lip room'] = S.box(-75, 40, -w2, -w2 + P['lip_in'], hh - P['lip_h'], hh)
    out['Rail lip back'] = S.box(-75, 40, w2 - P['lip_in'], w2, hh - P['lip_h'], hh)
    return out


# ------------------------------------------------------------------ worm wheel (free on the rod) and the lid
def build_wheel6(root, L):
    """As v0.4's wheel, but: round bore (the rod turns inside it), a wider lid-side barrel ending in a hex that
    drives the ring cup, and a counterbore for the carrier's hub. Wheel-local z = global X."""
    occ, comp = T4.new_component(root, 'Worm wheel')
    fw, ns = P['wheel_face'], P['wheel_slices']
    T4.loft_sections(comp, [(-fw / 2 + fw * i / (ns - 1), T4.wheel_section(-fw / 2 + fw * i / (ns - 1))) for i in range(ns)], smooth=False)
    x0, x1 = T4.slab_x(L)
    zb = A - 0.3                                           # round barrel ends just outside the lid face
    T4.extrude(comp, T4.circle_profile(comp, zb, g['hex_R']), -fw / 2 + 0.3 - zb, T4.JOIN)
    T4.extrude(comp, T4.circle_profile(comp, fw / 2 - 0.3, P['barrel_r']), x1 - 0.2 - fw / 2 + 0.3, T4.JOIN)
    zh = X['floor1'] + 0.1
    sk = comp.sketches.add(T4.offset_plane(comp, zh))
    T4.polyline(sk, ngon((0, 0), g['hex_R'], 6))
    T4.extrude(comp, T4.largest_profile(sk), zb - zh + 0.01, T4.JOIN)
    T4.merge_bodies(comp)
    T4.extrude(comp, T4.circle_profile(comp, zh, g['wheel_bore_rod']), x1 - zh, T4.CUT)
    T4.extrude(comp, T4.circle_profile(comp, zh, g['wheel_bore_hub']), g['hub_end_x'] + 0.5 - zh, T4.CUT)
    comp.bRepBodies.item(0).name = 'Worm wheel'
    return occ, comp


_case_shapes_v4 = T4.case_shapes


def case_shapes_v6(L):
    env, cav, trims, mo_len, dome = _case_shapes_v4(L)
    drop = {'motor socket', 'motor screw hole', 'motor screw counterbore'}
    cav = [pr for pr in cav if getattr(pr, 'label', '') not in drop]
    pr = T4.Prim('cyl', p1=(A - 1, 0, RZ), p2=(-P['wheel_face'] / 2 - 0.2, 0, RZ), r=g['hex_R'] + g['lid_bore_clear'])
    pr.label = 'lid barrel bore'
    cav.append(pr)
    return env, cav, trims, mo_len, dome


T4.case_shapes = case_shapes_v6
T4.motor_pod = lambda L: T4.box_minmax(500, 501, 500, 501, 500, 501)


# ------------------------------------------------------------------ build + checks
def _rot(tbm, body, ang, c):
    m = adsk.core.Matrix3D.create()
    m.setToRotation(ang, T4.V3((1, 0, 0)), T4.P3((0, c[0], c[1])))
    b = tbm.copy(body)
    tbm.transform(b, m)
    return b


def _vol(tbm, a, b):
    p, q = a.boundingBox, b.boundingBox
    if (p.maxPoint.x <= q.minPoint.x or q.maxPoint.x <= p.minPoint.x or p.maxPoint.y <= q.minPoint.y or
            q.maxPoint.y <= p.minPoint.y or p.maxPoint.z <= q.minPoint.z or q.maxPoint.z <= p.minPoint.z):
        return 0.0, ''
    c = tbm.copy(a)
    tbm.booleanOperation(c, tbm.copy(b), B.IntersectionBooleanType)
    try:
        if not c.faces.count:
            return 0.0, ''
        bb = c.boundingBox
        return c.volume * 1000, 'X %.1f..%.1f Y %.1f..%.1f Z %.1f..%.1f' % (
            bb.minPoint.x * 10, bb.maxPoint.x * 10, bb.minPoint.y * 10, bb.maxPoint.y * 10, bb.minPoint.z * 10, bb.maxPoint.z * 10)
    except Exception:
        return 0.0, ''


MATES = [{'Carrier', 'Dowel %d' % k} for k in range(1, 5)] + [{'Worm', 'Worm wheel'}, {'Motor pinion 9T', 'N20 shaft'}]  # ref shaft has no flat
STL_NAMES = {'Ring cup': 'ring_cup', 'Carrier': 'carrier', 'Planet 1': 'planet', 'Sun + 27T': 'sun_27t',
             'P1 20T/9T': 'cluster_p1', 'P2 21T/9T': 'cluster_p2', 'R1 27T/15T': 'gear_r1', 'Motor pinion 9T': 'motor_pinion', 'Bearing plate': 'bearing_plate',
             'Motor plate': 'motor_plate', 'Worm wheel': 'worm_wheel', 'Case left': 'case_left',
             'Case right': 'case_right', 'Worm': 'worm'}
COLORS = {'Ring cup': 'Plastic - Translucent Matte (Blue)', 'Carrier': 'Plastic - Glossy (Green)', 'Sun + 27T': 'Plastic - Glossy (Yellow)',
          'P1 20T/9T': 'Plastic - Glossy (Red)', 'P2 21T/9T': 'Plastic - Glossy (Red)', 'R1 27T/15T': 'Plastic - Glossy (Blue)', 'Motor pinion 9T': 'Plastic - Glossy (Yellow)'}


def mesh_states(tbm, parts, wheel_body, steps=8):
    """Turn the train through one tooth pitch of the slowest-phased mesh, in both modes, and add up any overlap."""
    hits, worst = [], 0.0
    pcs = planet_centers()

    def test(label, pairs):
        nonlocal worst
        for na, a, nb, b in pairs:
            v, w = _vol(tbm, a, b)
            worst = max(worst, v)
            if v > 0.01:
                hits.append('%s: %s / %s: %.3f mm3 at %s' % (label, na, nb, v, w))

    def planets(th_c, spin):
        out = []
        for k, pc in enumerate(pcs):
            b = _rot(tbm, parts['Planet %d' % (k + 1)], spin, pc)
            out.append(('Planet %d' % (k + 1), _rot(tbm, b, th_c, ROD)))
        return out
    zs, zr, zp = g['zs'], g['zr'], g['zp']
    for i in range(steps + 1):
        # motor mode: ring held, sun turns
        th = (2 * math.pi / zs) * 2.0 * i / steps
        thc = th * zs / (zs + zr)
        sun = _rot(tbm, parts['Sun + 27T'], th, ROD)
        k2 = g['z27'] / g['z9b']
        k3 = k2 * g['z21'] / g['z15']
        k4 = k3 * g['z27'] / g['z9b']
        p2 = _rot(tbm, parts['P2 21T/9T'], -th * k2, CL)
        r1 = _rot(tbm, parts['R1 27T/15T'], th * k3, ROD)
        p1 = _rot(tbm, parts['P1 20T/9T'], -th * k4, CL)
        pin = _rot(tbm, parts['Motor pinion 9T'], th * k4 * g['z20'] / g['z9'], MO)
        car = _rot(tbm, parts['Carrier'], thc, ROD)
        pl = planets(thc, -thc * zr / zp)
        lab = 'motor %d/%d' % (i, steps)
        test(lab, [(n, b, 'Sun + 27T', sun) for n, b in pl] + [(n, b, 'Ring cup', parts['Ring cup']) for n, b in pl] +
             [(n, b, 'Carrier', car) for n, b in pl] +
             [('Sun + 27T', sun, 'P2 21T/9T', p2), ('P2 21T/9T', p2, 'R1 27T/15T', r1), ('R1 27T/15T', r1, 'P1 20T/9T', p1),
              ('P1 20T/9T', p1, 'Motor pinion 9T', pin), ('P1 20T/9T', p1, 'P2 21T/9T', p2), ('R1 27T/15T', r1, 'Sun + 27T', sun),
              ('R1 27T/15T', r1, 'Motor plate', parts['Motor plate']), ('P1 20T/9T', p1, 'Motor plate', parts['Motor plate']),
              ('R1 27T/15T', r1, 'Motor pinion 9T', pin),
              ('Sun + 27T', sun, 'Bearing plate', parts['Bearing plate']), ('Carrier', car, 'Ring cup', parts['Ring cup']),
              ('Carrier', car, 'Worm wheel', wheel_body)])
        # wand mode: sun held, ring (and the wheel) turn
        thr = (2 * math.pi / zr) * 2.0 * i / steps
        thc = thr * zr / (zs + zr)
        cup = _rot(tbm, parts['Ring cup'], thr, ROD)
        whl = _rot(tbm, wheel_body, thr, ROD)
        car = _rot(tbm, parts['Carrier'], thc, ROD)
        pl = planets(thc, (thr - thc) * zr / zp)
        lab = 'wand %d/%d' % (i, steps)
        test(lab, [(n, b, 'Sun + 27T', parts['Sun + 27T']) for n, b in pl] + [(n, b, 'Ring cup', cup) for n, b in pl] +
             [('Ring cup', cup, 'Worm wheel', whl), ('Carrier', car, 'Ring cup', cup), ('Carrier', car, 'Worm wheel', whl),
              ('Ring cup', cup, 'Bearing plate', parts['Bearing plate'])])
    # the fast end, in fine steps: two tooth pitches of the motor pinion (the slow gears barely move)
    for i in range(steps + 1):
        tp = (2 * math.pi / g['z9']) * 2.0 * i / steps
        t1 = -tp * g['z9'] / g['z20']
        tr = -t1 * g['z9b'] / g['z27']
        t2 = -tr * g['z15'] / g['z21']
        pin = _rot(tbm, parts['Motor pinion 9T'], tp, MO)
        p1 = _rot(tbm, parts['P1 20T/9T'], t1, CL)
        r1 = _rot(tbm, parts['R1 27T/15T'], tr, ROD)
        p2 = _rot(tbm, parts['P2 21T/9T'], t2, CL)
        test('fast %d/%d' % (i, steps), [('Motor pinion 9T', pin, 'P1 20T/9T', p1), ('P1 20T/9T', p1, 'R1 27T/15T', r1),
                                         ('R1 27T/15T', r1, 'P2 21T/9T', p2), ('R1 27T/15T', r1, 'Motor pinion 9T', pin)])
    return hits, worst


def build(design, export_dir=None):
    root = design.rootComponent
    L = T4.layout()
    S = Shop(root)
    tbm = S.tbm
    parts = make_parts(S)
    refs = ref_parts(S)
    S.done()                                               # before any placement (deleting resets transform2)
    comps = {}
    for nm, b in parts.items():
        occ, comp = T4.new_component(root, nm)
        T4.add_bodies(comp, [(nm, b)])
        comps[nm] = comp
        T4.color(design, comp, COLORS.get(nm, 'Plastic - Matte (White)'))
    occ, rc = T4.new_component(root, 'REF (not printed)')
    for b in T4.add_bodies(rc, list(refs.items())):
        if b.name.startswith('Rail'):
            b.opacity = 0.2
    wocc, worm = T4.build_worm(root, L)
    hocc, wheel = build_wheel6(root, L)
    cases, bosses, mo_len, pegs = T4.build_case(root, L)
    T4.place(wocc, L['p0'], L['X'], L['d'])
    T4.place(hocc, L['rod_c'], L['n'], L['X'])
    comps.update({'Worm': worm, 'Worm wheel': wheel, 'Case left': cases['Case left'][1], 'Case right': cases['Case right'][1]})
    T4.color(design, worm, 'Plastic - Glossy (Yellow)')
    T4.color(design, wheel, 'Plastic - Glossy (Green)')
    T4.color(design, cases['Case left'][1], 'Plastic - Translucent Matte (Blue)')
    T4.color(design, cases['Case right'][1], 'Plastic - Matte (Blue)')

    world = {}                                             # every body in global coordinates
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        for j in range(o.bRepBodies.count):
            world[o.bRepBodies.item(j).name] = tbm.copy(o.bRepBodies.item(j))
    names = list(world)
    static = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            if {a, b} in MATES or (a.startswith('Rail') and b.startswith(('Rail', 'Worm', 'Case'))) or (a.startswith('Planet') and b.startswith('Planet')):
                continue
            v, w = _vol(tbm, world[a], world[b])
            if v > 0.01:
                static.append('%s / %s: %.3f mm3 at %s' % (a, b, v, w))
    hits, worst = mesh_states(tbm, parts, world['Worm wheel'])
    def play(name, c, other, pitch):                     # free rotation of one gear against a held neighbor (deg)
        n = 0
        for sgn in (1, -1):
            for k in range(1, 40):
                if _vol(tbm, _rot(tbm, parts[name], sgn * k * pitch / 80, c), parts[other])[0] > 0.005:
                    break
                n += 1
        return round(math.degrees(n * pitch / 80), 2)
    backlash = {'sun vs planet 1 (deg of sun)': play('Sun + 27T', ROD, 'Planet 1', 2 * math.pi / g['zs']),
                'ring vs planet 1 (deg of ring)': play('Ring cup', ROD, 'Planet 1', 2 * math.pi / g['zr']),
                'P2 vs sun 27T (deg of P2)': play('P2 21T/9T', CL, 'Sun + 27T', 2 * math.pi / g['z9b']),
                'R1 vs P2 (deg of R1)': play('R1 27T/15T', ROD, 'P2 21T/9T', 2 * math.pi / g['z15']),
                'P1 vs R1 (deg of P1)': play('P1 20T/9T', CL, 'R1 27T/15T', 2 * math.pi / g['z9b']),
                'pinion vs P1 (deg of pinion)': play('Motor pinion 9T', MO, 'P1 20T/9T', 2 * math.pi / g['z9'])}
    ext = {}
    for nm in list(parts) + ['N20']:
        bb = world[nm].boundingBox
        ext[nm] = 'X %.1f..%.1f Y %.1f..%.1f Z %.1f..%.1f' % (bb.minPoint.x * 10, bb.maxPoint.x * 10, bb.minPoint.y * 10,
                                                             bb.maxPoint.y * 10, bb.minPoint.z * 10, bb.maxPoint.z * 10)
    files = []
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        em = design.exportManager
        for nm, fn in STL_NAMES.items():
            path = os.path.join(export_dir, fn + '.stl')
            opt = em.createSTLExportOptions(comps[nm], path)
            opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
            em.execute(opt)
            files.append(path)
    zs, zr = g['zs'], g['zr']
    ratio = (g['z20'] / g['z9']) * (g['z27'] / g['z9b']) * (g['z21'] / g['z15']) * (g['z27'] / g['z9b']) * (1 + zr / zs)
    return dict(
        ratio={'N20 -> rod': round(ratio, 2), 'sun -> rod': round(1 + zr / zs, 3), 'wand ring -> rod': round(zr / (zs + zr), 3)},
        axes={'cluster (Y, Z)': [round(v, 2) for v in CL], 'motor (Y, Z)': [round(v, 2) for v in MO], 'orbit r': R_ORBIT},
        stations={k: round(v, 2) for k, v in X.items()},
        gears={'ring tip/root': (round(GR['tip'], 2), round(GR['root'], 2)), 'planet tip/root': (round(GP['ra'], 2), round(GP['rf'], 2)),
               'sun tip/root': (round(GS['ra'], 2), round(GS['rf'], 2))},
        static_interference=static, mesh_interference=hits, mesh_worst_mm3=round(worst, 4), backlash=backlash, extents=ext,
        exported=[os.path.basename(f) for f in files])
