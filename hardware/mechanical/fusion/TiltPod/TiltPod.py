"""TiltPod: the drive housing on the tilter's sensor (lid, -X) side, plus its end cover. It encloses the N20, the
AS5600's back, the tilter's own DRV8833 and the RJ12 jack, so tilter + motor + driver + sensor + plug are one unit.

  HOUSING    continues the tilter case's own cross-section (same width, steps under the rail lips, plateau, rounded
             long edges), closed on all sides except its two ends: the +X end seats on the lid's outer face, the -X
             end takes the cover. It touches the lid only (never the sensor board: a relief clears the board's edge).
             Two M3 x 20 flat-head bolts go through 4 mm bosses in its top room-side and bottom back corners, through
             the lid into M3 inserts in the main half (TiltPartsV4 pod_bolts). They go in with the cover off, straight
             down the empty housing, before anything else is fitted.
  COVER      2 mm plate flush with the housing's outline, 3 x M3 x 8 flat head into heat-set inserts in the housing's
             corners; the RJ12 jack's body fills a window in it, face flush with the cover (like a wall plate), so the
             plug's latch is reachable; a tab on its inside holds the jack down.
  INSIDE     RJ12 breakout on two pegs on the floor (mouth at the cover), DRV8833 sliding in along X between two
             grooved rails on the room-side wall (stop at the far end, the cover closes the rails), cradle under the
             N20's end. 10 uF ceramic across the DRV8833's VCC/GND.

RJ12 (pin 1 -> pin 1 cords): 1 VBAT, 2 IN1, 3 GND, 4 ANGLE, 5 EN (AS5600 VCC + DRV8833 sleep), 6 IN2.

Global tilter coordinates (TiltPartsV4): X along the rod (lid face at X -8.33), Y across (-Y room side), Z up from the
rail floor. From TiltPartsV4.layout(): N20 X -6.83..-31.83, Y -16.19..-4.19, Z 3.81..13.81; AS5600 board back
X -9.93, Y 2.75..26.15, Z 7.88..31.28; its bolts' heads (flat head on the board) proud to X -11.1.
"""

import math

P = dict(
    lid_x=-8.33, half_w=27.7, floor_z=0.2, step_z=33.3, plateau_hw=21.7, plateau_z=38.9, edge_r=1.0,
    wall=1.8, floor=1.8, ceil=1.8,
    rod_z=24.0, rod=4.0, rod_through=False,       # True if the blind's rod runs on past the tilter on this side
    # tilter bolts (TiltPartsV4 pod_bolts): flat head flush in a boss
    pod_bolts=((-23.0, 27.0), (22.0, 5.5)), boss_len=4.0, boss_r=4.2, m3=3.4, cs_d=6.4,
    # cover screws: M3 x 8 flat head into inserts (Ø4.0 x 6.7) in corner bosses
    cover_t=2.0,
    # 3 cover screws: the room side's top corner is the DRV8833's slide-in path, and the back side's bottom corner is
    # the hex key's path to the (22, 5.5) tilter bolt
    cov_screws=((-23.0, 4.9), (23.0, 12.0), (23.0, 28.7)),
    ins_d=4.0, ins_depth=6.7, ins_wall=1.4, register=1.2,
    motor=(-31.83, -16.19, -4.19, 3.81, 13.81), motor_tabs=2.5,
    board=(2.75, 26.15, 7.88, 31.28), board_relief=0.5,
    # RJ12 breakout (listing photo): board 19.4 W x 19.9 D, jack 13.5 W x 14.7 L x 13.0 H overhanging 4.5;
    # holes 7.0 from the back edge, 2.1 from the sides
    rj_bw=19.4, rj_bd=19.9, rj_jw=13.5, rj_jl=14.7, rj_jh=13.0, rj_over=4.5, rj_hole=7.0, rj_hole_side=2.1,
    rj_y=9.5, rj_x0=-16.0,      # jack face flush with the cover's outer face
    rj_z=5.0, rj_mouth_w=9.9, rj_mouth_h=8.6,
    # DRV8833 (18.5 x 16): stands in the XZ plane, 16 along X, pin rows (on the 18.5 edges) vertical at its X ends
    drv_l=16.0, drv_h=18.5, drv_t=1.6, drv_y=-23.2, drv_x1=-14.5, drv_z0=11.0,
)
p = P
P['iw'] = p['half_w'] - p['wall']
P['rj_face'] = p['rj_x0'] - p['rj_bd'] - p['rj_over']      # jack mouth, flush with the cover's outer face
P['end_x'] = p['rj_face'] + p['cover_t']                    # housing's -X end = cover's inner face
P['cover_x0'] = p['end_x'] - p['cover_t']
P['boss_x'] = p['lid_x'] - p['boss_len']


def rj_holes():
    hx = p['rj_x0'] - p['rj_hole']
    hy = p['rj_bw'] / 2 - p['rj_hole_side']
    return [(hx, p['rj_y'] - hy), (hx, p['rj_y'] + hy)]


def profile_box(bx, uni, x0, x1, grow=0.0):
    """The tilter case's cross-section (full width under the lips, plateau between them), extruded along X."""
    return uni(bx(x0, x1, -p['half_w'] - grow, p['half_w'] + grow, p['floor_z'] - grow, p['step_z'] + grow),
               bx(x0, x1, -p['plateau_hw'] - grow, p['plateau_hw'] + grow, p['step_z'] - 1, p['plateau_z'] + grow))


def build(tbm, bx, cyl, cone, uni, cut):
    """{group: [(name, body)]}; bx/cyl/cone make temporary B-rep bodies in mm."""
    w = p['wall']
    iw = p['iw']
    x0, x1 = p['end_x'], p['lid_x']
    out = {}

    # ---------------- housing
    inner = uni(bx(x0 - 1, x1 + 1, -iw, iw, p['floor_z'] + p['floor'], p['step_z'] - p['ceil']),
                bx(x0 - 1, x1 + 1, -p['plateau_hw'] + w, p['plateau_hw'] - w, p['step_z'] - 2, p['plateau_z'] - p['ceil']))
    house = cut(profile_box(bx, uni, x0, x1), inner)
    # bosses for the two tilter bolts, joined to the walls by webs
    for by, bz in p['pod_bolts']:
        sy = -1 if by < 0 else 1
        boss = uni(cyl((p['boss_x'], by, bz), (x1, by, bz), p['boss_r']),
                   bx(p['boss_x'], x1, by, sy * (iw + 0.5), bz - p['boss_r'] * 0.8, bz + p['boss_r'] * 0.8),
                   bx(p['boss_x'], x1, by - p['boss_r'] * 0.8, by + p['boss_r'] * 0.8, bz,
                      (p['step_z'] - p['ceil'] + 0.5) if bz > 16 else (p['floor_z'] + p['floor'] - 0.5)))
        house = uni(house, boss)
    # corner bosses for the cover's inserts
    ir = p['ins_d'] / 2 + p['ins_wall']
    for cy, cz in p['cov_screws']:
        sy = -1 if cy < 0 else 1
        zw = (p['step_z'] - p['ceil'] + 0.5) if cz > 16 else (p['floor_z'] + p['floor'] - 0.5)
        house = uni(house, cyl((x0, cy, cz), (x0 + p['ins_depth'] + 1.5, cy, cz), ir),
                    bx(x0, x0 + p['ins_depth'] + 1.5, cy, sy * (iw + 0.5), cz - ir, cz + ir),
                    bx(x0, x0 + p['ins_depth'] + 1.5, cy - ir, cy + ir, cz, zw))
    # tilter bolt holes: clearance + 90° countersink, head flush with the boss end
    for by, bz in p['pod_bolts']:
        house = cut(house, cyl((p['boss_x'] - 1, by, bz), (x1 + 1, by, bz), p['m3'] / 2),
                    cone((p['boss_x'] - 0.01, by, bz), p['cs_d'] / 2, (p['boss_x'] + (p['cs_d'] - p['m3']) / 2, by, bz), p['m3'] / 2))
    # relief round the AS5600 board's edge (the housing never touches the board) and its bolt heads
    b0, b1, c0, c1 = p['board']
    r = p['board_relief']
    house = cut(house, bx(x1 - 1.6 - r, x1 + 1, b0 - r, b1 + r, c0 - r, c1 + r))
    # cradle under the N20's end
    mx0, my0, my1, mz0, mz1 = p['motor']
    house = uni(house, cut(bx(mx0 + 3.0, mx0 + 6.0, my0 - 1.5, my1 + 1.5, p['floor_z'] + 1, mz0 + 2.0),
                           bx(mx0 + 2.0, mx0 + 7.0, my0 - 0.15, my1 + 0.15, mz0 - 0.15, mz0 + 5)))
    # RJ12 pegs on collars
    for hx, hy in rj_holes():
        house = uni(house, cyl((hx, hy, p['floor_z'] + 1), (hx, hy, p['rj_z']), 2.4),
                    cyl((hx, hy, p['rj_z'] - 0.1), (hx, hy, p['rj_z'] + 1.6 + 1.2), 1.3))
    # DRV8833 rails: grooved bars along X on the room-side wall, open at the cover end, stop at the far end
    gy0, gy1 = p['drv_y'] - 0.15, p['drv_y'] + p['drv_t'] + 0.15
    xa, xb = x0 + p['register'] + 0.3, p['drv_x1'] + 1.5          # clear of the cover's register lip
    z_lo, z_hi = p['drv_z0'], p['drv_z0'] + p['drv_h']
    for rz0, rz1, gz0, gz1 in ((z_lo - 2.4, z_lo + 1.2, z_lo - 1.0, z_lo + 3.0),      # rail under the board, groove 1.0 deep
                               (z_hi - 1.2, z_hi + 2.4, z_hi - 3.0, z_hi + 1.0)):     # rail over it
        rail = bx(xa, xb, -iw - 0.5, gy1 + 1.4, rz0, rz1)
        rail = cut(rail, bx(xa - 1, p['drv_x1'] + 0.3, gy0, gy1, gz0, gz1))
        house = uni(house, rail)
    for cy, cz in p['cov_screws']:                                     # insert holes last
        house = cut(house, cyl((x0 - 1, cy, cz), (x0 + p['ins_depth'], cy, cz), p['ins_d'] / 2))
    out['Housing'] = [('Housing', house)]

    # ---------------- cover
    cover = profile_box(bx, uni, p['cover_x0'], x0)
    cover = uni(cover, cut(bx(x0 - 0.01, x0 + p['register'], -iw + 0.15, iw - 0.15, p['floor_z'] + p['floor'] + 0.15,
                              p['step_z'] - p['ceil'] - 0.15),
                           bx(x0 - 1, x0 + 2, -iw + 1.35, iw - 1.35, p['floor_z'] + p['floor'] + 1.35, p['step_z'] - p['ceil'] - 1.35)))
    jz0 = p['rj_z'] + 1.6
    mzc = jz0 + p['rj_jh'] / 2 - 0.5
    for cy, cz in p['cov_screws']:                                  # register ring clears the corner bosses
        cover = cut(cover, cyl((x0 - 0.01, cy, cz), (x0 + 2, cy, cz), ir + 0.3))
    cover = uni(cover, bx(x0, x0 + 5.0, p['rj_y'] - 3.0, p['rj_y'] + 3.0, jz0 + p['rj_jh'] + 0.1, jz0 + p['rj_jh'] + 1.6))  # jack tab
    cover = uni(cover, bx(x0, x0 + 4.0, p['rj_y'] - 3.0, p['rj_y'] + 3.0, jz0 + p['rj_jh'] + 0.1, p['step_z'] - p['ceil'] - 0.2))
    win = bx(p['cover_x0'] - 1, x0 + 1, p['rj_y'] - p['rj_jw'] / 2 - 0.15, p['rj_y'] + p['rj_jw'] / 2 + 0.15,
             jz0 - 0.15, jz0 + p['rj_jh'] + 0.15)                    # the jack's body fills the window, face flush
    cover = cut(cover, win)
    for cy, cz in p['cov_screws']:
        cover = cut(cover, cyl((p['cover_x0'] - 1, cy, cz), (x0 + 3, cy, cz), p['m3'] / 2),
                    cone((p['cover_x0'] - 0.01, cy, cz), p['cs_d'] / 2, (p['cover_x0'] + (p['cs_d'] - p['m3']) / 2, cy, cz), p['m3'] / 2))
    cover = cut(cover, tbm.copy(house))                              # register lip clears every boss and rail
    if p['rod_through']:
        rs = p['rod'] * math.sqrt(2) / 2 + 0.8
        cover = cut(cover, cyl((p['cover_x0'] - 1, 0, p['rod_z']), (x0 + 3, 0, p['rod_z']), rs))
    out['Cover'] = [('Cover', cover)]

    # ---------------- parts inside
    parts = []
    rb = bx(p['rj_x0'] - p['rj_bd'], p['rj_x0'], p['rj_y'] - p['rj_bw'] / 2, p['rj_y'] + p['rj_bw'] / 2, p['rj_z'], p['rj_z'] + 1.6)
    for hx, hy in rj_holes():
        rb = cut(rb, cyl((hx, hy, p['rj_z'] - 1), (hx, hy, p['rj_z'] + 3), 1.5))
    parts.append(('RJ12 board', rb))
    jack = bx(p['rj_face'], p['rj_face'] + p['rj_jl'], p['rj_y'] - p['rj_jw'] / 2, p['rj_y'] + p['rj_jw'] / 2, jz0, jz0 + p['rj_jh'])
    jack = cut(jack, bx(p['rj_face'] - 1, p['rj_face'] + 13, p['rj_y'] - p['rj_mouth_w'] / 2, p['rj_y'] + p['rj_mouth_w'] / 2,
                        mzc - p['rj_mouth_h'] / 2, mzc + p['rj_mouth_h'] / 2))
    parts.append(('RJ12 jack', jack))
    parts.append(('RJ12 pins', bx(p['rj_face'] + p['rj_over'], p['rj_face'] + p['rj_over'] + 9, p['rj_y'] - 5, p['rj_y'] + 5,
                                  p['floor_z'] + p['floor'] + 0.2, p['rj_z'])))
    dx1, dx0 = p['drv_x1'], p['drv_x1'] - p['drv_l']
    parts.append(('DRV8833', bx(dx0, dx1, p['drv_y'], p['drv_y'] + p['drv_t'], z_lo, z_hi)))
    parts.append(('DRV8833 chip', bx((dx0 + dx1) / 2 - 2.5, (dx0 + dx1) / 2 + 2.5, p['drv_y'] + p['drv_t'],
                                     p['drv_y'] + p['drv_t'] + 1.0, z_lo + 7, z_lo + 11)))
    parts.append(('C 10uF', bx(dx0 + 4, dx0 + 7, p['drv_y'] + p['drv_t'], p['drv_y'] + p['drv_t'] + 2.0, z_lo + 2.5, z_lo + 5.5)))
    parts.append(('N20 tabs', bx(mx0 - p['motor_tabs'], mx0, my0 + 2, my1 - 2, mz0 + 2, mz1 - 2)))
    out['Inside'] = parts
    heads = []
    for by, bz in p['pod_bolts']:
        heads.append(('M3x20 head', cone((p['boss_x'], by, bz), 2.95, (p['boss_x'] + 1.65, by, bz), 1.5)))
    for cy, cz in p['cov_screws']:
        heads.append(('M3x8 head', cone((p['cover_x0'], cy, cz), 2.95, (p['cover_x0'] + 1.65, cy, cz), 1.5)))
    out['Screws'] = heads
    plug = bx(p['rj_face'] - 9.0, p['rj_face'] + 12.5, p['rj_y'] - p['rj_mouth_w'] / 2 + 0.15, p['rj_y'] + p['rj_mouth_w'] / 2 - 0.15,
              mzc - p['rj_mouth_h'] / 2 + 0.15, mzc + p['rj_mouth_h'] / 2 - 0.15)
    cord = bx(p['rj_face'] - 60, p['rj_face'] - 9.0, p['rj_y'] - 3.3, p['rj_y'] + 3.3, mzc - 1.5, mzc + 1.5)
    out['Plug'] = [('RJ12 plug', plug), ('White cord', cord)]
    return out


def summary():
    return {
        'housing': 'X %.2f..%.2f (%.1f mm beyond the lid face), same section as the tilter case' % (
            p['cover_x0'], p['lid_x'], p['lid_x'] - p['cover_x0']),
        'fasteners': '2 x M3 x 20 flat head (housing -> tilter, inserts in the main half); 3 x M3 x 8 flat head + 3 inserts (cover)',
        'jack mouth': 'cover at X %.2f, centre Y %.1f, Z %.1f' % (p['cover_x0'], p['rj_y'], p['rj_z'] + 1.6 + p['rj_jh'] / 2 - 0.5),
    }
