"""TiltPod: the sensor module on the tilter's lid (-X) side. One printed cup, open only toward the tilter, carrying
the AS5600 board, the tilter's DRV8833 and the RJ12 jack. It is wired completely on the bench (two loose leads left
for the motor), then slid onto the lid face over the motor and bolted through the tilter from the other side.

Assembly
  1. Tilter: build as before (N20 in the lid, gears, sensor gear + magnet). No bolts yet.
  2. Module on the bench: AS5600 board into its seat in the open face (chip facing out, pressed onto two pins through
     its spare holes); RJ12 breakout slid in along its rails until the jack is flush in the end wall (a detent holds
     it); DRV8833 slid into its rails on the room-side wall. Wire everything; leave two leads from OUT1/OUT2.
  3. Solder the two leads to the N20's tabs, slide the module onto the lid face (the motor goes into its cavity and
     its can drops into the cradle), and fit 4 x M3 x 25 flat head from the main half's back face: through both case
     halves (two of them through the AS5600 board) into heat-set inserts in the module. To open it up, undo those 4.
  4. The tilt rod slides in through the module's tube from outside at any time and may stay sticking out.

RJ12 (pin 1 -> pin 1 cords): 1 VBAT, 2 IN1, 3 GND, 4 ANGLE, 5 EN (AS5600 VCC + DRV8833 sleep), 6 IN2.

Global tilter coordinates (TiltPartsV4): X along the rod (lid face X -8.33), Y across (-Y room side), Z up from the
rail floor. From TiltPartsV4.layout(): N20 axis at (Y -10.19, Z 8.81): gearbox X -6.83..-15.83 (12 W x 10 H), can
X -15.83..-30.83 (Ø12, flats 10 apart top and bottom), end cap to -31.83, tabs to -34.3. AS5600 board X -9.93..-8.33,
Y 2.75..26.15, Z 7.88..31.28, holes at (+-8, +-8) from (14.45, 19.58); the bolts use (6.45, 11.58) and (22.45, 27.58).
"""

import math

P = dict(
    lid_x=-8.33, half_w=27.7, floor_z=0.2, step_z=33.3, plateau_hw=21.7, plateau_z=38.9, edge_r=1.0,
    wall=1.8, floor=1.8, ceil=1.8, end_x=-43.5, end_t=2.0,
    rod_z=24.0, rod=4.0, rod_clear=0.65, tube_wall=1.2, tube_x1=-10.3,     # tube stops behind the board
    # 4 bolts from the main half; inserts (Ø4.0 x 6.7, M3 x 5.7 ruthex) in the module
    bolts_board=((6.45, 11.58), (22.45, 27.58)), bolts_rim=((-23.0, 27.0), (22.0, 5.5)),
    ins_d=4.0, ins_hole=8.0, ins_wall=1.5,
    # AS5600 board seat: rests on 4 bosses behind its corners, front flush with the open face
    board=(2.75, 26.15, 7.88, 31.28), board_t=1.6, chip=(14.45, 19.58), hole_off=8.0, board_hole=3.7,
    pin_holes=((6.45, 27.58),), pin_d=3.75,     # one pin; the board's other spare hole stays free
    # N20
    n20_axis=(-10.19, 8.81), n20_w=12.0, n20_h=10.0, gbx=(-6.83, -15.83), can=(-15.83, -30.83), cap_end=-31.83,
    tab_end=-34.3, motor_clear=0.4,
    # RJ12 breakout (listing photo): board 19.4 W x 19.9 D x 1.6, jack 13.5 W x 14.7 L x 13.0 H overhanging 4.5
    rj_bw=19.4, rj_bd=19.9, rj_jw=13.5, rj_jl=14.7, rj_jh=13.0, rj_over=4.5, rj_y=-11.85, rj_z=17.0,
    rj_mouth_w=9.9, rj_mouth_h=8.6,
    # DRV8833 (18.5 x 16): standing in the XZ plane in the back-middle, 16 along X; its +X end stops just behind the
    # AS5600 board, which closes its rails
    drv_l=16.0, drv_h=18.5, drv_t=1.6, drv_y=14.7, drv_x1=-10.5, drv_z0=4.0,
)
p = P
P['iw'] = p['half_w'] - p['wall']
P['in_x0'] = p['end_x'] + p['end_t']                 # end wall's inner face
P['rj_x0'] = p['end_x'] + p['rj_over']               # breakout board's front edge (jack face flush with the end wall)
P['rj_x1'] = p['rj_x0'] + p['rj_bd']


def profile(bx, uni, x0, x1, grow=0.0):
    """The tilter case's cross-section: full width under the rail lips, plateau between them."""
    return uni(bx(x0, x1, -p['half_w'] - grow, p['half_w'] + grow, p['floor_z'] - grow, p['step_z'] + grow),
               bx(x0, x1, -p['plateau_hw'] - grow, p['plateau_hw'] + grow, p['step_z'] - 1, p['plateau_z'] + grow))


def n20_section(bx, cyl, cut, uni, x0, x1, grow):
    """The N20 can's cross-section (round, flats top and bottom), extruded from x0 to x1."""
    ay, az = p['n20_axis']
    c = cyl((x0, ay, az), (x1, ay, az), p['n20_w'] / 2 + grow)
    return cut(c, bx(x0 - 1, x1 + 1, ay - 10, ay + 10, az + p['n20_h'] / 2 + grow, az + 20),
               bx(x0 - 1, x1 + 1, ay - 10, ay + 10, az - 20, az - p['n20_h'] / 2 - grow))


def build(tbm, bx, cyl, cone, uni, cut):
    w, iw = p['wall'], p['iw']
    x0, x1 = p['end_x'], p['lid_x']
    fz = p['floor_z'] + p['floor']
    out = {}

    # ---------------- cup
    inner = uni(bx(p['in_x0'], x1 + 1, -iw, iw, fz, p['step_z'] - p['ceil']),
                bx(p['in_x0'], x1 + 1, -p['plateau_hw'] + w, p['plateau_hw'] - w, p['step_z'] - 2, p['plateau_z'] - p['ceil']))
    cup = cut(profile(bx, uni, x0, x1), inner)

    # PRINTING: the module prints end wall down, so -X is "down" and every face that looks toward -X and doesn't sit on
    # the end wall is an overhang. Every feature below either runs all the way down to the end wall (a column) or ends
    # in a 45° taper (a cone or a gusset), so nothing needs support.
    xin = p['in_x0'] - 0.01

    def gusset(xf, y0, y1, z0, z1, base):
        """45° support under a face at X = xf spanning y0..y1 / z0..z1, growing out of the floor ('floor'), the ceiling
        ('ceil') or a side wall ('wall-' / 'wall+')."""
        import adsk.core, adsk.fusion
        k = math.sqrt(0.5)
        INTER = adsk.fusion.BooleanTypes.IntersectionBooleanType
        if base in ('floor', 'ceil'):
            zc = z0 if base == 'floor' else z1
            d = z1 - z0
            obb = adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(xf / 10, (y0 + y1) / 20, zc / 10),
                                                         adsk.core.Vector3D.create(k, 0, k), adsk.core.Vector3D.create(0, 1, 0),
                                                         d * math.sqrt(2) / 10, (y1 - y0) / 10, d * math.sqrt(2) / 10)
            g = tbm.createBox(obb)
            tbm.booleanOperation(g, bx(xf - d, xf, y0, y1, z0, z1), INTER)
        else:
            yc = y0 if base == 'wall-' else y1
            d = y1 - y0
            obb = adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(xf / 10, yc / 10, (z0 + z1) / 20),
                                                         adsk.core.Vector3D.create(k, k, 0), adsk.core.Vector3D.create(0, 0, 1),
                                                         d * math.sqrt(2) / 10, (z1 - z0) / 10, d * math.sqrt(2) / 10)
            g = tbm.createBox(obb)
            tbm.booleanOperation(g, bx(xf - d, xf, y0, y1, z0, z1), INTER)
        return g

    def column(y, z, r, xb, ribs=True):
        """Boss of radius r from the end wall up to xb. Near a wall / floor / ceiling it is tied to it by a rib as wide as
        the boss (tangent, so the boss blends straight into it); in a corner the corner is filled solid."""
        sy = -1 if y < 0 else 1
        body = cyl((xin, y, z), (xb, y, z), r)
        if not ribs:
            return body
        dw, dz_floor, dz_ceil = iw - abs(y), z - fz, (p['step_z'] - p['ceil']) - z
        if dw < 6:
            body = uni(body, bx(xin, xb, y, sy * (iw + 0.5), z - r, z + r))
        if min(dz_floor, dz_ceil) < 6:
            zw = (p['step_z'] - p['ceil'] + 0.5) if dz_ceil < dz_floor else fz - 0.5
            body = uni(body, bx(xin, xb, y - r, y + r, z, zw))
            if dw < 6:                                    # in a corner: fill it solid (no slot between the ribs)
                body = uni(body, bx(xin, xb, y, sy * (iw + 0.5), z, zw))
        return body

    ir = p['ins_d'] / 2 + p['ins_wall']
    bt = p['board_t']
    seat = x1 - bt                                        # board's back face
    bA, bB = p['bolts_board']                             # (6.45, 11.58), (22.45, 27.58)
    rC, rD = p['bolts_rim']                               # (-23, 27), (22, 5.5)
    pF, = p['pin_holes']                                  # (6.45, 27.58)
    # every boss is a plain column from the end wall (nothing sits in their way any more)
    cup = uni(cup, column(bA[0], bA[1], ir, seat))        # bolt A: free-standing cylinder
    cup = uni(cup, column(bB[0], bB[1], ir, seat))        # bolt B: top back corner
    cup = uni(cup, column(rC[0], rC[1], ir, x1))          # bolt C: top room-side corner
    cup = uni(cup, column(rD[0], rD[1], ir, x1))          # bolt D: bottom back corner
    cup = uni(cup, column(pF[0], pF[1], 3.0, seat, ribs=False))   # pin F: cylinder + the locating pin on top
    for y, z in p['pin_holes']:                           # locating pins through the board's spare holes
        cup = uni(cup, cyl((seat - 0.01, y, z), (x1 - 0.2, y, z), p['pin_d'] / 2))
    # the board pocket in the side wall: the board is wider than the cup's inside on the back side
    b0, b1, c0, c1 = p['board']
    cup = cut(cup, bx(seat - 0.3, x1 + 1, b0 - 0.3, b1 + 0.3, c0 - 0.3, c1 + 0.3))
    # N20 cradle under the can's end, shaped to the can
    cx0, cx1 = p['can'][1] + 1.0, p['can'][1] + 5.0
    ay, az = p['n20_axis']
    cy0, cy1 = ay - p['n20_w'] / 2 - 1.6, ay + p['n20_w'] / 2 + 1.6
    cr = uni(bx(cx0, cx1, cy0, cy1, fz - 0.5, az + 2.0), gusset(cx0, cy0, cy1, fz - 0.5, az + 2.0, 'floor'))
    cup = uni(cup, cut(cr, n20_section(bx, cyl, cut, uni, cx0 - 12, cx1 + 1, 0.15)))
    # RJ12 breakout: room side, above the motor. That is the one channel from the open face to the end wall that every
    # boss, rib and the rod tube stay out of, so the board (with its leads soldered) slides straight in on two grooved
    # rails until the jack sits flush in the end wall. A spring latch in the room-side rail snaps behind the board's back
    # edge, so pushing a plug in can't move it (release: press the latch toward the wall from the open face).
    gz0, gz1 = p['rj_z'] - 0.1, p['rj_z'] + 1.6 + 0.1
    ry0, ry1 = p['rj_y'] - p['rj_bw'] / 2, p['rj_y'] + p['rj_bw'] / 2       # -20.8 .. -1.4
    jz0 = p['rj_z'] + 1.6
    rj_back = p['rj_x1']
    # room-side rail: a block from the side wall to 1.2 mm under the board's edge, from the end wall to the latch
    blk = bx(xin, rj_back + 1.6, -iw - 0.5, ry0 + 1.2, p['rj_z'] - 2.5, gz1 + 1.8)
    blk = cut(blk, bx(xin - 1, x1 + 1, ry0 - 0.2, ry0 + 1.3, gz0, gz1))                # groove (open to the face)
    blk = cut(blk, bx(rj_back - 12.0, rj_back + 2.0, ry0 - 3.2, ry0 - 0.2, gz0 - 0.6, gz1 + 0.6))   # latch relief
    blk = cut(blk, bx(rj_back - 0.6, rj_back + 2.0, ry0 - 3.2, ry0 + 1.3, gz0 - 0.6, gz1 + 0.6))     # rail cut back at the hook
    cup = uni(cup, blk)
    hz0, hz1 = gz0 + 0.25, gz1 - 0.25           # latch 0.25 mm clear of the rail above and below: they print apart
    arm = bx(rj_back - 13.6, rj_back + 1.6, ry0 - 2.2, ry0 - 1.0, hz0, hz1)          # spring arm, anchored at -X
    hook = uni(bx(rj_back + 0.1, rj_back + 0.5, ry0 - 1.0, ry0 + 0.8, hz0, hz1),        # stop face behind the board
               bx(rj_back + 0.5, rj_back + 0.9, ry0 - 1.0, ry0 + 0.5, hz0, hz1),        # ramp (stepped)
               bx(rj_back + 0.9, rj_back + 1.3, ry0 - 1.0, ry0 + 0.0, hz0, hz1),
               bx(rj_back + 1.3, rj_back + 1.6, ry0 - 1.0, ry0 - 0.5, hz0, hz1))
    cup = uni(cup, arm, hook)
    # inner rail: hangs from the rod tube, along the board's other edge
    bar = bx(xin, rj_back + 1.6, ry1 - 1.2, ry1 + 1.6, p['rj_z'] - 2.5, p['rod_z'] - 4.0)
    bar = cut(bar, bx(xin - 1, x1 + 1, ry1 - 1.3, ry1 + 0.2, gz0, gz1))
    cup = uni(cup, bar)
    # front stop for the board's front edge, under the jack's overhang
    cup = uni(cup, bx(xin, p['rj_x0'], ry0 + 2.0, ry1 - 2.0, p['rj_z'] - 2.5, p['rj_z'] + 1.5))
    jy0, jy1 = p['rj_y'] - p['rj_jw'] / 2 - 0.15, p['rj_y'] + p['rj_jw'] / 2 + 0.15
    cup = cut(cup, bx(x0 - 1, p['in_x0'] + 0.01, jy0, jy1, jz0 - 0.15, jz0 + p['rj_jh'] + 0.15))   # jack window, flush
    # DRV8833: stands on a grooved floor rail, top edge in a rail standing up from the end wall; slides in from the open
    # face to a stop; the AS5600 board covers its +X end once fitted
    dg0, dg1 = p['drv_y'] - 0.15, p['drv_y'] + p['drv_t'] + 0.15
    za, zb = p['drv_z0'], p['drv_z0'] + p['drv_h']
    dx0 = p['drv_x1'] - p['drv_l']
    for rz0, rz1, cz0, cz1 in ((fz - 0.5, za + 1.5, za - 0.2, za + 3.0), (zb - 1.5, zb + 1.8, zb - 3.0, zb + 0.2)):
        rail = cut(bx(xin, x1 - 1.6, dg0 - 1.6, dg1 + 1.6, rz0, rz1), bx(dx0 - 0.2, x1 + 1, dg0, dg1, cz0, cz1))
        cup = uni(cup, rail)
    # rod tube (closed through the module; the rod goes in from outside and may stay sticking out)
    rr = p['rod'] * math.sqrt(2) / 2 + p['rod_clear']
    cup = uni(cup, cyl((x0, 0, p['rod_z']), (p['tube_x1'], 0, p['rod_z']), rr + p['tube_wall']))
    cup = cut(cup, cyl((x0 - 1, 0, p['rod_z']), (x1 + 1, 0, p['rod_z']), rr))
    # insert holes last (Ø4.0, 8 deep: the M3 x 25 bolts run 1.6 past the insert at the rim pair)
    for y, z in p['bolts_board']:
        cup = cut(cup, cyl((seat + 0.01, y, z), (seat - p['ins_hole'], y, z), p['ins_d'] / 2))
    for y, z in p['bolts_rim']:
        cup = cut(cup, cyl((x1 + 1, y, z), (x1 - p['ins_hole'], y, z), p['ins_d'] / 2))
    out['Module'] = [('Sensor module', cup)]

    # ---------------- parts inside
    parts = []
    board = bx(seat, x1, b0, b1, c0, c1)
    cy, cz = p['chip']
    for dy in (-1, 1):
        for dz in (-1, 1):
            hy, hz = cy + dy * p['hole_off'], cz + dz * p['hole_off']
            board = cut(board, cyl((seat - 1, hy, hz), (x1 + 1, hy, hz), p['board_hole'] / 2))
    parts.append(('AS5600 board', board))
    parts.append(('AS5600 chip', bx(x1, x1 + 1.5, cy - 2.5, cy + 2.5, cz - 2.0, cz + 2.0)))
    rb = bx(p['rj_x0'], p['rj_x1'], p['rj_y'] - p['rj_bw'] / 2, p['rj_y'] + p['rj_bw'] / 2, p['rj_z'], p['rj_z'] + 1.6)
    parts.append(('RJ12 board', rb))
    jack = bx(x0, x0 + p['rj_jl'], p['rj_y'] - p['rj_jw'] / 2, p['rj_y'] + p['rj_jw'] / 2, jz0, jz0 + p['rj_jh'])
    mzc = jz0 + p['rj_jh'] / 2 - 0.5
    jack = cut(jack, bx(x0 - 1, x0 + 13, p['rj_y'] - p['rj_mouth_w'] / 2, p['rj_y'] + p['rj_mouth_w'] / 2,
                        mzc - p['rj_mouth_h'] / 2, mzc + p['rj_mouth_h'] / 2))
    parts.append(('RJ12 jack', jack))
    parts.append(('RJ12 pins', bx(p['rj_x0'] + 1.0, p['rj_x0'] + 10.0, p['rj_y'] - 5, p['rj_y'] + 5, p['rj_z'] - 3.0, p['rj_z'])))
    dx1, dx0 = p['drv_x1'], p['drv_x1'] - p['drv_l']
    parts.append(('DRV8833', bx(dx0, dx1, p['drv_y'], p['drv_y'] + p['drv_t'], za, zb)))
    parts.append(('DRV8833 chip', bx((dx0 + dx1) / 2 - 2.5, (dx0 + dx1) / 2 + 2.5, p['drv_y'] + p['drv_t'],
                                     p['drv_y'] + p['drv_t'] + 1.0, za + 7, za + 11)))
    parts.append(('C 10uF', bx(dx0 + 4, dx0 + 7, p['drv_y'] + p['drv_t'], p['drv_y'] + p['drv_t'] + 2.0, za + 2.5, za + 5.5)))
    out['Inside'] = parts
    out['Screws'] = [('M3x25', uni(cone((9.3, y, z), 2.95, (9.3 - 1.45, y, z), 1.5), cyl((9.3 - 1.4, y, z), (9.3 - 25, y, z), 1.45)))
                     for y, z in p['bolts_board'] + p['bolts_rim']]
    plug = bx(x0 - 9.0, x0 + 12.5, p['rj_y'] - p['rj_mouth_w'] / 2 + 0.15, p['rj_y'] + p['rj_mouth_w'] / 2 - 0.15,
              mzc - p['rj_mouth_h'] / 2 + 0.15, mzc + p['rj_mouth_h'] / 2 - 0.15)
    cord = bx(x0 - 60, x0 - 9.0, p['rj_y'] - 3.3, p['rj_y'] + 3.3, mzc - 1.5, mzc + 1.5)
    out['Plug'] = [('RJ12 plug', plug), ('White cord', cord)]
    return out


def summary():
    return {
        'module': 'X %.2f..%.2f (%.1f mm beyond the lid face), same section as the tilter case, open toward the tilter' % (
            p['end_x'], p['lid_x'], p['lid_x'] - p['end_x']),
        'fasteners': '4 x M3 x 25 flat head from the main half back face (2 through the AS5600 board) into 4 inserts in the module',
        'jack': 'end wall at X %.2f, flush; centre Y %.1f, Z %.1f' % (p['end_x'], p['rj_y'], p['rj_z'] + 1.6 + p['rj_jh'] / 2 - 0.5),
        'rod tube': 'Ø%.1f bore through the module at (Y 0, Z %.0f)' % (2 * (p['rod'] * math.sqrt(2) / 2 + p['rod_clear']), p['rod_z']),
    }
