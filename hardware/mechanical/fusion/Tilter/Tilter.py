"""Tilter: the motor drive that tilts one blind. Builds every printed part in place, checks them and exports STLs.

Along the rod, from the blind side (+X) to the rail's end (-X):
  main half | lid           worm + worm wheel
  bearing shell             solid block round the ring cup; the sun piece runs in its wall
  motor shell               closed gear room: the cluster, the motor pinion; the N20 screws to its back
  tray                      open-topped: N20 body, sensor gears, AS5600, DRV8833, RJ12 breakout all drop in from above
  tray lid                  two bolts on a diagonal; carries the magnet gear's cage

Global coordinates (mm): X along the rod, Y across (-Y room side), Z up from the rail floor.
Gear train, worm math and dimensions come from gear_geom.py (pure), the Fusion helpers and the worm from tilt_base.py,
fastener sizes from ../fits.py.
"""

import importlib.util
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path):
    """Load a module from a file, fresh each run (Fusion keeps old imports alive)."""
    spec = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(path))[0], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T4 = _load(os.path.join(_HERE, 'tilt_base.py'))
KIT = _load(os.path.join(_HERE, '..', 'fusion_kit.py'))   # shared checks
GG = T4.GG                                # gear_geom.py: dimensions and pure geometry
FIT = GG.FIT                              # ../fits.py
adsk = T4.adsk
P = GG.P
B = adsk.fusion.BooleanTypes
OVERLAP_MM3 = 0.01                        # any overlap bigger than this between two bodies is a failure

RZ, A, G, g, X = GG.RZ, GG.A, GG.G, GG.G, GG.X      # rod height, lid face, gear train sizes, X stations
GS, GP, GR, G27, G9B, G20, G9 = GG.GS, GG.GP, GG.GR, GG.G27, GG.G9B, GG.G20, GG.G9
R_ORBIT, CL, MO, ROD = GG.R_ORBIT, GG.CL, GG.MO, GG.ROD
profile, phases, planet_centers, ngon, hex_a0 = GG.profile, GG.phases, GG.planet_centers, GG.ngon, GG.hex_a0


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
        return T4.brep(GG.box_minmax(min(xa, xb), max(xa, xb), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)), self.tbm)

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


def make_parts(S):
    """Every new printed part as {name: body}, in place."""
    ph = phases()
    out = {}
    # ring cup: floor with the hex socket (wheel's hex), 32T inside, open toward -X
    cup = S.cyl(ROD, g['ring_ro'], X['floor0'], X['pl1'])
    S.D(cup, S.gear(GR, ROD, ph['ring'], X['floor1'], X['pl1'] - 1, internal=True),
        S.prism(ngon(ROD, g['hex_R'] + g['hex_clear'], 6, hex_a0()), X['floor0'] + 1, X['floor1'] - 1))
    out['Ring cup'] = cup
    # carrier: disc + long hub (inside the wheel's bore) with the square bore, 4 dowel pockets
    car = S.U(S.cyl(ROD, g['disc_r'], X['disc0'], X['disc1']), S.cyl(ROD, g['hub_r'], X['disc0'], g['hub_end_x']))
    h = FIT.ROD_BORE / 2
    S.D(car, S.box(g['hub_end_x'] + 1, X['disc1'] - 1, -h, h, RZ - h, RZ + h))
    for pc in planet_centers():
        S.D(car, S.cyl(pc, g['pin_d'] / 2 - g['pin_press'], X['disc1'] - 1, X['disc1'] + g['pin_pocket']))
    kw, kr, kd = g['lug_w'] / 2 + g['lug_clear'], g['nose_r'] + 0.1, g['lug_len'] + 0.2      # slots for the sleeve's four lugs
    S.D(car, S.box(X['disc1'] - 1, X['disc1'] + kd, -kw, kw, RZ - kr, RZ + kr), S.box(X['disc1'] - 1, X['disc1'] + kd, -kr, kr, RZ - kw, RZ + kw))
    out['Carrier'] = car
    for k, (pc, (_, rot)) in enumerate(zip(planet_centers(), ph['planets'])):
        pl = S.gear(GP, pc, rot, X['pl0'], X['pl1'])
        S.D(pl, S.cyl(pc, g['pin_d'] / 2 + g['planet_bore_clear'], X['pl0'] + 1, X['pl1'] - 1))
        out['Planet %d' % (k + 1)] = pl
    # sun piece: 16T + journal (runs in the bearing plate) + 27T
    sun = S.U(S.gear(GS, ROD, ph['sun'], X['pl0'], X['pl1'] - 0.1),
              S.cyl(ROD, GS['ra'], X['pl1'], X['a0'] - 0.01),
              S.gear(G27, ROD, ph['g27'], X['a0'], X['a1']))
    S.D(sun, S.cyl(ROD, g['sun_bore'], X['pl0'] + 1, X['a1'] - 1))
    out['Sun + 27T'] = sun
    # the one cluster: 9T on the sun piece's 27T, 20T on the motor pinion
    cl = S.U(S.gear(G9B, CL, ph['g9b'], X['a1'], X['d1'] + 0.01), S.gear(G20, CL, ph['g20'], X['d1'], X['d0']))
    S.D(cl, S.cyl(CL, g['axle_bore'], X['d0'] + 1, X['a1'] - 1))
    out['Cluster 20T/9T'] = cl
    # motor pinion, D-bore on the N20's flat
    pin = S.gear(G9, MO, ph['g9'], X['d0'], X['d1'])
    r = P['n20_shaft_d'] / 2 + 0.05
    fx = P['n20_flat'] - P['n20_shaft_d'] / 2 + 0.05
    dpts = [(MO[0] + min(r * math.cos(t), fx), MO[1] + r * math.sin(t)) for t in [2 * math.pi * i / 48 for i in range(48)]]
    S.D(pin, S.prism(dpts, X['d0'] + 1, X['d1'] - 1))
    out['Motor pinion 9T'] = pin
    return out


# ------------------------------------------------------------------ worm wheel (free on the rod) and the lid
def build_wheel(root, L):
    """Worm wheel: teeth cut by the worm's motion, a round bore (the rod turns inside it), a lid-side barrel ending in a
    hex that drives the ring cup, and a counterbore for the carrier's hub. Wheel-local z = global X."""
    occ, comp = T4.new_component(root, 'Worm wheel')
    fw, ns = P['wheel_face'], P['wheel_slices']
    T4.loft_sections(comp, [(-fw / 2 + fw * i / (ns - 1), GG.wheel_section(-fw / 2 + fw * i / (ns - 1))) for i in range(ns)], smooth=False)
    x0, x1 = GG.slab_x(L)
    zb = A - 0.3                                           # round barrel ends just outside the lid face
    T4.extrude(comp, T4.circle_profile(comp, zb, g['hex_R']), -fw / 2 + 0.3 - zb, T4.JOIN)
    T4.extrude(comp, T4.circle_profile(comp, fw / 2 - 0.3, P['barrel_r']), x1 - 0.2 - fw / 2 + 0.3, T4.JOIN)
    zh = X['floor1'] + 0.1
    sk = comp.sketches.add(T4.offset_plane(comp, zh))
    T4.polyline(sk, ngon((0, 0), g['hex_R'], 6))
    T4.extrude(comp, T4.largest_profile(sk), zb - zh + 0.01, T4.JOIN)
    T4.merge_bodies(comp)
    T4.extrude(comp, T4.circle_profile(comp, zh, FIT.ROD_HOLE_R), x1 - zh, T4.CUT)
    T4.extrude(comp, T4.circle_profile(comp, zh, g['wheel_bore_hub']), g['hub_end_x'] + 0.5 - zh, T4.CUT)
    comp.bRepBodies.item(0).name = 'Worm wheel'
    return occ, comp


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


def mesh_states(tbm, parts, wheel_body, steps=8):
    """Turn the train through one tooth pitch of the slowest-phased mesh, in both modes, and add up any overlap."""
    hits, worst = [], 0.0
    pcs = planet_centers()

    def test(label, pairs):
        nonlocal worst
        for na, a, nb, b in pairs:
            v, w = _vol(tbm, a, b)
            worst = max(worst, v)
            if v > OVERLAP_MM3:
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
        cl = _rot(tbm, parts['Cluster 20T/9T'], -th * k2, CL)
        pin = _rot(tbm, parts['Motor pinion 9T'], th * k2 * g['z20'] / g['z9'], MO)
        slv = _rot(tbm, parts['Sensor sleeve'], thc, ROD)
        car = _rot(tbm, parts['Carrier'], thc, ROD)
        pl = planets(thc, -thc * zr / zp)
        lab = 'motor %d/%d' % (i, steps)
        test(lab, [(n, b, 'Sun + 27T', sun) for n, b in pl] + [(n, b, 'Ring cup', parts['Ring cup']) for n, b in pl] +
             [(n, b, 'Carrier', car) for n, b in pl] +
             [('Sun + 27T', sun, 'Cluster 20T/9T', cl), ('Cluster 20T/9T', cl, 'Motor pinion 9T', pin),
              ('Cluster 20T/9T', cl, 'Motor shell', parts['Motor shell']), ('Sun + 27T', sun, 'Motor pinion 9T', pin),
              ('Sensor sleeve', slv, 'Sun + 27T', sun), ('Sensor sleeve', slv, 'Carrier', car), ('Sensor sleeve', slv, 'Cluster 20T/9T', cl),
              ('Sensor sleeve', slv, 'Motor shell', parts['Motor shell']), ('Sensor sleeve', slv, 'Tray', parts['Tray']),
              ('Sun + 27T', sun, 'Bearing shell', parts['Bearing shell']), ('Carrier', car, 'Ring cup', parts['Ring cup']),
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
              ('Ring cup', cup, 'Bearing shell', parts['Bearing shell'])])
    # the fast end, in fine steps: two tooth pitches of the motor pinion (the slow gears barely move)
    for i in range(steps + 1):
        tp = (2 * math.pi / g['z9']) * 2.0 * i / steps
        t1 = -tp * g['z9'] / g['z20']
        ts = -t1 * g['z9b'] / g['z27']
        pin = _rot(tbm, parts['Motor pinion 9T'], tp, MO)
        cl = _rot(tbm, parts['Cluster 20T/9T'], t1, CL)
        sun = _rot(tbm, parts['Sun + 27T'], ts, ROD)
        test('fast %d/%d' % (i, steps), [('Motor pinion 9T', pin, 'Cluster 20T/9T', cl), ('Cluster 20T/9T', cl, 'Sun + 27T', sun)])
    return hits, worst


# ================================================================== housing
p1 = X['plate1']
H = dict(
    hw=25.75, wall=2.0, floor=1.2,      # tray: 2 mm walls
    # outline (Y, Z), counter-clockwise from the room-side bottom corner: square on top (under the rail's lips), the
    # bottom corners chamfered 8 mm on the back (sensor) side, 3 mm on the room side
    F=[(-22.75, 0.2), (17.75, 0.2), (25.75, 8.2), (25.75, 33.2), (-25.75, 33.2), (-25.75, 3.2)],
    roof_r=15.9, cup_bore=14.9, gear_bore=14.8, wheel_roof_r=9.6,
    case_bolts=((18.5, 28.5), (-12.0, 5.0)),                    # M3 x 25, two on a diagonal
    tray_bolts=(CL, (11.0, 5.2)),          # M3 x 20: tray (heads on lugs inside it) -> through the motor shell -> inserts in the bearing shell; the room-side one is the cluster's axle
    pegs=((21.0, 18.0), (-3.0, 6.0)),
    bolt=25.0, tray_bolt=20.0, boss=4.6, head_back=4.0, short=8.0,          # tray bolts M3 x 20; the lid's corner bolt M3 x 8
    lid_z=31.2,                                                 # the tray is open above this; the lid is the 2 mm on top
    end_wall=2.0,
    as_hole=8.0, stud_d=3.6,     # AS5600: four holes, 8 mm out from the middle each way. Studs 3.6 (3.75 printed too tight)
    chip_h=1.5, mag_gap=0.8, board=23.4, board_t=1.6,
    # RJ12 breakout (owner's caliper numbers): board 20 x 20.25 x 1.5, jack 12.3 wide, 14.7 off the board (re-measured on the print, 2026-11-14), 14.7 long,
    # mouth 2.75 past the board's edge. It stands along the ROOM-side wall, beside the motor, jack toward the rod.
    rj_bw=20.0, rj_bd=20.25, rj_t=1.5, rj_jw=12.3, rj_jl=14.7, rj_jh=14.7, rj_over=2.75,
    rj_yb=-23.2, rj_x0=p1 - 1.5, rj_pin=1.6,                       # board's back face (Y), its +X edge; room for solder joints behind it
    # (-23.2: the jack is 14.7 tall, so the board sits 1.5 nearer the wall to clear the rod gear; pins go into a wall pocket)
    # DRV8833: upright under the RJ12 jack, between the board and the motor
    drv_w=16.0, drv_l=18.5, drv_t=1.6, drv_y=-13.0, drv_z=1.6, drv_x0=p1 - 4.3,
    end_bay=5.6,                         # room behind the boards
    lid_bolt=(-20.0, 29.7),              # lid's corner bolt (Y, insert top): 1.5 under the tray's rim, the lid's spigot in a socket above it
    # sensor gears: 8T, normal module 1.0, 45° helix, same hand, axes crossed at 90°
    sg_z=8, sg_face=5.4, sleeve_r=4.0, hub_r=3.0, mag_r=1.97, mag_t=2.05,
    board_z=14.5,                                               # AS5600 board's underside (chip on top)
    key=(-27.45, -19.5, -1.8, 0.3), key_hw=5.85,
    cheek=(-27.45, -25.0, 0.2, 15.0), cheek_hw=7.0,            # covers the worm's collar where it nears the room-side wall
)
h = H
F = h['F']
ZL = h['lid_z']
F_CASE = [(-25.75, 0.2), F[1], F[2], F[3], F[4]]                   # worm case: the worm leaves through the front bottom corner, no chamfer there
FT = [F[0], F[1], F[2], (25.75, ZL), (-25.75, ZL), F[5]]         # tray outline (open at the lid line)
FL = [(-25.75, ZL), (25.75, ZL), (25.75, 33.2), (-25.75, 33.2)]  # lid outline
SG = GG.helical(h['sg_z'])
SG_CD = 2 * SG['rp'] + P['hx_cd_extra']
MG = (SG_CD, RZ)                   # magnet gear's axis (Y, and the height of its middle)
xa1 = p1                           # the motor shell's back face: the AS5600 board's stop
bx0 = xa1 - 0.2                    # AS5600 board, +X edge
xg = bx0 - h['board'] / 2          # sensor gears' station (the board's middle)
bx1 = bx0 - h['board']             # AS5600 board, -X edge
RJM = 33.2                                                        # jack mouth: flush with the lid's top
RJZ0 = RJM - h['rj_over'] - h['rj_bd']                            # board's bottom edge
RJX = (h['rj_x0'], h['rj_x0'] - h['rj_bw'])                       # board's two upright edges
xin = bx1 - h['end_bay']           # end wall, inside
xe1 = xin - h['end_wall']          # end of the device
xh = p1 - h['head_back']           # tray bolts: where the head's top sits
SPIG = 2.9                         # radius of the lid's spigot at the corner bolt
XLB = xin + 3.0                    # lid's corner bolt: in the far room-side corner, in front of the RJ12 board's plane
by0, by1 = MG[0] - h['board'] / 2, MG[0] + h['board'] / 2
Z_CHIP = h['board_z'] + h['board_t'] + h['chip_h']
Z_MAG = Z_CHIP + h['mag_gap']      # magnet's face (looking down at the chip)
ZG0, ZG1 = RZ - h['sg_face'] / 2, RZ + h['sg_face'] / 2
BR = (ZG0 - 1.8, ZG0 - 0.3)        # sensor bridge's plate (the magnet gear turns on it, hub through its hole)
Z_BT = h['board_z'] + h['board_t']
HX = (xg + h['as_hole'], xg - h['as_hole'])                      # the board's holes
HY = (MG[0] - h['as_hole'], MG[0] + h['as_hole'])
XS = dict(rib_a_back=xa1, board_front=bx0, sensor_gears=xg, board_back=bx1, rj_board_bottom_z=RJZ0, rj_mouth_z=RJM,
          end_inside=xin, end=xe1, tray_head=xh, lid_bolt_x=XLB)
CASE_X1 = P['main_half']


def inset(poly, offs):
    """Convex CCW polygon moved in by offs[i] on edge i (point i -> i + 1)."""
    n = len(poly)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        L = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        lines.append((nx, ny, nx * x0 + ny * y0 + offs[i]))
    out = []
    for i in range(n):
        a1, b1, c1 = lines[i - 1]
        a2, b2, c2 = lines[i]
        det = a1 * b2 - a2 * b1
        out.append(((c1 * b2 - c2 * b1) / det, (a1 * c2 - a2 * c1) / det))
    return out


FINT = inset(FT, [h['floor'], 1.8, h['wall'], -1.0, h['wall'], 1.6])     # tray's inside (open at the top)


def body(S, xa, xb):
    return S.prism(F, xa, xb)


def clip(S, part, outer):
    S.tbm.booleanOperation(part, S.tbm.copy(outer), B.IntersectionBooleanType)
    return part


def csink(S, b, c, x_face, sgn):
    """Countersink in the face at x_face, opening toward sgn (the outside)."""
    S.D(b, S.cyl(c, FIT.CSINK_R, x_face + sgn * 0.01, x_face - sgn * FIT.CSINK_H, FIT.M3_R))


def zcyl(S, x, y, r, z0, z1, r2=None):
    return S.tbm.createCylinderOrCone(T4.P3((x, y, z0)), r / 10, T4.P3((x, y, z1)), (r if r2 is None else r2) / 10)


# ---- locating pins between the housing parts, like the worm case's own: Ø2.5 x 2 pins in Ø2.8 holes, two per
# joint, far apart. A pin always grows from a face that is UP when its part prints; the hole is in the other part.
PEG_A = ((21.0, 18.0), (-3.0, 6.0))      # worm case's lid <- bearing shell (pins on the shell's front face)
PEG_W = ((21.0, 18.0), (-21.0, 30.0))    # bearing shell <- motor shell (pins on the motor shell's open face)
PEG_T = ((19.5, 6.5), (-21.9, 6.0))      # motor shell <- tray (pins on the tray's front face: they print lying sideways, so they are diamonds)
PEG_R, PEG_H = FIT.PEG_D / 2, FIT.PEG_H
PEG_HOLE_R, PEG_HOLE_H = PEG_R + FIT.PEG_CLEAR, PEG_H + FIT.PEG_DEPTH_EXTRA


def bearing_shell(S):
    w0, w1 = X['wall0'], X['wall1']
    b = S.U(body(S, A, w1), S.cyl(ROD, h['roof_r'], A, w1))
    S.D(b, S.cyl(ROD, h['cup_bore'], A + 1, w0), S.cyl(ROD, GS['ra'] + g['journal_clear'], w0 + 1, w1 - 1))
    for c in PEG_A:                                        # pins into the worm case's lid
        S.U(b, S.cyl(c, PEG_R, A - 0.5, A + PEG_H))
    for c in PEG_W:                                        # holes for the motor shell's pins
        S.D(b, S.cyl(c, PEG_HOLE_R, w1 - 0.1, w1 + PEG_HOLE_H))
    for c in h['case_bolts']:                              # inserts at the lid end
        S.D(b, S.cyl(c, FIT.INSERT_R, A + 1, A - FIT.INSERT_LEN_TILTER), S.cyl(c, FIT.M3_R, A, A - 9.0))
    S.D(b, S.cyl(MO, 1.9, w1 - 1, p1 + P['n20_shaft_len'] + 0.5))   # the motor shaft's tip goes through the skin into a pocket in the block behind it
    for c in h['tray_bolts']:                              # inserts pressed in from the gear side
        S.D(b, S.cyl(c, FIT.INSERT_R, w1 - 1, w1 + FIT.INSERT_LEN_TILTER), S.cyl(c, FIT.M3_R, w1, xh + h['tray_bolt'] + 0.8))
    return b


def motor_shell(S):
    w1, q0 = X['wall1'], X['plate0']
    outer = S.U(body(S, w1, p1), S.cyl(ROD, h['roof_r'], w1, p1))
    b = S.tbm.copy(outer)
    # the gear room is the gears' negative. Solid everywhere except a pocket round each gear at its own
    # depth, with about 0.6 mm of room round the teeth. Each gear still drops straight in from the open face.
    xt = X['a0']                                          # the step: 0.3 under the 20T and the motor pinion
    S.D(b, S.cyl(ROD, h['gear_bore'], w1 + 1, q0),        # 27T at the bottom (and its way in); the sun's journal above it
        S.cyl(CL, G20['ra'] + 0.66, w1 + 1, xt),          # cluster: 20T on top ...
        S.cyl(CL, G9B['ra'] + 0.5, xt + 0.01, q0),        # ... its 9T below, beside the 27T
        S.cyl(MO, G9['ra'] + 0.6, w1 + 1, xt))            # motor pinion: its pocket's floor is the land that keeps it up the shaft
    S.D(b, S.cyl(ROD, g['nose_r'] + g['nose_clear'], q0 + 1, p1 - 1))                  # the sleeve's front bearing
    S.D(b, S.cyl(MO, 1.75, xt + 1, p1 - 1), S.cyl(MO, 2.3, p1 - 1, q0 + 0.3))          # motor shaft; the motor's boss
    # N20's two M1.6 x 4 screws: Ø3.5 wells from the open face down to 1.8 mm above the motor (2.2 mm of thread in the motor)
    for sg in (-1, 1):
        c = (MO[0] + sg * P['n20_screw_spacing'] / 2, MO[1])
        S.D(b, S.cyl(c, FIT.M1_6_R, w1 + 1, p1 - 1), S.cyl(c, FIT.M1_6_HEAD_R, w1 + 1, p1 + 1.8))
        dv = (CL[0] - c[0], CL[1] - c[1])
        dn = math.hypot(*dv)
        if dn - FIT.M1_6_HEAD_R - (G9B['ra'] + 0.5) < 1.0:              # the well next to the 9T's pocket: open the 0.5 mm sliver between them
            S.D(b, S.cyl((c[0] + dv[0] / dn * 2.1, c[1] + dv[1] / dn * 2.1), 1.3, xt + 0.01, p1 + 1.8))
    for c in h['tray_bolts']:                             # the tray's bolts pass through
        S.D(b, S.cyl(c, FIT.M3_R, w1 + 1, p1 - 1))
    for c in PEG_W:                                       # pins into the bearing shell
        S.U(b, S.cyl(c, PEG_R, w1 - 0.5, w1 + PEG_H))
    for c in PEG_T:                                       # holes for the tray's pins (the shell is solid here behind the thin plate)
        S.D(b, S.cyl(c, PEG_HOLE_R, p1 - 0.1, p1 + PEG_HOLE_H))
    return b


def rj_y():
    """RJ12 breakout: board back, board front (jack side), jack's far face (toward the rod)."""
    yb = h['rj_yb']
    return yb, yb + h['rj_t'], yb + h['rj_t'] + h['rj_jh']


def drv_x():
    return h['drv_x0'], h['drv_x0'] - h['drv_l']           # board +X, board -X


def tray(S):
    """Open-topped tray: bolts to the motor shell's back. Everything drops in from above. Every mount grows out of a
    wall or a rib. Back side: the AS5600. Room side: the RJ12 (in two slotted ribs) with the DRV8833 under its jack."""
    hw = h['hw']
    iw = hw - h['wall'] + 0.1                              # just into the side wall
    outer = S.prism(FT, p1, xe1)
    b = S.tbm.copy(outer)
    S.D(b, S.prism(FINT, p1 + 1, xin))
    bz = h['board_z']
    c2, c1 = h['tray_bolts']                               # c2: room side, on the cluster's axle.  c1: floor
    B2 = 4.0                                               # its lug is a little smaller: the motor's gearbox is right beside it
    shelf = [(3.1, 11.6), (3.1, bz), (0.9, bz), (0.9, 13.8)]            # 45° shelf over the motor's edge
    add = []
    # AS5600 board: flat, chip up. Back pair of holes: M3 inserts in buttresses on the back wall.
    # Front pair: studs on a rail that runs from rib A to the end wall. Back pair: one M3 insert (near the motor
    # shell) and one more stud.
    add += [S.box(xa1, xin, 3.1, 7.0, 0.9, bz), S.prism(shelf, xa1, xin)]
    studs = [(hx, HY[0]) for hx in HX] + [(HX[1], HY[1])]
    for hx in HX:
        add += [S.box(hx - 4.2, hx + 4.2, 15.3, iw, 0.9, bz)]
    for sx, sy in studs:
        add += [zcyl(S, sx, sy, h['stud_d'] / 2, bz - 0.5, Z_BT + 1.0),
                zcyl(S, sx, sy, h['stud_d'] / 2, Z_BT + 0.99, Z_BT + 1.5, h['stud_d'] / 2 - 0.5)]
    # two short lugs for the tray's bolts (M3 x 20, heads inside, the driver comes through holes in the end wall)
    add += [S.cyl(c1, h['boss'], p1, xh), S.box(p1, xh, c1[0] - h['boss'], c1[0] + h['boss'], 0.9, c1[1]),
            S.cyl(c2, B2, p1, xh), S.box(p1, xh, -iw, c2[0], c2[1], c2[1] + B2),
            S.prism([(-iw, c2[1] - c2[0] - iw - B2 * math.sqrt(2)), (c2[0] + B2 * math.sqrt(0.5), c2[1] - B2 * math.sqrt(0.5)),
                     c2, (-iw, c2[1] + B2)], p1, xh)]
    # two ribs on the room-side wall. Upper part: a slot for each upright edge of the RJ12 board.
    # Lower part (reaches further in): a slot for each end of the DRV8833.
    yb, yf, yj = rj_y()
    d0, d1 = drv_x()
    ya, yc, z0 = h['drv_y'], h['drv_y'] + h['drv_t'], h['drv_z']
    for sg, xr, xd in ((1, RJX[0], d0), (-1, RJX[1], d1)):
        add += [S.box(xr + sg * 1.5, xr - sg * 1.2, -iw, yf + 1.6, 0.9, 19.0),
                S.box(xr + sg * 1.5, xd - sg * 1.2, -iw, yc + 1.4, 0.9, RJZ0 - 0.4)]
    # behind the DRV8833's far end the low block runs solid to the end wall
    add += [S.box(xin, d1 + 1.2, -iw, yc + 1.4, 0.9, RJZ0 - 0.4)]
    # block for the lid's corner bolt: fills the corner between the end wall, the room-side wall and the far RJ12 rib
    ly, lz = h['lid_bolt']
    add += [S.box(xin, XLB + 4.2, -iw, ly + 4.2, 0.9, ZL)]                # right up to the rim: the lid sits on it
    for a_ in add:
        S.U(b, a_)
    clip(S, b, outer)
    S.D(b, S.cyl(ROD, FIT.ROD_HOLE_R, xin + 0.5, xe1 - 1),                                                # end wall: just a hole for a long rod
        S.box(p1 + 1, p1 - 28.5, MO[0] - 6.3, MO[0] + 6.3, 0.95, 2.0),                              # the motor sits in a shallow dip in the floor
        S.box(RJX[0] + 0.15, RJX[1] - 0.15, yb - 0.15, yf + 0.15, RJZ0, ZL + 1),                    # RJ12 board's slots (it stands on their floors)
        S.box(RJX[0] - 1.2, RJX[1] + 1.2, -iw + 0.3, yf + 2.0, RJZ0 - 0.41, ZL + 1),                # ... open between the two ribs
        S.box(RJX[0] - 2.3, RJX[1] + 2.3, -iw - 1.1, -iw + 0.4, RJZ0 + 0.3, ZL + 1),                # pocket in the wall for the board's solder joints (0.8 skin left)
        S.box(d0 + 0.15, d1 - 0.15, ya - 0.15, yc + 0.15, z0, RJZ0),                                # DRV8833's slots
        zcyl(S, XLB, ly, SPIG + 0.15, lz, ZL + 1),                                                  # socket for the lid's spigot: the lid finds its place
        zcyl(S, XLB, ly, FIT.INSERT_R, lz + 0.1, lz - FIT.INSERT_LEN_TILTER), zcyl(S, XLB, ly, FIT.M3_R, lz, 33.2 - h['short'] - 0.8))
    # wire way in the end bay (AS5600 -> RJ12): the stud rail stops just past the far stud, its end rounded; the
    # corner block's free corner is rounded too. Wires lie on a flat floor and bend round r 1.5, not a sharp edge.
    xr, fz, r = HX[1] - 2.4, 0.2 + h['floor'], 1.5
    S.D(b, S.box(xin, xr, 0.8, 7.1, fz, bz + 0.1),
        S.box(xr - 0.01, xr + r, 3.09, 3.1 + r, fz, 11.5), S.box(xr - 0.01, xr + r, 7.0 - r, 7.01, fz, 11.5))
    S.U(b, zcyl(S, xr + r, 3.1 + r, r, fz - 0.1, 11.5), zcyl(S, xr + r, 7.0 - r, r, fz - 0.1, 11.5))
    xc, yc, zc = XLB + 4.2, ly + 4.2, RJZ0 - 0.4          # the block's free corner, above the low block it stands in
    S.D(b, S.box(xc - r, xc + 0.01, yc - r, yc + 0.01, zc, ZL + 0.1))
    S.U(b, zcyl(S, xc - r, yc - r, r, zc - 0.1, ZL))
    S.D(b, zcyl(S, XLB, ly, SPIG + 0.15, lz, ZL + 1))      # re-open the socket
    for hx in HX[:1]:                                      # insert for the sensor bolt
        S.D(b, zcyl(S, hx, HY[1], FIT.INSERT_R, bz + 0.1, bz - FIT.INSERT_LEN_TILTER), zcyl(S, hx, HY[1], FIT.M3_R, bz, 33.2 - h['bolt'] - 0.8))
    for c in h['tray_bolts']:
        S.D(b, S.cyl(c, FIT.M3_R, xh, p1 + 1), S.cyl(c, FIT.CSINK_R, xh - 0.01, xh + FIT.CSINK_H, FIT.M3_R),
            S.cyl(c, 3.5, xh, xe1 - 1))                                                             # driver's path
    for y_, z_ in PEG_T:                                   # pins into the motor shell: diamonds (each layer steps out at 45 deg, no support)
        S.U(b, S.prism([(y_, z_ - PEG_R), (y_ + PEG_R, z_), (y_, z_ + PEG_R), (y_ - PEG_R, z_)], p1 - 0.5, p1 + PEG_H))
    return b


def lid(S):
    """Lid = cover + sensor mount, one unit. Two columns stand on the AS5600's back corners. Two bolts on a diagonal
    hold it: one down through a column and the board into an insert in the tray, one in the far room-side corner
    (a spigot locates it there). Between the columns hangs the GEAR CAGE: a block over the magnet gear, two cheeks and
    a back wall, and a shelf under the gear with a keyhole for the gear's hub. The gear slides in from the rod side and
    its hub snaps past two small bumps into the round seat, so it is held all round, right above the sensor. The RJ12
    jack comes up through a close opening, flush with the top. Prints top down, with support under the shelf."""
    b = S.prism(FL, p1, xe1)
    ly, lz = h['lid_bolt']
    yb, yf, yj = rj_y()
    jx0 = (RJX[0] + RJX[1]) / 2 + h['rj_jw'] / 2
    add = [S.box(FING[0], FING[1], -5.0, 7.1, FING_Z, ZL),                                          # square stop behind the top of the sleeve's gear, part of the gear block. It ends above the magnet gear (that gear slides in under it) and above a long rod
           zcyl(S, XLB, ly, SPIG, lz + 0.2, ZL),                                                    # short spigot into the corner block's socket
           S.box(xg - 8.4, xg + 8.4, 7.0, HY[1] + 1.0, ZG1 + 0.3, ZL),                              # block over the gear
           S.box(xg - 8.4, xg + 8.4, SG['ra'] + MG[0] + 0.6, HY[1] + 1.0, BR[0], ZG1 + 0.31),       # back wall
           S.box(xg - 8.4, xg + 8.4, 6.4, HY[1] + 1.0, BR[0], BR[1]),                               # shelf under the gear
           zcyl(S, xg, MG[0], 4.6, Z_CHIP + 0.3, BR[0] + 0.01),                                     # longer seat for the hub
           S.box(xg - 4.6, xg + 4.6, 6.4, MG[0], Z_CHIP + 0.3, BR[0] + 0.01)]
    add += [S.box(xg + sg * 7.0, xg + sg * 8.4, 7.4, HY[1] + 1.0, BR[1] - 0.01, ZG1 + 0.31) for sg in (-1, 1)]   # cheeks
    add += [zcyl(S, hx, HY[1], 3.8, Z_BT + 0.05, ZL) for hx in HX]                                  # columns down onto the board
    for a_ in add:
        S.U(b, a_)
    S.D(b, S.cyl(ROD, h['sleeve_r'] + 0.15, p1 + 1, FING[1] + 0.01),
        zcyl(S, HX[1], HY[1], h['stud_d'] / 2 + 0.25, Z_BT - 1, Z_BT + 1.8),                        # the far column sits over a stud
        S.box(jx0 + 0.3, jx0 - h['rj_jw'] - 0.3, yf - 0.3, yj + 0.3, 20.0, 40.0),                   # the jack, flush
        zcyl(S, xg, MG[0], h['hub_r'] + 0.15, Z_BT, BR[1] + 0.01),                                  # keyhole: round seat ...
        S.box(xg - h['hub_r'] - 0.15, xg + h['hub_r'] + 0.15, 0.0, MG[0], Z_BT, BR[1] + 0.01))      # ... and the way in from the rod side
    for sg in (-1, 1):                                     # two bumps the hub snaps past (0.1 mm tight each side)
        S.U(b, zcyl(S, xg + sg * (h['hub_r'] + 0.15 + 0.55), MG[0] - h['hub_r'] - 0.9, 0.8, Z_CHIP + 0.3, BR[1]))
    for x_, y_ in ((XLB, ly), (HX[0], HY[1])):                # two bolts, on a diagonal
        S.D(b, zcyl(S, x_, y_, FIT.M3_R, 0.0, 40.0), zcyl(S, x_, y_, FIT.CSINK_R, 33.21, 33.2 - FIT.CSINK_H, FIT.M3_R))
    return b


def helical_tb(S, face, origin, xax, yax, zax):
    """8T 45° helical gear as a TemporaryBRep body, its axis (local z, 0 -> face) placed in global coordinates."""
    f = T4.helical_body(S.comp, SG, 0.0, face)
    b = S.tbm.copy(f.bodies.item(0))
    m = adsk.core.Matrix3D.create()
    m.setWithCoordinateSystem(T4.P3(origin), T4.V3(xax), T4.V3(yax), T4.V3(zax))
    S.tbm.transform(b, m)
    return b


XGR = xg - h['sg_face'] / 2        # the sleeve gear's back face = the sleeve's end
FING = (XGR - 2.1, XGR - 0.3)      # the lid's stop block behind it
FING_Z = max(ZG1 + 0.6, RZ + 3.4)  # its underside


def rod_gear(S):
    """SENSOR SLEEVE. A short tube with the rod's square bore right through it. Its back end is the 8T helical gear over
    the sensor; from there a nose runs forward through the motor plate (its bearing) and the sun piece and ends in four
    lugs that sit in the carrier's back. It floats: the lugs stop it toward the front, a finger under the lid stops it
    toward the back. Prints standing on the gear's flat back face, lugs up."""
    fw = h['sg_face']
    b = helical_tb(S, fw, (XGR, 0.0, RZ), (0, 1, 0), (0, 0, 1), (1, 0, 0))
    xn = X['disc1'] - 0.3                                  # nose's shoulder: 0.3 behind the carrier's back
    nr = g['nose_r']
    S.U(b, S.cyl(ROD, h['sleeve_r'], p1 - 0.3, XGR), S.cyl(ROD, nr, p1 - 0.31, xn))
    lw, xl = g['lug_w'] / 2, X['disc1'] + g['lug_len']
    lugs = S.cyl(ROD, nr, xn - 0.5, xl)
    S.tbm.booleanOperation(lugs, S.U(S.box(xn, xl + 1, -lw, lw, RZ - 5, RZ + 5), S.box(xn, xl + 1, -5, 5, RZ - lw, RZ + lw)), B.IntersectionBooleanType)
    S.U(b, lugs)
    k = FIT.ROD_BORE / 2
    S.D(b, S.box(xl + 1, XGR - 1, -k, k, RZ - k, RZ + k))  # the rod's bore, plain at both ends
    return b


def magnet_gear(S):
    """8T helical on an upright axis; the hub under it carries the magnet over the chip and runs in the keyhole of the
    lid's gear cage. Prints top face down."""
    b = helical_tb(S, h['sg_face'], (xg, MG[0], ZG0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    S.tbm.booleanOperation(b, zcyl(S, xg, MG[0], h['hub_r'], Z_MAG, ZG0 + 0.01), B.UnionBooleanType)
    S.tbm.booleanOperation(b, zcyl(S, xg, MG[0], h['mag_r'], Z_MAG - 1, Z_MAG + h['mag_t']), B.DifferenceBooleanType)
    return b


def _rotz(tbm, bdy, ang, c):
    m = adsk.core.Matrix3D.create()
    m.setToRotation(ang, T4.V3((0, 0, 1)), T4.P3((c[0], c[1], 0)))
    nb = tbm.copy(bdy)
    tbm.transform(nb, m)
    return nb


def housing_parts(S):
    out = {'Bearing shell': bearing_shell(S), 'Motor shell': motor_shell(S), 'Tray': tray(S), 'Lid': lid(S),
           'Sensor sleeve': rod_gear(S)}
    mg = magnet_gear(S)                                    # turn it to the tooth phase that clears the rod gear
    best = None
    for k in range(24):
        cand = _rotz(S.tbm, mg, 2 * math.pi / h['sg_z'] * k / 24, (xg, MG[0]))
        v = _vol(S.tbm, cand, out['Sensor sleeve'])[0]
        if best is None or v < best[0]:
            best = (v, cand)
    out['Magnet gear'] = best[1]
    return out


SHOULDER_SKIN = 2.0                # plastic between the worm's pocket and the shoulder's sloped side


def shoulder_pts(cav):
    """(Y, Z) outline of the shoulder beside the hump, over the worm's top end. Its sloped side runs parallel to the worm
    (to the edge of the worm's pocket), SHOULDER_SKIN outside it."""
    wt = [pr for pr in cav if getattr(pr, 'label', '') == 'worm threads'][0]
    (ay, az), (by, bz_) = (wt.p1[1], wt.p1[2]), (wt.p2[1], wt.p2[2])
    if bz_ < az:
        (ay, az), (by, bz_) = (by, bz_), (ay, az)
    ln = math.hypot(by - ay, bz_ - az)
    dy, dz = (by - ay) / ln, (bz_ - az) / ln               # along the worm, upward
    ny, nz = -dz, dy                                       # across it, toward the room side and up
    c0 = ay * ny + az * nz + max(wt.r, getattr(wt, 'r2', None) or wt.r) + SHOULDER_SKIN
    yat = lambda z: (c0 - nz * z) / ny
    return [(yat(33.0), 33.0), (yat(39.9), 39.9), (-1.0, 39.9), (-1.0, 33.0)]


def case_halves(S, L):
    """Main half + lid round the worm and the worm wheel."""
    tbm = S.tbm
    cav = GG.worm_case_cavities(L)
    cav.append(GG.Prim('cyl', p1=(A - 1, 0, RZ), p2=(-P['wheel_face'] / 2 - 0.2, 0, RZ), r=g['hex_R'] + g['lid_bore_clear']))   # the wheel's barrel
    cav.append(GG.cyl_s(L, L['s_g0'] - 0.5, L['s_back'] + 0.5, P['collar_d'] / 2 + P['barrel_clear']))   # the worm's plain barrel
    b = S.U(S.prism(F_CASE, A, CASE_X1), S.cyl(ROD, h['wheel_roof_r'], A, CASE_X1),
            S.cyl(ROD, h['roof_r'], A, CASE_X1))             # the roof's hump runs on to the very front (one shape end to end)
    # the worm's top end is covered by a straight shoulder beside the hump (same height, same along the whole
    # case), not by the old cone: nothing overhangs when the halves print, and the top reads as one shape.
    dk = S.prism(shoulder_pts(cav), A, CASE_X1)
    y0, y1, z0, z1 = h['key']
    c0, c1, c2, c3 = h['cheek']
    S.U(b, dk, S.box(-h['key_hw'], h['key_hw'], y0, y1, z0, z1), S.box(-h['cheek_hw'], h['cheek_hw'], c0, c1, c2, c3))
    for pr in cav:
        tbm.booleanOperation(b, T4.brep(pr, tbm), B.DifferenceBooleanType)
    for c in h['case_bolts']:
        S.D(b, S.cyl(c, FIT.M3_R, A - 1, CASE_X1 + 1))
        csink(S, b, c, CASE_X1, 1)
    lid, main = tbm.copy(b), b
    tbm.booleanOperation(lid, S.box(-60, 0, -60, 60, -20, 80), B.IntersectionBooleanType)
    tbm.booleanOperation(main, S.box(0, 60, -60, 60, -20, 80), B.IntersectionBooleanType)
    for c in h['pegs']:
        S.U(main, S.cyl(c, PEG_R, 0.5, -PEG_H))
        S.D(lid, S.cyl(c, PEG_HOLE_R, -PEG_HOLE_H, 0.1))
    for c in PEG_A:                                        # holes in the lid's outer face for the bearing shell's pins
        S.D(lid, S.cyl(c, PEG_HOLE_R, A - 0.1, A + PEG_HOLE_H))
    return {'Case left': lid, 'Case right': main}


def strip_worm_gear(comp, L):
    """The worm is still built with its old 8T helical gear (it drives nothing now): turn it down to the plain barrel."""
    tbm = adsk.fusion.TemporaryBRepManager.get()
    old = comp.bRepBodies.item(0)
    nb = tbm.copy(old)
    sa, sb, br = L['s_g0'] - 0.6, L['s_back'] + 0.02, P['collar_d'] / 2
    tool = tbm.createCylinderOrCone(T4.P3((0, 0, sa)), 1.2, T4.P3((0, 0, sb)), 1.2)
    tbm.booleanOperation(tool, tbm.createCylinderOrCone(T4.P3((0, 0, sa - 1)), br / 10, T4.P3((0, 0, sb + 1)), br / 10), B.DifferenceBooleanType)
    tbm.booleanOperation(nb, tool, B.DifferenceBooleanType)
    T4.add_bodies(comp, [('Worm', nb)])
    old.deleteMe()
    comp.bRepBodies.item(0).name = 'Worm'


def ref_parts(S):
    out = {}
    out['Rod'] = S.box(-98, 40, -2, 2, RZ - 2, RZ + 2)                # a long rod, right through (a short one ends in the carrier)
    f = p1
    gb = S.box(f, f - P['n20_gbx'], MO[0] - 6, MO[0] + 6, MO[1] - 5, MO[1] + 5)
    can = S.cyl(MO, 6, f - P['n20_gbx'], f - P['n20_gbx'] - P['n20_motor'])
    S.tbm.booleanOperation(can, S.box(f, f - 40, MO[0] - 7, MO[0] + 7, MO[1] - 5, MO[1] + 5), B.IntersectionBooleanType)
    tail = f - P['n20_gbx'] - P['n20_motor']
    out['N20'] = S.U(gb, can, S.cyl(MO, 4.5, tail, tail - 1), S.box(tail - 1, tail - 4, MO[0] - 4, MO[0] + 4, MO[1] - 1, MO[1] + 1))
    out['N20 shaft'] = S.cyl(MO, 1.5, f, f + P['n20_shaft_len'])
    for k, pc in enumerate(planet_centers()):
        out['Dowel %d' % (k + 1)] = S.cyl(pc, 1.0, X['disc1'] + g['pin_pocket'], X['disc1'] + g['pin_pocket'] - g['pin_len'])
    for k, c in enumerate(h['case_bolts']):
        out['Case bolt %d' % (k + 1)] = S.cyl(c, 1.5, CASE_X1, CASE_X1 - h['bolt'])
    for k, c in enumerate(h['tray_bolts']):
        out['Tray bolt %d' % (k + 1)] = S.U(S.cyl(c, 1.5, xh, xh + h['tray_bolt']), S.cyl(c, 3.0, xh, xh + 1.5, 1.5))
    ly, lz = h['lid_bolt']
    out['Lid bolt'] = S.U(zcyl(S, XLB, ly, 1.5, 33.2 - h['short'], 33.2), zcyl(S, XLB, ly, 3.0, 33.2, 31.7, 1.5))
    bz = h['board_z']
    out['AS5600 board'] = S.box(bx0, bx1, by0, by1, bz, bz + h['board_t'])
    for hx in HX:
        for hy in HY:
            S.D(out['AS5600 board'], zcyl(S, hx, hy, 1.85, bz - 1, bz + 3))
        if hx == HX[0]:
            out['Sensor bolt'] = S.U(zcyl(S, hx, HY[1], 1.5, 33.2 - h['bolt'], 33.2), zcyl(S, hx, HY[1], 3.0, 33.2, 31.7, 1.5))
    out['AS5600 chip'] = S.box(xg - 2.5, xg + 2.5, MG[0] - 2.0, MG[0] + 2.0, bz + h['board_t'], Z_CHIP)
    out['Magnet'] = zcyl(S, xg, MG[0], 2.0, Z_MAG, Z_MAG + 2.0)
    yb, yf, yj = rj_y()
    jx0 = (RJX[0] + RJX[1]) / 2 + h['rj_jw'] / 2
    jx1 = jx0 - h['rj_jw']
    out['RJ12 board'] = S.box(RJX[0], RJX[1], yb, yf, RJZ0, RJZ0 + h['rj_bd'])
    out['RJ12 jack'] = S.box(jx0, jx1, yf, yj, RJM - h['rj_jl'], RJM)
    out['RJ12 pins'] = S.box(jx0 - 2.9, jx1 + 2.9, yb - h['rj_pin'], yb, RJM - h['rj_jl'] + 1.0, RJM - h['rj_over'] - 1.0)
    out['RJ12 solder row'] = S.box(RJX[0] - 2.6, RJX[1] + 2.6, yb - h['rj_pin'], yb, RJZ0 + 0.6, RJZ0 + 3.0)
    out['RJ12 plug'] = S.box(jx0 - 1.3, jx1 + 1.3, (yf + yj) / 2 - 3.5, (yf + yj) / 2 + 3.5, RJM - 12.0, RJM + 9.5)
    d0, d1 = drv_x()
    y0, z0, z1 = h['drv_y'], h['drv_z'], h['drv_z'] + h['drv_w']
    out['DRV8833'] = S.box(d0, d1, y0, y0 + h['drv_t'], z0, z1)
    out['DRV8833 parts'] = S.box(d0 - 2.0, d1 + 2.0, y0 - 2.0, y0, z0 + 2.0, z1 - 2.0)             # chips toward the room
    out['DRV8833 joints'] = S.box(d0 - 2.0, d1 + 2.0, y0 + h['drv_t'], y0 + h['drv_t'] + 1.5, z0 + 0.2, z1 - 0.2)
    w2, hh, t = P['rail_w'] / 2, P['rail_h'], P['rail_wall']
    out['Rail floor'] = S.box(-100, 40, -w2 - t, w2 + t, -t, 0)
    out['Rail wall room'] = S.box(-100, 40, -w2 - t, -w2, 0, hh)
    out['Rail wall back'] = S.box(-100, 40, w2, w2 + t, 0, hh)
    out['Rail lip room'] = S.box(-100, 40, -w2, -w2 + P['lip_in'], hh - P['lip_h'], hh)
    out['Rail lip back'] = S.box(-100, 40, w2 - P['lip_in'], w2, hh - P['lip_h'], hh)
    return out


# ================================================================== build + checks
MATES = [{'Carrier', 'Dowel %d' % k} for k in range(1, 5)] + [
    {'Worm', 'Worm wheel'}, {'Motor pinion 9T', 'N20 shaft'}, {'Magnet gear', 'Magnet'}, {'RJ12 jack', 'RJ12 plug'},
    {'Tray', 'AS5600 board'},      # press fit: the studs are 0.05 over the board's holes
]
PRINTED = {'Ring cup': 'ring_cup', 'Carrier': 'carrier', 'Planet 1': 'planet', 'Sun + 27T': 'sun_27t',
           'Cluster 20T/9T': 'cluster', 'Motor pinion 9T': 'motor_pinion',
           'Bearing shell': 'bearing_shell', 'Motor shell': 'motor_shell', 'Tray': 'tray',
           'Lid': 'tray_lid', 'Sensor sleeve': 'sensor_sleeve', 'Magnet gear': 'magnet_gear',
           'Worm wheel': 'worm_wheel', 'Case left': 'case_left', 'Case right': 'case_right', 'Worm': 'worm'}
COLORS = {'Ring cup': 'Plastic - Translucent Matte (Blue)', 'Carrier': 'Plastic - Glossy (Green)', 'Sun + 27T': 'Plastic - Glossy (Yellow)',
          'Cluster 20T/9T': 'Plastic - Glossy (Red)',
          'Motor pinion 9T': 'Plastic - Glossy (Yellow)', 'Sensor sleeve': 'Plastic - Glossy (Red)', 'Magnet gear': 'Plastic - Glossy (Yellow)',
          'Lid': 'Plastic - Matte (White)'}


def build(design, export_dir=None):
    root = design.rootComponent
    L = GG.layout()
    S = Shop(root)
    tbm = S.tbm
    parts = make_parts(S)
    parts.update(housing_parts(S))
    parts.update(case_halves(S, L))
    refs = ref_parts(S)
    section = S.prism(F_CASE, -200, 200)                   # the housing's cross-section, for the stays-inside check
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
    strip_worm_gear(worm, L)
    hocc, wheel = build_wheel(root, L)
    T4.place(wocc, L['p0'], L['X'], L['d'])
    T4.place(hocc, L['rod_c'], L['n'], L['X'])
    comps.update({'Worm': worm, 'Worm wheel': wheel})
    T4.color(design, worm, 'Plastic - Glossy (Yellow)')
    T4.color(design, wheel, 'Plastic - Glossy (Green)')

    world = {}                                             # every body in global coordinates
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        for j in range(o.bRepBodies.count):
            nm = o.bRepBodies.item(j).name
            assert nm not in world, 'two bodies named %r: the checks key bodies by name' % nm
            world[nm] = tbm.copy(o.bRepBodies.item(j))
    names = list(world)
    static = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            if {a, b} in MATES or (a.startswith('Planet') and b.startswith('Planet')):
                continue
            ra, rb = a.startswith('Rail'), b.startswith('Rail')
            if ra and rb:
                continue
            if ra or rb:
                other = b if ra else a
                if other.startswith(('Worm', 'Case')):
                    continue
            v, w = _vol(tbm, world[a], world[b])
            if v > OVERLAP_MM3:
                static.append('%s / %s: %.3f mm3 at %s' % (a, b, v, w))
    # stays-inside check: every bought part (motor, boards, bolts, dowels, magnet) lies inside the housing's
    # cross-section, between the housing's two ends. The rod and the RJ12 plug are meant to stick out. (Not checked
    # this way: the printed parts and the planet dowels inside the ring cup. The roof hump over the ring cup and the
    # worm are outside the plain cross-section by design.)
    hx = [world[nm].boundingBox for nm in ('Tray', 'Lid', 'Bearing shell', 'Motor shell', 'Case left', 'Case right')]
    tbm.booleanOperation(section, S.box(min(q.minPoint.x for q in hx) * 10, max(q.maxPoint.x for q in hx) * 10, -60, 60, -20, 80),
                         B.IntersectionBooleanType)
    pokes = KIT.stays_inside(tbm, [(nm, world[nm]) for nm in refs if not nm.startswith(('Rail', 'Rod', 'RJ12 plug', 'Dowel'))], section,
                             tol=OVERLAP_MM3)
    hits, worst = mesh_states(tbm, parts, world['Worm wheel'])
    # sensor gears: turn the pair (1 : 1, crossed axes) through two tooth pitches
    sg_hits = []
    for i in range(17):
        th = 2 * (2 * math.pi / h['sg_z']) * i / 16
        for sgn in (1, -1):
            v = _vol(tbm, _rot(tbm, parts['Sensor sleeve'], th, ROD), _rotz(tbm, parts['Magnet gear'], sgn * th, (xg, MG[0])))[0]
            sg_hits.append((sgn, round(v, 3)))
    sg = {sgn: max(v for s_, v in sg_hits if s_ == sgn) for sgn in (1, -1)}   # only one direction is the real one
    lumps = {nm: world[nm].lumps.count for nm in PRINTED if world[nm].lumps.count != 1}
    ext = {}
    for nm in PRINTED:
        bb = world[nm].boundingBox
        ext[nm] = 'X %.1f..%.1f Y %.1f..%.1f Z %.1f..%.1f' % (bb.minPoint.x * 10, bb.maxPoint.x * 10, bb.minPoint.y * 10,
                                                             bb.maxPoint.y * 10, bb.minPoint.z * 10, bb.maxPoint.z * 10)
    files = []
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        em = design.exportManager
        for nm, fn in PRINTED.items():
            path = os.path.join(export_dir, fn + '.stl')
            opt = em.createSTLExportOptions(comps[nm], path)
            opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
            em.execute(opt)
            files.append(path)
    zs, zr = g['zs'], g['zr']
    ratio = (g['z20'] / g['z9']) * (g['z27'] / g['z9b']) * (1 + zr / zs)
    failures = []
    if static:
        failures.append('static interference: %d pairs' % len(static))
    if hits:
        failures.append('gear mesh interference: %d hits' % len(hits))
    if min(sg.values()) > OVERLAP_MM3:
        failures.append('sensor gears overlap in both directions: %s' % sg)
    if lumps:
        failures.append('more than one lump: %s' % lumps)
    if pokes:
        failures.append('parts poke out of the housing: %d' % len(pokes))
    return dict(
        ok=not failures, failures=failures,
        ratio=round(ratio, 2),
        axes={'P (Y, Z)': [round(v, 2) for v in CL], 'motor (Y, Z)': [round(v, 2) for v in MO], 'magnet gear (Y, Z)': [round(v, 2) for v in MG]},
        stations={k: round(v, 2) for k, v in list(X.items()) + list(XS.items())},
        sensor={'chip top Z': Z_CHIP, 'magnet face Z': Z_MAG, 'gear Z': (ZG0, ZG1),  'gear tip r': round(SG['ra'], 2)},
        static_interference=static, pokes_out_of_housing=pokes, mesh_interference=hits, mesh_worst_mm3=round(worst, 4),
        sensor_gear_worst_overlap_mm3_by_direction=sg,
        more_than_one_lump=lumps, extents=ext, exported=[os.path.basename(f) for f in files])
