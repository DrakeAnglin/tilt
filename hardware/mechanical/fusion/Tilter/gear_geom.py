"""Tilter's pure geometry: dimensions, vectors, gear math (involute, helical, worm, hobbed worm wheel), the worm's
layout, the worm case's pockets and the gear train. No Fusion import: test_geometry.py runs it on its own.

Global coordinates (mm): X along the rod (0 = tilter mid-plane, +X toward the tilt drums), Y across the rail
(-Y = room side), Z up from the rail's inner floor. s = distance along the worm axis from its thread center,
positive toward the wand.
"""

import importlib.util
import math
import os

_spec = importlib.util.spec_from_file_location('fits', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fits.py'))
FIT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FIT)

# ------------------------------------------------------------------ parameters (mm / deg)
P = dict(
    rod_z=FIT.ROD_Z,
    rail_w=FIT.RAIL_W, rail_h=FIT.RAIL_H, rail_wall=FIT.RAIL_WALL, lip_in=FIT.LIP_IN, lip_h=FIT.LIP_H,
    pressure=25.0,            # all gears: 25° prints cleaner than 20° (less flank overhang on the vertical worm)
    backlash=0.15,
    # worm + worm wheel: same ratio / size class as the factory pair (16:1, m 0.88)
    module_worm=0.88, z_wheel=16, worm_d=9.6, worm_angle=60.0, cd_extra=0.2,
    worm_backlash=0.2,        # axial, cut into the wheel teeth
    worm_root_clear=0.25,     # x module: worm tip to wheel root
    wheel_face=7.5, barrel_r=6.25, wheel_slices=7, wheel_pts=16,
    # worm bearing + thrust: one long Ø8.2 barrel (the collar's size) carries it radially; axial load goes only onto
    # two small steps: up onto the barrel's top step, down onto the collar's step at the wand exit. Every other end
    # face runs >= 1 mm clear, so print tolerance can't make it touch
    journal_r=3.0,            # short neck between the threads and the barrel
    thrust_s=7.6,             # s of the barrel's top step (the up-thrust face)
    thread_clear=0.6,         # worm thread OD to its pocket
    thread_end_clear=1.0, worm_thrust_clear=0.1,
    # a Ø2 steel dowel pressed into the case runs in a hole in the worm's thread end, so the worm can't tip
    top_pin_d=2.0, top_pin_len=6.0, top_pin_case=2.0, top_pin_hole_clear=0.1,
    barrel_clear=0.25, collar_clear=0.3, neck_clear=0.5,
    # the worm's old 8T 45° helical (Tilter.py turns it down to a plain barrel) and the 7T pinion it was paired with:
    # the pinion's reach still shapes the worm's print-chamfer floor (build_worm)
    mn=1.0, helix=45.0, addendum=0.85, dedendum=1.25, hx_cd_extra=0.20,
    z_worm_gear=8, z_pinion=7, worm_gear_face=6.5,
    worm_gear_s0=15.0,        # s of the worm gear's thread-side face; its other face = collar start (21.5)
    print_chamfer=True,       # 45° bevels on the gear's tooth ends (the worm prints standing on its top pin)
    n20_shaft_len=10.0,
    # wand shaft
    collar_d=8.2, collar_len=2.5, body_d=6.0, body_end_s=34.5, loop_s=43.97,   # shaft ends early: long teardrop flanks
    loop_r_out=5.4, loop_r_in=2.7, loop_t=4.0, loop_round=1.0, blend_len=2.5,   # round shaft -> flat loop blend
    # N20 (no encoder)
    n20_gbx=9.0, n20_motor=15.0, n20_shaft_d=3.0, n20_flat=2.5, n20_screw_spacing=9.0,
    slab_half=7.3,            # the worm case's lid face (its skin lies on the ring cup's floor)
    main_half=9.3,            # the main half's back face
)


# ------------------------------------------------------------------ vector helpers (mm)
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a): return math.sqrt(dot(a, a))
def unit(a): return mul(a, 1.0 / norm(a))



# ------------------------------------------------------------------ gear math
def inv(x): return math.tan(x) - x


def involute_teeth(z, rp, rb, ra, rf, at, half, rscale=1.0, ascale=1.0, rot=0.0, n_flank=8):
    """Closed outline of z involute teeth. half = tooth half-angle at the pitch circle. rscale / ascale map a
    virtual gear onto a real one (bevel back cone: radius x cos δ, angle / cos δ)."""
    def theta(r):
        return half + inv(at) - (inv(math.acos(rb / r)) if r > rb else 0.0)
    r0 = max(rf, rb)
    radii = [r0 + (ra - r0) * i / (n_flank - 1) for i in range(n_flank)]
    pitch = 2 * math.pi / z
    pts = []
    for k in range(z):
        c = k * pitch + rot
        tooth = []
        if rf < rb:
            tooth.append((rf, c - theta(rb) * ascale))
        tooth += [(r, c - theta(r) * ascale) for r in radii]
        a0, a1 = c - theta(ra) * ascale, c + theta(ra) * ascale
        tooth += [(ra, a0 + (a1 - a0) * i / 3) for i in (1, 2)]
        tooth += [(r, c + theta(r) * ascale) for r in reversed(radii)]
        if rf < rb:
            tooth.append((rf, c + theta(rb) * ascale))
        b0 = tooth[-1][1]
        b1 = c + pitch - theta(rb if rf < rb else r0) * ascale
        tooth += [(rf, b0 + (b1 - b0) * i / 3) for i in (1, 2)]
        pts += tooth
    return [(r * rscale * math.cos(t), r * rscale * math.sin(t)) for r, t in pts]


def spur(z, m):
    at = math.radians(P['pressure'])
    rp = z * m / 2.0
    return dict(z=z, mt=m, at=at, rp=rp, rb=rp * math.cos(at), ra=rp + 0.8 * m, rf=rp - 1.25 * m, beta=0.0)


def gear_profile(g, backlash=None):
    half = math.pi / (2 * g['z']) - ((P['backlash'] if backlash is None else backlash) / 2.0) / g['rp']
    return involute_teeth(g['z'], g['rp'], g['rb'], g['ra'], g['rf'], g['at'], half)


def helical(z):
    b = math.radians(P['helix'])
    mt = P['mn'] / math.cos(b)
    at = math.atan(math.tan(math.radians(P['pressure'])) / math.cos(b))
    rp = z * mt / 2.0
    return dict(z=z, mt=mt, at=at, rp=rp, rb=rp * math.cos(at),
                ra=rp + P['addendum'] * P['mn'], rf=rp - P['dedendum'] * P['mn'], beta=b)


def worm_dims():
    m = P['module_worm']
    rp = P['worm_d'] / 2.0
    return dict(m=m, p=math.pi * m, rp=rp, ra=rp + m, rf=rp - 1.2 * m, at=math.radians(P['pressure']),
                lead_deg=math.degrees(math.atan(m / P['worm_d'])))


def worm_radius(th, z, extra=0.0, tip=0.0):
    """Single-start right-hand worm: outer radius at angle th of the transverse section at axial position z.
    extra thickens the thread (axially, both flanks); tip raises the outside diameter."""
    w = worm_dims()
    p = w['p']
    e = (p * (th - 2 * math.pi * z / p) / (2 * math.pi)) % p
    e = min(e, p - e)
    return min(max(w['rp'] + (p / 4 + extra / 2 - e) / math.tan(w['at']), w['rf']), w['ra'] + tip)


def wheel_dims():
    m, z = P['module_worm'], P['z_wheel']
    w = worm_dims()
    R = z * m / 2.0
    cd = R + w['rp'] + P['cd_extra']
    return dict(m=m, z=z, R=R, ra=R + m, rf=cd - w['ra'] - P['worm_root_clear'] * m, cd=cd)


def wheel_section(zz):
    """Wheel outline in its plane at axial position zz (wheel-local: x toward the worm, y along the worm axis toward
    the wand, z = wheel axis): the worm (thickened by the backlash, tip raised by the root clearance) is moved
    through its mesh with the wheel and every point it ever reaches is removed. Radius per angle, one pitch, then
    patterned (the wheel is 16-fold symmetric)."""
    w, wh = worm_dims(), wheel_dims()
    zw, cd = wh['z'], wh['cd']
    pitch = 2 * math.pi / zw
    tip = P['worm_root_clear'] * w['m']
    reach = w['ra'] + tip

    def hit(x, y, phi):
        wx, wy, wz = zz, x - cd, y               # worm-local: x = wheel axis, y = toward the worm, z = worm axis
        r = math.hypot(wx, wy)
        if r > reach:
            return False
        return r <= worm_radius(math.atan2(wy, wx) - phi, wz, P['worm_backlash'], tip)

    n_th, n_phi = P['wheel_pts'], 240

    def blocked(r, th):
        for k in range(n_phi):
            psi = -1.6 * pitch + 3.2 * pitch * k / n_phi            # wheel turns psi, worm turns -16 psi
            a = th + psi
            if hit(r * math.cos(a), r * math.sin(a), -zw * psi):
                return True
        return False

    radii = []
    for i in range(n_th):
        th = pitch * i / n_th
        r = wh['rf'] - 0.3
        while r < wh['ra'] and not blocked(r, th):
            r += 0.05
        if r < wh['ra']:                               # refine the edge (coarse steps make the loft ripple)
            lo, hi = r - 0.05, r
            for _ in range(7):
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if blocked(mid, th) else (mid, hi)
            r = lo
        radii.append(min(r, wh['ra']))
    out = []
    for k in range(zw):
        for i, r in enumerate(radii):
            a = k * pitch + pitch * i / n_th
            out.append((r * math.cos(a), r * math.sin(a)))
    return out


# ------------------------------------------------------------------ layout
def layout():
    """Where the worm and the worm wheel sit: axes, the worm's stations (s) and both gears' sizes."""
    a = math.radians(P['worm_angle'])
    X = (1.0, 0.0, 0.0)
    d = (0.0, -math.cos(a), -math.sin(a))          # worm axis, toward the wand
    n = (0.0, -math.sin(a), math.cos(a))           # rod axis -> worm axis
    rod_c = (0.0, 0.0, P['rod_z'])
    w, wh = worm_dims(), wheel_dims()
    p0 = add(rod_c, mul(n, wh['cd']))
    S = lambda s: add(p0, mul(d, s))
    # worm thread half-length: covers the wheel's tips
    half = math.sqrt(max(wh['ra'] ** 2 - (wh['cd'] - w['ra']) ** 2, 0)) + 0.5 * w['m']
    ga, gp = helical(P['z_worm_gear']), helical(P['z_pinion'])
    s_g0 = P['worm_gear_s0']
    s_back = s_g0 + P['worm_gear_face']             # gear's lower face = wand collar start
    cd = ga['rp'] + gp['rp'] + P['hx_cd_extra']     # worm gear to the old pinion
    return dict(X=X, d=d, n=n, rod_c=rod_c, p0=p0, S=S, half=half, ga=ga, gp=gp, cd=cd,
                s_g0=s_g0, s_back=s_back, worm=w, wheel=wh)


# ------------------------------------------------------------------ simple solids
class Prim:
    """Finite cylinder (p1, p2, r, optional r2) or oriented box (c, u, w, L, W, H). tilt_base.brep() makes the solid."""

    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)

    def contains(self, p, grow=0.0):
        if self.kind == 'cyl':
            ax = sub(self.p2, self.p1)
            Lx = norm(ax)
            ax = mul(ax, 1 / Lx)
            v = sub(p, self.p1)
            t = dot(v, ax)
            rr = self.r + (getattr(self, 'r2', self.r) - self.r) * min(max(t / Lx, 0.0), 1.0)
            return -grow <= t <= Lx + grow and norm(sub(v, mul(ax, t))) <= rr + grow
        v = sub(p, self.c)
        h = cross(self.u, self.w)
        return (abs(dot(v, self.u)) <= self.L / 2 + grow and abs(dot(v, self.w)) <= self.W / 2 + grow
                and abs(dot(v, h)) <= self.H / 2 + grow)


def box(c, L, W, H, u=(1, 0, 0), w=(0, 1, 0)):
    return Prim('box', c=c, u=u, w=w, L=L, W=W, H=H)


def box_minmax(x0, x1, y0, y1, z0, z1):
    return box(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), x1 - x0, y1 - y0, z1 - z0)


def cyl_s(L, s0, s1, r):
    return Prim('cyl', p1=L['S'](s0), p2=L['S'](s1), r=r)


def slab_x(L):
    """X of the worm case's lid face and of the main half's back face."""
    return -P['slab_half'], P['main_half']


def worm_case_cavities(L):
    """The pockets the worm case needs round the worm wheel and the worm, each with a .label."""
    rc = L['rod_c']
    wd, wh = L['worm'], L['wheel']
    half = L['half']
    thr, free = P['worm_thrust_clear'], P['thread_end_clear']
    br = P['collar_d'] / 2
    x0, x1 = slab_x(L)
    collar_end = L['s_back'] + P['collar_len']
    fw = P['wheel_face'] / 2 + 0.4
    named = [
        ('wheel teeth', Prim('cyl', p1=add(rc, (-fw, 0, 0)), p2=add(rc, (fw, 0, 0)), r=wh['ra'] + 0.45)),
        ('barrel bore', Prim('cyl', p1=add(rc, (x0 - 1, 0, 0)), p2=add(rc, (x1 + 1, 0, 0)), r=P['barrel_r'] + 0.15)),
        # worm: thrust up on the thread's top face, the thrust ring both ways (wand pull: collar -> case shoulder)
        ('worm threads', cyl_s(L, -half - free, half + free, wd['ra'] + P['thread_clear'])),   # threads run free
        ('worm top pin', cyl_s(L, -half - free + 0.01, -half - free - P['top_pin_case'], P['top_pin_d'] / 2)),  # press
        ('worm neck', cyl_s(L, half + free - 0.01, P['thrust_s'] - thr, P['journal_r'] + P['neck_clear'])),
        ('worm barrel', cyl_s(L, P['thrust_s'] - thr - 0.01, L['s_g0'], br + P['barrel_clear'])),   # up-thrust step at top
        ('wand collar', cyl_s(L, L['s_back'], collar_end + thr, br + P['collar_clear'])),   # down-thrust step
        ('wand exit', cyl_s(L, collar_end + thr - 0.01, collar_end + 40, P['body_d'] / 2 + P['collar_clear'])),
    ]
    for nm, pr in named:
        pr.label = nm
    return [pr for _, pr in named]


# ------------------------------------------------------------------ gear train (motor -> planetary -> ring cup)
RZ = P['rod_z']
A = -P['slab_half']                       # lid outer face
G = dict(
    m=0.75, zs=16, zp=8, zr=32, n_planets=4, shift=0.1,    # planets +0.1, sun -0.1, ring +0.1 (8T: no undercut)
    m3=0.8,                                                # the motor pair (9T -> 20T): module 0.8
    m2=1.0, z27=27, z9b=9, z20=20, z9=9,
    ring_ro=14.5, floor_t=2.8, disc_t=3.0, disc_r=11.0, planet_face=4.3, gap=0.3,
    hex_R=7.2, hex_clear=0.15, lid_bore_clear=0.15,
    hub_r=4.2, hub_end_x=7.8,          # the hub runs the whole wheel (a short rod is still fully gripped)
    wheel_bore_hub=4.4,
    pin_d=2.0, pin_len=5.9, pin_hole_clear=0.1, pin_pocket=3.0, planet_bore_clear=0.1,   # dowel pockets Ø2.2, as the worm's top-pin hole (#183)
    sun_bore=4.1, journal_clear=0.15,                    # the sensor sleeve's nose (r 3.9) runs through it
    wall_t=0.8, face_a=3.5, face_d=3.2, plate_t=1.2,      # wall and plate are just skins that keep gears from rubbing
    nose_r=3.9, nose_clear=0.15,                           # sensor sleeve's nose; the motor plate's bore is its front bearing
    lug_w=3.0, lug_len=2.4, lug_clear=0.05,                # four lugs on the nose, in slots in the carrier's back
    axle_bore=1.65,
    cluster_y=-13.4, motor_z=6.2,
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
X['d0'] = X['wall1'] - g['gap']               # 20T + motor pinion: at the bearing wall, on the tip of the motor's shaft
X['d1'] = X['d0'] - g['face_d']
X['a0'] = X['d1'] - g['gap']                  # 27T + the cluster's 9T: at the motor plate (the N20's screw heads stand in this zone, clear of both)
X['a1'] = X['a0'] - g['face_a']
X['plate0'] = X['a1'] - g['gap']
X['plate1'] = X['plate0'] - g['plate_t']


def gear(z, m, x=0.0):
    d = spur(z, m)
    d['x'] = x
    d['ra'] = d['rp'] + (0.8 + x) * m
    d['rf'] = d['rp'] - (1.25 - x) * m
    return d


GS, GP, GR = gear(g['zs'], g['m'], -g['shift']), gear(g['zp'], g['m'], g['shift']), gear(g['zr'], g['m'], g['shift'])
G27, G9B = gear(g['z27'], g['m2']), gear(g['z9b'], g['m2'])
G20, G9 = gear(g['z20'], g['m3']), gear(g['z9'], g['m3'])
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
        return involute_teeth(d['z'], d['rp'], d['rb'], d['root'], d['tip'], d['at'], half + bl / 2 / d['rp'], rot=rot)
    return involute_teeth(d['z'], d['rp'], d['rb'], d['ra'], d['rf'], d['at'], half - bl / 2 / d['rp'], rot=rot)


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
                g20=psi2, g9=psi2 + math.pi + math.pi / g['z9'])


def ngon(c, R, n, a0=0.0):
    return [(c[0] + R * math.cos(a0 + 2 * math.pi * k / n), c[1] + R * math.sin(a0 + 2 * math.pi * k / n)) for k in range(n)]


def hex_a0():
    """The wheel's hex has a corner along the wheel-local x axis (= layout n)."""
    n = layout()['n']
    return math.atan2(n[2], n[1])


def planet_centers():
    return [(ROD[0] + R_ORBIT * math.cos(phi), ROD[1] + R_ORBIT * math.sin(phi)) for phi, _ in phases()['planets']]


