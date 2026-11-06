"""ControllerV1: dev-board mock-up and headrail case for one blind controller (ESP32-C6, 3 tilters).

Every bought part is mocked at its listed / measured size so the dev board and the case can be checked for fit
before anything is cut or printed. The case sits on the headrail floor UNDER the tilt rod, between the rail walls,
and drops in through the rail's top opening (46.5 mm between the lips).

  RAIL REF       headrail section (55.5 x 36.5 inside, lips 4.5 in), 4 mm square tilt rod at Z 24 (reference only)
  CASE TRAY      floor + walls; battery saddles, perfboard ledge + posts, breakout pegs, charger ribs; RJ12 / USB-C
                 openings in the end walls, solar pigtail hole, snap windows
  CASE LID       flat lid with a groove along the middle (the rod sweeps down to Z 21.2), snap skirts, hold-down fingers
  PERFBOARD      24 x 82 strip cut from the 9 x 15 cm board, on posts at Z 9: 2 x DRV8833, ESP32-C6 SuperMini,
                 electrolytic, passives strip on top; the MCP73871 charger underneath
  BREAKOUTS      3 x RJ12 6P6C (2 at end A, 1 at end B) and the USB-C breakout (end B) on the case floor
  BATTERY        protected 18650 (18.6 x 69) on the room side
  PLUGS          RJ12 plugs + white cord stubs, USB-C plug, solar pigtail (to check the openings)

Coordinates (mm): X along the rail (case from 0 to its length), Y across (-Y = room side), Z up from the rail floor.
"""

import math

import adsk.core
import adsk.fusion

PREFIX = 'CT '

P = dict(
    # headrail (same numbers as TiltPartsV4)
    rail_w=55.5, rail_h=36.5, rail_wall=2.0, lip_in=4.5, lip_h=3.0, rod_z=24.0, rod=4.0,
    # case
    half_w=23.0,          # outer half width: 46 fits the 46.5 opening between the lips
    wall=1.2, floor=1.2, lid=1.2, top=23.0,
    groove_hw=4.5,        # |Y| < this stays below groove_top (rod sweep bottom = 24 - 2.83 = 21.17)
    groove_wall=1.2, groove_top=20.2,
    # RJ12 6P6C breakout (risingsaplings, measured from the listing photo against the 2.54 pitch)
    rj_bw=20.3, rj_bd=13.1, rj_bt=1.6, rj_jw=12.6, rj_jh=11.7, rj_jd=16.3, rj_over=12.9,
    rj_hole_side=2.6, rj_hole_back=3.8, rj_hole_d=3.0, rj_mouth_w=9.9, rj_mouth_h=8.6, rj_mouth_z=5.4,
    standoff=3.0,         # breakout boards' underside above the case floor (through-hole pins below)
    rj_y=10.75,           # |Y| of the RJ12 centers
    # USB-C 16-pin breakout (Teansic; size estimated, check on arrival)
    usb_bw=18.0, usb_bd=15.0, usb_y=-11.5, rec_w=8.94, rec_h=3.26, rec_d=7.35, rec_over=0.5,
    # perfboard strip on posts
    pb_x0=18.0, pb_len=82.0, pb_y0=-2.5, pb_w=24.0, pb_z=9.0, pb_t=1.6, spacer=2.5,
    # modules
    esp_l=22.5, esp_w=18.0, esp_t=1.0, esp_row=15.24,     # row spacing assumed 0.6" (check on arrival)
    drv_l=18.5, drv_w=16.0, drv_t=1.6,
    chg_l=20.0, chg_w=19.0, chg_t=1.6,                       # Comimark MCP73871 (pads, no USB / DC jack)
    cap_d=8.0, cap_l=13.0,                                   # the electrolytic that ships with the charger
    # battery
    bat_d=18.6, bat_l=69.0, bat_x0=28.5, bat_lead=4.0,
)

tbm = None


# ------------------------------------------------------------------ primitives (mm in, cm to Fusion)
def P3(x, y, z):
    return adsk.core.Point3D.create(x / 10.0, y / 10.0, z / 10.0)


def bx(x0, x1, y0, y1, z0, z1):
    obb = adsk.core.OrientedBoundingBox3D.create(
        P3((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
        adsk.core.Vector3D.create(1, 0, 0), adsk.core.Vector3D.create(0, 1, 0),
        abs(x1 - x0) / 10.0, abs(y1 - y0) / 10.0, abs(z1 - z0) / 10.0)
    return tbm.createBox(obb)


def obox(c, u, w, L, W, H):
    obb = adsk.core.OrientedBoundingBox3D.create(P3(*c), adsk.core.Vector3D.create(*u),
                                                 adsk.core.Vector3D.create(*w), L / 10.0, W / 10.0, H / 10.0)
    return tbm.createBox(obb)


def cyl(p1, p2, r):
    return tbm.createCylinderOrCone(P3(*p1), r / 10.0, P3(*p2), r / 10.0)


def uni(*bodies):
    a = bodies[0]
    for b in bodies[1:]:
        tbm.booleanOperation(a, b, adsk.fusion.BooleanTypes.UnionBooleanType)
    return a


def cut(a, *tools):
    for t in tools:
        tbm.booleanOperation(a, t, adsk.fusion.BooleanTypes.DifferenceBooleanType)
    return a


# ------------------------------------------------------------------ layout
def layout():
    p = P
    e_pb = p['pb_x0'] + p['pb_len'] + 0.5 + p['rj_jd']                    # perfboard side: board, then RJ12 #3
    e_bat = p['bat_x0'] + p['bat_l'] + p['bat_lead'] + p['usb_bd'] + 0.5   # battery side: cell, lead, USB-C board
    e = max(e_pb, e_bat)                                                    # inner face of end wall B
    Lo = e + p['wall']
    bz0 = p['floor'] + p['standoff']                                        # breakout board underside
    bz1 = bz0 + p['rj_bt']
    pb_top = p['pb_z'] + p['pb_t']
    mod_z = pb_top + p['spacer']                                            # module PCB underside on the perfboard
    bat_r = p['bat_d'] / 2
    return dict(e=e, Lo=Lo, bz0=bz0, bz1=bz1, pb_top=pb_top, mod_z=mod_z,
                bat_c=(p['bat_x0'] + p['bat_l'] / 2, -(p['half_w'] - p['wall']) + 0.3 + bat_r, p['floor'] + 0.3 + bat_r),
                drv1=(19.0, 3.5), drv2=(38.5, 3.5), esp=(59.0, 2.0), chg=(70.0, 0.5),
                cap=(84.0, 15.5), rj=[('A', -p['rj_y']), ('A', p['rj_y']), ('B', p['rj_y'])])


def rj_geom(L, end, yc):
    """x ranges of the RJ12 jack and its breakout board; the jack face sits on the end wall's inner face."""
    p = P
    w = p['wall']
    if end == 'A':
        jx = (w, w + p['rj_jd'])
        bx0 = w + p['rj_over']
        bxr = (bx0, bx0 + p['rj_bd'])
        hole_x = bxr[1] - p['rj_hole_back']
        sgn = 1
    else:
        e = L['e']
        jx = (e - p['rj_jd'], e)
        bx1 = e - p['rj_over']
        bxr = (bx1 - p['rj_bd'], bx1)
        hole_x = bxr[0] + p['rj_hole_back']
        sgn = -1
    hy = p['rj_bw'] / 2 - p['rj_hole_side']
    return dict(jx=jx, bxr=bxr, holes=[(hole_x, yc - hy), (hole_x, yc + hy)], sgn=sgn)


def jack_z(L):
    return L['bz1'], L['bz1'] + P['rj_jh']


def mouth_z(L):
    z0 = L['bz1'] + P['rj_mouth_z'] - P['rj_mouth_h'] / 2
    return z0, z0 + P['rj_mouth_h']


def usb_geom(L):
    p = P
    e = L['e']
    rx = (e - p['rec_d'], e)
    bxr = (e - p['usb_bd'], e - p['rec_over'])
    rz = (L['bz1'], L['bz1'] + p['rec_h'])
    return dict(rx=rx, bxr=bxr, rz=rz, yc=p['usb_y'])


# ------------------------------------------------------------------ parts
def rail_ref(L):
    p = P
    hw, t = p['rail_w'] / 2, p['rail_wall']
    x0, x1 = -25.0, L['Lo'] + 25.0
    bodies = [('Rail floor', bx(x0, x1, -hw - t, hw + t, -t, 0)),
              ('Rail wall room', bx(x0, x1, -hw - t, -hw, -t, p['rail_h'])),
              ('Rail wall back', bx(x0, x1, hw, hw + t, -t, p['rail_h'])),
              ('Rail lip room', bx(x0, x1, -hw, -hw + p['lip_in'], p['rail_h'] - p['lip_h'], p['rail_h'])),
              ('Rail lip back', bx(x0, x1, hw - p['lip_in'], hw, p['rail_h'] - p['lip_h'], p['rail_h'])),
              ('Tilt rod', obox(((x0 + x1) / 2, 0, p['rod_z']), (1, 0, 0), (0, math.cos(math.pi / 4), math.sin(math.pi / 4)),
                                x1 - x0, p['rod'], p['rod']))]
    return bodies


def rod_sweep(L):
    p = P
    return cyl((-25.0, 0, p['rod_z']), (L['Lo'] + 25.0, 0, p['rod_z']), p['rod'] * math.sqrt(2) / 2)


def case_tray(L):
    p = P
    Lo, e, hw, w, fl = L['Lo'], L['e'], p['half_w'], p['wall'], p['floor']
    zl = p['top'] - p['lid']                       # tray rim = lid underside
    iw = hw - w
    tray = cut(bx(0, Lo, -hw, hw, 0, zl), bx(w, e, -iw, iw, fl, 40))
    # the lid's groove floor closes the end walls in the middle
    tray = cut(tray, bx(-1, Lo + 1, -(p['groove_hw'] + p['groove_wall']), p['groove_hw'] + p['groove_wall'],
                        p['groove_top'] - p['lid'], 40))
    jz = jack_z(L)
    for end, yc in L['rj']:
        g = rj_geom(L, end, yc)
        xw = (-1, w + 1) if end == 'A' else (e - 1, Lo + 1)
        tray = cut(tray, bx(xw[0], xw[1], yc - p['rj_jw'] / 2 - 0.2, yc + p['rj_jw'] / 2 + 0.2, jz[0] - 0.2, jz[1] + 0.2))
        for hx, hy in g['holes']:                  # collar under the board + peg through its hole
            tray = uni(tray, cyl((hx, hy, fl - 0.1), (hx, hy, L['bz0']), 2.6),
                       cyl((hx, hy, L['bz0'] - 0.1), (hx, hy, L['bz1'] + 1.5), p['rj_hole_d'] / 2 - 0.15))
    u = usb_geom(L)
    zc = (u['rz'][0] + u['rz'][1]) / 2
    tray = cut(tray, bx(e - 1, Lo + 1, u['yc'] - 4.8, u['yc'] + 4.8, zc - 2.0, zc + 2.0))
    for bxx in (u['bxr'][0] + 2.0, u['bxr'][1] - 2.0):            # USB board rests on two rails
        tray = uni(tray, bx(bxx - 1.0, bxx + 1.0, u['yc'] - p['usb_bw'] / 2, u['yc'] + p['usb_bw'] / 2, fl - 0.1, L['bz0']))
    tray = cut(tray, cyl((e - 1, -17.0, 15.0), (Lo + 1, -17.0, 15.0), 1.75))        # solar pigtail
    # battery saddles
    bc = L['bat_c']
    br = p['bat_d'] / 2 + 0.2
    for sx in (p['bat_x0'] + 6, p['bat_x0'] + p['bat_l'] - 10):
        s = cut(bx(sx, sx + 4, -iw, -3.4, fl - 0.1, bc[2] - 3.0),
                cyl((sx - 1, bc[1], bc[2]), (sx + 5, bc[1], bc[2]), br))
        tray = uni(tray, s)
    # perfboard: ledge on the back wall + posts on the battery side edge
    pz = p['pb_z']
    tray = uni(tray, bx(28.0, 90.0, iw - 1.5, iw + 0.1, fl - 0.1, pz))
    for px in (28.5, 60.0, p['pb_x0'] + p['pb_len'] - 2.0):
        tray = uni(tray, bx(px, px + 2.0, p['pb_y0'] + 0.5, p['pb_y0'] + 3.0, fl - 0.1, pz))
    # charger ribs (it sits under the perfboard)
    cx, cy = L['chg']
    for rx in (cx + 1.0, cx + p['chg_l'] - 3.0):
        tray = uni(tray, bx(rx, rx + 2.0, cy, cy + p['chg_w'], fl - 0.1, fl + 1.0))
    # snap windows
    for sx in (Lo * 0.25, Lo * 0.75):
        for s in (-1, 1):
            tray = cut(tray, bx(sx - 4.0, sx + 4.0, s * (iw - 0.5), s * (hw + 1), zl - 2.2, zl - 0.6))
    return tray


def case_lid(L):
    p = P
    Lo, hw, w = L['Lo'], p['half_w'], p['wall']
    zl = p['top'] - p['lid']
    iw = hw - w
    gw = p['groove_hw'] + p['groove_wall']
    lid = bx(0, Lo, -hw, hw, zl, p['top'])
    # snap skirts along both long walls, with bumps into the tray's windows
    for s in (-1, 1):
        y0, y1 = sorted((s * (iw - 0.2), s * (iw - 1.4)))
        lid = uni(lid, bx(6.0, Lo - 6.0, y0, y1, zl - 3.5, zl + 0.1))
        for sx in (Lo * 0.25, Lo * 0.75):
            b0, b1 = sorted((s * (iw - 0.2), s * (iw + 0.3)))
            lid = uni(lid, bx(sx - 3.5, sx + 3.5, b0, b1, zl - 2.0, zl - 0.8))
    # hold-down fingers: RJ12 jack tops, battery, perfboard edge (tabs on the back skirt)
    jz = jack_z(L)
    for end, yc in L['rj']:
        g = rj_geom(L, end, yc)
        fx = (g['jx'][0] + g['jx'][1]) / 2
        lid = uni(lid, bx(fx - 2, fx + 2, yc - 3, yc + 3, jz[1] + 0.1, zl + 0.1))
    bc = L['bat_c']
    btop = bc[2] + p['bat_d'] / 2
    for fx in (p['bat_x0'] + 18, p['bat_x0'] + p['bat_l'] - 22):
        lid = uni(lid, bx(fx, fx + 4, bc[1] - 2, bc[1] + 2, btop + 0.1, zl + 0.1))
    for fx in (30.0, 70.0, 92.0):
        lid = uni(lid, bx(fx - 2, fx + 2, iw - 1.4, iw - 0.2, L['pb_top'] + 0.1, zl + 0.1))
    # groove for the tilt rod
    lid = cut(lid, bx(-1, Lo + 1, -gw, gw, p['groove_top'] - p['lid'], 40))
    lid = uni(lid, bx(0, Lo, -gw, gw, p['groove_top'] - p['lid'], p['groove_top']))
    for s in (-1, 1):
        y0, y1 = sorted((s * p['groove_hw'], s * gw))
        lid = uni(lid, bx(0, Lo, y0, y1, p['groove_top'] - p['lid'], p['top']))
    return lid


def pin(x, y, z0, z1, s=0.64):
    return bx(x - s / 2, x + s / 2, y - s / 2, y + s / 2, z0, z1)


def header_row(xs, y, L):
    """Straight male header through the perfboard: plastic spacer on top, pins from under the board to the module."""
    p = P
    z_sp0, z_sp1 = L['pb_top'], L['mod_z']
    plastic = bx(min(xs) - 1.27, max(xs) + 1.27, y - 1.27, y + 1.27, z_sp0, z_sp1)
    pins = [pin(x, y, p['pb_z'] - 1.5, L['mod_z'] + 1.6 + 0.5) for x in xs]
    return plastic, pins


def esp32(L):
    p = P
    x0, y0 = L['esp']
    z0 = L['mod_z']
    yc = y0 + p['esp_w'] / 2
    pcb = bx(x0, x0 + p['esp_l'], y0, y0 + p['esp_w'], z0, z0 + p['esp_t'])
    chip = bx(x0 + 5, x0 + 10, yc - 2.5, yc + 2.5, z0 + p['esp_t'], z0 + p['esp_t'] + 0.9)
    ant = bx(x0 + 1.0, x0 + 4.0, yc - 1.5, yc + 1.5, z0 + p['esp_t'], z0 + p['esp_t'] + 1.2)
    usb = bx(x0 + p['esp_l'] - 7.35 + 0.8, x0 + p['esp_l'] + 0.8, yc - 4.47, yc + 4.47, z0 + p['esp_t'], z0 + p['esp_t'] + 3.26)
    xs = [x0 + 1.27 + 2.54 * i for i in range(9)]
    plastics, pins = [], []
    for y in (yc - p['esp_row'] / 2, yc + p['esp_row'] / 2):
        pl, ps = header_row(xs, y, L)
        plastics.append(pl)
        pins += ps
    return [('ESP32-C6 PCB', pcb), ('ESP32-C6 chip', uni(chip, ant)), ('ESP32-C6 USB-C', usb),
            ('ESP32-C6 headers', uni(*plastics)), ('ESP32-C6 pins', uni(*pins))]


def drv8833(L, at, n):
    p = P
    x0, y0 = at
    z0 = L['mod_z']
    yc = y0 + p['drv_w'] / 2
    pcb = bx(x0, x0 + p['drv_l'], y0, y0 + p['drv_w'], z0, z0 + p['drv_t'])
    chip = bx(x0 + p['drv_l'] / 2 - 2.5, x0 + p['drv_l'] / 2 + 2.5, yc - 2, yc + 2, z0 + p['drv_t'], z0 + p['drv_t'] + 1.0)
    plastics, pins = [], []
    for xr in (x0 + 1.27, x0 + p['drv_l'] - 1.27):      # 6-pin rows on the 16 mm edges
        ys = [yc - 6.35 + 2.54 * i for i in range(6)]
        pl = bx(xr - 1.27, xr + 1.27, min(ys) - 1.27, max(ys) + 1.27, L['pb_top'], L['mod_z'])
        plastics.append(pl)
        pins += [pin(xr, y, p['pb_z'] - 1.5, z0 + p['drv_t'] + 0.5) for y in ys]
    nm = 'DRV8833 %d' % n
    return [(nm + ' PCB', pcb), (nm + ' chip', chip), (nm + ' headers', uni(*plastics)), (nm + ' pins', uni(*pins))]


def charger(L):
    p = P
    x0, y0 = L['chg']
    z0 = p['floor'] + 1.0
    pcb = bx(x0, x0 + p['chg_l'], y0, y0 + p['chg_w'], z0, z0 + p['chg_t'])
    chip = bx(x0 + 8, x0 + 12, y0 + 7.5, y0 + 11.5, z0 + p['chg_t'], z0 + p['chg_t'] + 0.9)
    return [('MCP73871 PCB', pcb), ('MCP73871 chip', chip)]


def perfboard(L):
    p = P
    x0 = p['pb_x0']
    board = bx(x0, x0 + p['pb_len'], p['pb_y0'], p['pb_y0'] + p['pb_w'], p['pb_z'], L['pb_top'])
    t = L['pb_top']
    cx, cy = L['cap']
    cap = cyl((cx, cy, t + p['cap_d'] / 2), (cx + p['cap_l'], cy, t + p['cap_d'] / 2), p['cap_d'] / 2)
    small = [cyl((84.0, 6.0, t + 2.5), (95.0, 6.0, t + 2.5), 2.5)]                       # 10 uF lying down
    ys = -0.5
    xx = 20.0
    for i in range(4):                                                                    # 3 x 1N5819, zener
        small.append(cyl((xx, ys, t + 1.4), (xx + 5.2, ys, t + 1.4), 1.35))
        xx += 6.5
    for i in range(5):                                                                    # RC filters, divider
        small.append(cyl((xx, ys, t + 1.2), (xx + 6.0, ys, t + 1.2), 1.15))
        xx += 7.0
    for cx_ in (xx, 84.0, 89.0, 94.0):                                                   # 100 nF ceramics
        cy_ = ys if cx_ == xx else 10.0
        small.append(bx(cx_, cx_ + 4, cy_ - 1.25, cy_ + 1.25, t, t + 4))
    return [('Perfboard 24x82', board), ('Electrolytic', cap), ('Passives', uni(*small))]


def breakouts(L):
    p = P
    out = []
    jz = jack_z(L)
    mz = mouth_z(L)
    for i, (end, yc) in enumerate(L['rj']):
        g = rj_geom(L, end, yc)
        board = bx(g['bxr'][0], g['bxr'][1], yc - p['rj_bw'] / 2, yc + p['rj_bw'] / 2, L['bz0'], L['bz1'])
        for hx, hy in g['holes']:
            board = cut(board, cyl((hx, hy, L['bz0'] - 1), (hx, hy, L['bz1'] + 1), p['rj_hole_d'] / 2))
        jack = bx(g['jx'][0], g['jx'][1], yc - p['rj_jw'] / 2, yc + p['rj_jw'] / 2, jz[0], jz[1])
        face = g['jx'][0] if end == 'A' else g['jx'][1]
        mx = (face - 1, face + 13.5) if end == 'A' else (face - 13.5, face + 1)
        jack = cut(jack, bx(mx[0], mx[1], yc - p['rj_mouth_w'] / 2, yc + p['rj_mouth_w'] / 2, mz[0], mz[1]))
        out += [('RJ12 %d board' % (i + 1), board), ('RJ12 %d jack' % (i + 1), jack)]
    u = usb_geom(L)
    yc = u['yc']
    board = bx(u['bxr'][0], u['bxr'][1], yc - p['usb_bw'] / 2, yc + p['usb_bw'] / 2, L['bz0'], L['bz1'])
    rec = cut(bx(u['rx'][0], u['rx'][1], yc - p['rec_w'] / 2, yc + p['rec_w'] / 2, u['rz'][0], u['rz'][1]),
              bx(u['rx'][1] - 6.5, u['rx'][1] + 1, yc - 4.2, yc + 4.2, u['rz'][0] + 0.35, u['rz'][1] - 0.35))
    out += [('USB-C board', board), ('USB-C receptacle', rec)]
    return out


def battery(L):
    p = P
    c = L['bat_c']
    x0, x1 = p['bat_x0'], p['bat_x0'] + p['bat_l']
    cell = cyl((x0, c[1], c[2]), (x1, c[1], c[2]), p['bat_d'] / 2)
    lead = cyl((x1, c[1], c[2] + 3), (x1 + p['bat_lead'], c[1], c[2] + 3), 1.2)
    return [('18650 cell', cell), ('18650 lead', lead)]


def plugs(L):
    p = P
    out = []
    mz = mouth_z(L)
    for i, (end, yc) in enumerate(L['rj']):
        g = rj_geom(L, end, yc)
        face = g['jx'][0] if end == 'A' else g['jx'][1]
        s = -1 if end == 'A' else 1                      # outward direction
        ins = 12.5                                       # plug depth inside the jack
        x_in, x_out = face - s * ins, face + s * 9.0     # 9 mm of plug body outside the jack face
        plug = bx(min(x_in, x_out), max(x_in, x_out), yc - p['rj_mouth_w'] / 2 + 0.15, yc + p['rj_mouth_w'] / 2 - 0.15,
                  mz[0] + 0.15, mz[1] - 0.15)
        cord = bx(min(x_out, x_out + s * 40), max(x_out, x_out + s * 40), yc - 3.3, yc + 3.3,
                  (mz[0] + mz[1]) / 2 - 1.5, (mz[0] + mz[1]) / 2 + 1.5)
        out += [('RJ12 plug %d' % (i + 1), plug), ('White cord %d' % (i + 1), cord)]
    u = usb_geom(L)
    zc = (u['rz'][0] + u['rz'][1]) / 2
    e, Lo = L['e'], L['Lo']
    shell = bx(e - 6.5, Lo + 0.5, u['yc'] - 4.15, u['yc'] + 4.15, zc - 1.25, zc + 1.25)
    over = bx(Lo + 0.5, Lo + 15.5, u['yc'] - 6.0, u['yc'] + 6.0, zc - 3.25, zc + 3.25)
    cable = cyl((Lo + 15.5, u['yc'], zc), (Lo + 45, u['yc'], zc), 1.75)
    solar = cyl((e - 3, -17.0, 15.0), (Lo + 30, -17.0, 15.0), 1.2)
    zh = bx(Lo + 30, Lo + 36, -19.25, -14.75, 13.5, 16.5)
    out += [('USB-C plug', uni(shell, over, cable)), ('Solar pigtail', uni(solar, zh))]
    return out


# ------------------------------------------------------------------ Fusion side
APPEAR = {
    'Rail': 'Plastic - Matte (White)', 'Case tray': 'Plastic - Matte (White)', 'Case lid': 'Plastic - Translucent Matte (Blue)',
    'Perfboard': 'Plastic - Glossy (Green)', 'Modules': 'Plastic - Glossy (Green)', 'Breakouts': 'Plastic - Matte (Black)',
    'Battery': 'Plastic - Glossy (Blue)', 'Plugs': 'Plastic - Matte (White)',
}


def appearance(design, name):
    app = adsk.core.Application.get()
    a = design.appearances.itemByName(name)
    if a:
        return a
    for i in range(app.materialLibraries.count):
        lib = app.materialLibraries.item(i)
        try:
            src = lib.appearances.itemByName(name)
        except Exception:
            src = None
        if src:
            return design.appearances.addByCopy(src, name)
    return None


def add_part(design, name, bodies):
    root = design.rootComponent
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = PREFIX + name
    ap = appearance(design, APPEAR.get(name, 'Plastic - Matte (White)'))
    for nm, b in bodies:
        bb = comp.bRepBodies.add(b)
        bb.name = nm
        if ap:
            bb.appearance = ap
    return occ


def remove_old(design):
    occs = design.rootComponent.occurrences
    for i in range(occs.count - 1, -1, -1):
        if occs.item(i).component.name.startswith(PREFIX):
            occs.item(i).deleteMe()


def interference(groups):
    """Volume (mm3) of every overlap between bodies of different groups. Each body is checked on its own."""
    flat = [(g, nm, b) for g, bodies in groups for nm, b in bodies]
    hits = []
    for i in range(len(flat)):
        gi, ni, bi = flat[i]
        for j in range(i + 1, len(flat)):
            gj, nj, bj = flat[j]
            if gi == gj:
                continue
            a, b = bi.boundingBox, bj.boundingBox
            if (a.maxPoint.x <= b.minPoint.x or b.maxPoint.x <= a.minPoint.x or a.maxPoint.y <= b.minPoint.y or
                    b.maxPoint.y <= a.minPoint.y or a.maxPoint.z <= b.minPoint.z or b.maxPoint.z <= a.minPoint.z):
                continue
            c = tbm.copy(bi)
            tbm.booleanOperation(c, tbm.copy(bj), adsk.fusion.BooleanTypes.IntersectionBooleanType)
            try:
                v = c.volume * 1000.0 if c.faces.count else 0.0
            except Exception:
                v = 0.0
            if v > 0.01:
                hits.append('%s / %s: %.2f mm3' % (ni, nj, v))
    return hits


def build(design):
    global tbm
    tbm = adsk.fusion.TemporaryBRepManager.get()
    L = layout()
    modules = esp32(L) + drv8833(L, L['drv1'], 1) + drv8833(L, L['drv2'], 2) + charger(L)
    groups = [
        ('Rail', rail_ref(L)),
        ('Case tray', [('Case tray', case_tray(L))]),
        ('Case lid', [('Case lid', case_lid(L))]),
        ('Perfboard', perfboard(L)),
        ('Modules', modules),
        ('Breakouts', breakouts(L)),
        ('Battery', battery(L)),
        ('Plugs', plugs(L)),
    ]
    board = groups[3][1][0][1]                    # drill the perfboard where the header pins go through
    for nm, b in modules:
        if nm.endswith('pins'):
            cut(board, tbm.copy(b))
    sweep = [('Rod sweep', rod_sweep(L))]
    hits = interference(groups + [('Sweep', sweep)])
    hits = [h for h in hits if not h.startswith('Tilt rod / Rod sweep')]
    for name, bodies in groups:
        add_part(design, name, bodies)
    p = P
    return {
        'case': 'outer %.1f x %.1f x %.1f mm (groove top %.1f, |Y| < %.1f), wall %.1f' % (
            L['Lo'], 2 * p['half_w'], p['top'], p['groove_top'], p['groove_hw'], p['wall']),
        'rod sweep clearance to groove (mm)': round(p['rod_z'] - p['rod'] * math.sqrt(2) / 2 - p['groove_top'], 2),
        'perfboard': 'Z %.1f..%.1f, X %.1f..%.1f, Y %.1f..%.1f' % (p['pb_z'], L['pb_top'], p['pb_x0'], p['pb_x0'] + p['pb_len'],
                                                                   p['pb_y0'], p['pb_y0'] + p['pb_w']),
        'interference': hits or 'none',
    }
