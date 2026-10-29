"""TiltPod: the plug pod on the tilter's sensor (lid, -X) side. Holds the RJ12 jack and the tilter's own DRV8833, and
closes over the N20's tabs and the AS5600's solder pads, so tilter + motor + driver + sensor + plug are one unit.

Driver at the tilter (decided 2026-10-28): the phone cord carries battery power and logic, not the 20 kHz motor PWM,
so the flat cord no longer couples motor noise into the angle wire. RJ12 pinout (pin 1 -> pin 1 cords):
  1 VBAT   2 IN1   3 GND   4 ANGLE (AS5600 OUT)   5 EN (AS5600 VCC + DRV8833 ULT/sleep)   6 IN2

  POD TRAY   bulkhead clamped onto the AS5600 board by the tilter's two board bolts (now M3 x 20 flat head, heads in
             countersunk 3 mm bosses), floor + walls to the end wall with the jack mouth. Window in the bulkhead over
             the AS5600's pads, cut-out round the N20, cradle under the N20's end, slot for the tilt rod.
  POD LID    flat top under the rail lips, snaps into the walls.
  INSIDE     RJ12 breakout on two pegs (back side, jack mouth on the end wall), DRV8833 standing in two slots along
             the room-side wall, 10 uF across its VCC/GND.

Uses the tilter's global coordinates (TiltPartsV4): X along the rod (lid face at X -8.33), Y across (-Y room side),
Z up from the rail floor. Numbers from TiltPartsV4.layout() (2026-10-28 build): N20 X -6.83..-31.83, Y -16.19..-4.19,
Z 3.81..13.81; AS5600 board back X -9.93, Y 2.75..26.15, Z 7.88..31.28; board bolts (Y, Z) (6.45, 11.58), (22.45, 27.58).
"""

import math

P = dict(
    lid_x=-8.33, board_back=-9.93, half_w=27.7, floor_z=0.2, top=33.2, wall=1.6, floor=1.4, lid=1.2,
    rail_w=55.5, rail_h=36.5, rail_wall=2.0, lip_in=4.5, lip_h=3.0, rod_z=24.0, rod=4.0,
    boss_t=3.0, bulk_t=2.0, boss_r=4.5, cs_d=6.4, m3=3.4,
    bolts=((6.45, 11.58), (22.45, 27.58)),
    motor=(-31.83, -16.19, -4.19, 3.81, 13.81), motor_tabs=2.5,
    board=(2.75, 26.15, 7.88, 31.28),
    # RJ12 breakout (listing photo): board 19.4 W x 19.9 D, jack 13.5 W x 14.7 L x 13.0 H overhanging 4.5; holes
    # 7.0 from the back edge, 2.1 from the sides
    rj_bw=19.4, rj_bd=19.9, rj_jw=13.5, rj_jl=14.7, rj_jh=13.0, rj_over=4.5, rj_hole=7.0, rj_hole_side=2.1,
    rj_y=13.0, rj_x0=-14.0, rj_z=4.6, rj_mouth_w=9.9, rj_mouth_h=8.6,
    # DRV8833 standing on its 18.5 edge along X, board plane at Y drv_y
    drv_l=18.5, drv_h=16.0, drv_t=1.6, drv_y=-23.6, drv_x0=-15.0, drv_z0=11.0,
)
P['bulk_x1'] = P['board_back'] - P['bulk_t']          # bulkhead's inner face
P['boss_x1'] = P['board_back'] - P['boss_t']
P['rj_face'] = P['rj_x0'] - P['rj_bd'] - P['rj_over']  # jack mouth = end wall inner face
P['end_x0'] = P['rj_face'] - P['wall']                  # pod's outer end
P['iw'] = P['half_w'] - P['wall']


def rj_holes():
    p = P
    hx = p['rj_x0'] - p['rj_hole']
    hy = p['rj_bw'] / 2 - p['rj_hole_side']
    return [(hx, p['rj_y'] - hy), (hx, p['rj_y'] + hy)]


def build(tbm, bx, cyl, uni, cut):
    """Returns {group: [(name, body)]}. bx(x0,x1,y0,y1,z0,z1), cyl(p1,p2,r) make temporary B-rep bodies (mm)."""
    p = P
    hw, iw, w = p['half_w'], p['iw'], p['wall']
    z0, zt = p['floor_z'], p['top'] - p['lid']
    mx0, my0, my1, mz0, mz1 = p['motor']
    out = {}

    # ---------------- tray
    shell = cut(bx(p['end_x0'], p['bulk_x1'], -hw, hw, z0, zt),
                bx(p['rj_face'], p['bulk_x1'] + 1, -iw, iw, z0 + p['floor'], zt + 1))
    bulk = bx(p['bulk_x1'], p['board_back'], -hw, hw, z0, zt)
    for by, bz in p['bolts']:
        bulk = uni(bulk, cyl((p['boss_x1'], by, bz), (p['board_back'], by, bz), p['boss_r']))
    b0, b1, c0, c1 = p['board']
    win = cut(bx(p['boss_x1'] - 1, p['board_back'] + 1, b0 + 1.2, b1 - 1.2, c0 + 1.2, c1 - 1.2),
              *[cyl((p['boss_x1'] - 2, by, bz), (p['board_back'] + 2, by, bz), p['boss_r']) for by, bz in p['bolts']])
    bulk = cut(bulk, win)
    bulk = cut(bulk, bx(p['boss_x1'] - 1, p['board_back'] + 1, my0 - 0.6, my1 + 0.6, mz0 - 0.6, mz1 + 0.6))
    # spacer rim: rests on the lid face where the board isn't (bottom edge, room side, top edge left of the rod)
    rim = uni(bx(p['board_back'], p['lid_x'], -hw, hw, z0, z0 + 2.2),
              bx(p['board_back'], p['lid_x'], -hw, -hw + 2.0, z0, zt),
              bx(p['board_back'], p['lid_x'], -hw, -4.2, zt - 1.6, zt))
    rim = cut(rim, bx(p['board_back'] - 1, p['lid_x'] + 1, my0 - 0.6, my1 + 0.6, mz0 - 0.6, mz1 + 0.6))
    tray = uni(shell, bulk, rim)
    for by, bz in p['bolts']:                                   # M3 clearance + 90° countersink (flat head flush)
        tray = cut(tray, cyl((p['boss_x1'] - 1, by, bz), (p['lid_x'] + 1, by, bz), p['m3'] / 2),
                   tbm.createCylinderOrCone(P3(p['boss_x1'] - 0.01, by, bz), p['cs_d'] / 20.0,
                                            P3(p['boss_x1'] + (p['cs_d'] - p['m3']) / 2, by, bz), p['m3'] / 20.0))
    rs = p['rod'] * math.sqrt(2) / 2 + 1.0                       # tilt rod slot, open at the top
    tray = cut(tray, bx(p['end_x0'] - 1, p['lid_x'] + 1, -rs, rs, p['rod_z'] - rs, 60))
    # cradle under the N20's end
    tray = uni(tray, bx(mx0 + 3.0, mx0 + 6.0, my0 - 1.6, my1 + 1.6, z0 + 0.5, mz0 - 0.15))
    # RJ12: two pegs through its holes on collars; jack mouth through the end wall
    for hx, hy in rj_holes():
        tray = uni(tray, cyl((hx, hy, z0 + 0.5), (hx, hy, p['rj_z']), 2.4),
                   cyl((hx, hy, p['rj_z'] - 0.1), (hx, hy, p['rj_z'] + 1.6 + 1.2), 1.3))
    jz0 = p['rj_z'] + 1.6
    tray = cut(tray, bx(p['end_x0'] - 1, p['rj_face'] + 0.5, p['rj_y'] - p['rj_jw'] / 2 - 0.3, p['rj_y'] + p['rj_jw'] / 2 + 0.3,
                        jz0 - 0.3, jz0 + p['rj_jh'] + 0.3))
    # DRV8833 slots: a block on the room-side wall at each end of the board, slotted for the board's edge; they stop
    # below the lid's snap skirt
    dy0, dy1 = p['drv_y'] - 0.15, p['drv_y'] + p['drv_t'] + 0.15
    for xe, sg in ((p['drv_x0'], 1), (p['drv_x0'] - p['drv_l'], -1)):
        ch = bx(xe - sg * 1.0, xe + sg * 1.6, -iw - 0.1, dy1 + 1.2, p['drv_z0'] - 1.5, zt - 3.3)
        ch = cut(ch, bx(xe - sg * 2.0, xe + sg * 0.3, dy0, dy1, p['drv_z0'], zt))
        tray = uni(tray, ch)
    # snap windows in the long walls
    for sx in (p['bulk_x1'] - 6.0, p['end_x0'] + 6.0):
        for s in (-1, 1):
            tray = cut(tray, bx(sx - 3, sx + 3, s * (iw - 0.5), s * (hw + 1), zt - 2.2, zt - 0.6))
    out['Pod tray'] = [('Pod tray', tray)]

    # ---------------- lid
    lid = bx(p['end_x0'], p['bulk_x1'], -hw, hw, zt, p['top'])
    for s in (-1, 1):
        lid = uni(lid, bx(p['end_x0'] + 3, p['bulk_x1'] - 3, s * (iw - 0.1), s * (iw - 0.9), zt - 3.0, zt + 0.1))
        for sx in (p['bulk_x1'] - 6.0, p['end_x0'] + 6.0):
            lid = uni(lid, bx(sx - 2.5, sx + 2.5, s * (iw - 0.1), s * (iw + 0.35), zt - 2.0, zt - 0.8))
    lid = uni(lid, bx(p['rj_x0'] - 12, p['rj_x0'] - 8, p['rj_y'] - 3, p['rj_y'] + 3, jz0 + p['rj_jh'] + 0.1, zt + 0.1))  # holds the jack down
    lid = cut(lid, bx(p['end_x0'] - 1, p['bulk_x1'] + 1, -rs, rs, p['rod_z'] - rs, zt + 0.01))
    out['Pod lid'] = [('Pod lid', lid)]

    # ---------------- parts inside
    parts = []
    rb = bx(p['rj_x0'] - p['rj_bd'], p['rj_x0'], p['rj_y'] - p['rj_bw'] / 2, p['rj_y'] + p['rj_bw'] / 2, p['rj_z'], p['rj_z'] + 1.6)
    for hx, hy in rj_holes():
        rb = cut(rb, cyl((hx, hy, p['rj_z'] - 1), (hx, hy, p['rj_z'] + 3), 1.5))
    parts.append(('RJ12 board', rb))
    jack = bx(p['rj_face'], p['rj_face'] + p['rj_jl'], p['rj_y'] - p['rj_jw'] / 2, p['rj_y'] + p['rj_jw'] / 2, jz0, jz0 + p['rj_jh'])
    mzc = jz0 + p['rj_jh'] / 2 - 0.5
    jack = cut(jack, bx(p['rj_face'] - 1, p['rj_face'] + 13, p['rj_y'] - p['rj_mouth_w'] / 2, p['rj_y'] + p['rj_mouth_w'] / 2,
                        mzc - p['rj_mouth_h'] / 2, mzc + p['rj_mouth_h'] / 2))
    parts.append(('RJ12 jack', jack))
    parts.append(('RJ12 jack pins', bx(p['rj_face'] + p['rj_over'], p['rj_face'] + p['rj_over'] + 9, p['rj_y'] - 5, p['rj_y'] + 5,
                                       z0 + p['floor'] + 0.2, p['rj_z'])))
    dx1, dx0 = p['drv_x0'], p['drv_x0'] - p['drv_l']
    parts.append(('DRV8833 PCB', bx(dx0, dx1, p['drv_y'], p['drv_y'] + p['drv_t'], p['drv_z0'], p['drv_z0'] + p['drv_h'])))
    parts.append(('DRV8833 chip', bx((dx0 + dx1) / 2 - 2.5, (dx0 + dx1) / 2 + 2.5, p['drv_y'] + p['drv_t'],
                                     p['drv_y'] + p['drv_t'] + 1.0, p['drv_z0'] + 6, p['drv_z0'] + 10)))
    parts.append(('C 10uF', bx(dx0 + 2, dx0 + 6, p['drv_y'] + p['drv_t'], p['drv_y'] + p['drv_t'] + 2.5,
                               p['drv_z0'] + 1, p['drv_z0'] + 6)))
    parts.append(('N20 tabs', bx(mx0 - p['motor_tabs'], mx0, my0 + 2, my1 - 2, mz0 + 2, mz1 - 2)))
    for by, bz in p['bolts']:                                    # M3 x 20 flat heads, flush in the bosses
        parts.append(('M3x20 head', tbm.createCylinderOrCone(P3(p['boss_x1'], by, bz), 2.95 / 10.0,
                                                             P3(p['boss_x1'] + 1.65, by, bz), 1.5 / 10.0)))
    out['Pod parts'] = parts

    # ---------------- plug + cord, rod continuing on this side (in case it does)
    plug = bx(p['rj_face'] - 9.0, p['rj_face'] + 12.5, p['rj_y'] - p['rj_mouth_w'] / 2 + 0.15, p['rj_y'] + p['rj_mouth_w'] / 2 - 0.15,
              mzc - p['rj_mouth_h'] / 2 + 0.15, mzc + p['rj_mouth_h'] / 2 - 0.15)
    cord = bx(p['rj_face'] - 50, p['rj_face'] - 9.0, p['rj_y'] - 3.3, p['rj_y'] + 3.3, mzc - 1.5, mzc + 1.5)
    out['Pod plug'] = [('RJ12 plug', plug), ('White cord', cord)]
    return out


def P3(x, y, z):
    import adsk.core
    return adsk.core.Point3D.create(x / 10.0, y / 10.0, z / 10.0)


def summary():
    p = P
    return {
        'pod': 'X %.2f..%.2f (sticks out %.1f mm from the lid face), Y +-%.1f, Z %.1f..%.1f' % (
            p['end_x0'], p['lid_x'], p['lid_x'] - p['end_x0'], p['half_w'], p['floor_z'], p['top']),
        'board bolts': 'M3 x 20 flat head (was M3 x 18): +3 mm boss, head flush; thread reaches X +7.07 (was +6.92)',
        'jack mouth': 'end wall at X %.2f, centre Y %.1f, Z %.1f' % (p['rj_face'], p['rj_y'], p['rj_z'] + 1.6 + p['rj_jh'] / 2 - 0.5),
    }
