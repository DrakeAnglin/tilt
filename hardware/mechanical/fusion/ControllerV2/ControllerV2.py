"""ControllerV2: hole-accurate dev board + headrail case for one blind controller (ESP32-C6, 3 tilters).

Everything sits on the perfboard's real 2.54 mm grid: every pin is assigned a hole, the board is cut along hole rows,
and the checks run in plain Python (no Fusion) as well as inside Fusion:

  python3 hardware/mechanical/fusion/ControllerV2/ControllerV2.py      # checks + SVG hole map
  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v2.py --timeout 900   # Fusion model

Rules this layout follows (V1 broke them):
  * nothing under the perfboard except the breakouts that plug into it, so its underside is open for point-to-point
    wiring before the board goes into the case;
  * the RJ12 and USB-C breakouts hang UNDER the board ends on their own straight headers (pins up through the
    perfboard, soldered on top): no loose wires to the ports;
  * top-side joints get iron access in the build order (steps); module pins are soldered underneath.

Part sizes come from the listing photos / drawings (2026-10-28), see SOURCES. Coordinates (mm): X along the rail,
Y across (-Y = room side), Z up from the rail floor. Hole (i, m) is at X = X0 + 2.54 i, Y = Y0 + 2.54 m.
"""

import math
import os

SOURCES = {
    'ESP32-C6 SuperMini': '26 x 18 drawing in the listing; 10 pins a side (labels from the listing photo); row spacing '
                          'not readable: modeled 15.24 (6 holes), col 8 kept free for 17.78 (7 holes)',
    'DRV8833 (Suuoo)': '18.5 x 16 (listing); rows IN4 IN3 GND VCC IN2 IN1 / EEP OUT1 OUT2 OUT3 OUT4 ULT; rows 12.7 apart '
                       '(estimated from photo)',
    'RJ12 breakout (risingsaplings)': 'board 19.4 x 19.9, jack 13.5 W x 14.7 L overhanging the front edge 4.5, pin row '
                                      '1.3 and holes 7.0 from the back edge (quarter-coin photo, 2.54 pitch as scale); '
                                      'jack height 13.0 assumed',
    'USB-C breakout (Teansic)': '22.1 x 13.05 x 1.6 (listing); pins VBUS GND CC1 D- D+ CC2 along the back edge',
    'MCP73871 charger (Comimark)': '~19.6 x 18.3 scaled from its 2.54 header in the photos; pads only',
    '18650 pack (XINLANTECH)': '2.68 x 0.75 in = 68.1 x 19.05 (listing), XH lead from one end',
}

PITCH = 2.54
X0 = 19.22            # row 0; puts the end-A RJ12 pin row (row 2, X 24.30) where the jacks touch the end wall
Y0 = -1.00            # col 0: the strip's first column clears the battery

C = dict(
    rail_w=55.5, rail_h=36.5, rail_wall=2.0, lip_in=4.5, lip_h=3.0, rod_z=24.0, rod=4.0,
    half_w=23.0, wall=1.2, floor=1.2, lid=1.2, top=23.0, groove_hw=4.5, groove_wall=1.2, groove_top=20.2,
    hung_z0=2.7,            # hung breakouts' underside (jack pins trimmed to 1.5 below the board)
    plastic=2.5,            # header plastic
    pb_t=1.6,
    bat_d=19.05, bat_l=68.1, bat_x0=44.3,
    # RJ12 breakout
    rj_bw=19.4, rj_bd=19.9, rj_jw=13.5, rj_jl=14.7, rj_jh=13.0, rj_over=4.5, rj_row=1.3, rj_hole=7.0, rj_hole_side=2.1,
    rj_mouth_w=9.9, rj_mouth_h=8.6,
    # USB-C breakout
    usb_bw=22.1, usb_bd=13.05, usb_row=1.25, usb_trim=1.0,      # file 1 mm off its +Y end (clears RJ12 #3's board)
    rj3_recess=1.4,         # RJ12 #3's jack face behind end wall B (puts its pin row on the USB-C's grid)
)
C['hung_z1'] = C['hung_z0'] + 1.6
C['pb_z'] = C['hung_z1'] + C['plastic']
C['pb_top'] = C['pb_z'] + C['pb_t']
C['mod_z'] = C['pb_top'] + C['plastic']
C['bat_y'] = -(C['half_w'] - C['wall']) + 0.2 + C['bat_d'] / 2
C['bat_z'] = C['floor'] + 0.3 + C['bat_d'] / 2
C['bat_x1'] = C['bat_x0'] + C['bat_l']

ROW_USB = 41
E_IN = X0 + PITCH * ROW_USB + (C['usb_bd'] - C['usb_row'])      # inner face of end wall B (USB-C socket mouth)
LO = E_IN + C['wall']


def X(i):
    return X0 + PITCH * i


def Y(m):
    return Y0 + PITCH * m


BOARD = [(0, 9, -7, 8),       # ear A: full width (rows 0-9): RJ12 #1/#2 pins, RC filters, both DRV8833
         (10, 37, 0, 8),      # strip beside the battery: ESP32-C6, charger, divider, bulk cap, RJ12 #3 pins
         (38, 41, -7, 1)]     # ear B: room side + strip end, clear of RJ12 #3's jack: diodes, XH, solar, USB-C pins
HOLES = {(i, m) for i0, i1, m0, m1 in BOARD for i in range(i0, i1 + 1) for m in range(m0, m1 + 1)}


# ------------------------------------------------------------------ parts
class Part:
    """pins [(i, m, label)]; boxes [(name, x0, x1, y0, y1, z0, z1)]; cyls [(name, p1, p2, r)]; side = where its pins
    are soldered; step = build order."""

    def __init__(self, name, group, pins=(), boxes=(), cyls=(), side='under', step=4, note=''):
        self.name, self.group, self.pins, self.boxes, self.cyls = name, group, list(pins), list(boxes), list(cyls)
        self.side, self.step, self.note = side, step, note


def plastic_box(name, pins, z0, z1):
    xs, ys = [X(i) for i, m, _ in pins], [Y(m) for i, m, _ in pins]
    return (name, min(xs) - 1.27, max(xs) + 1.27, min(ys) - 1.27, max(ys) + 1.27, z0, z1)


def rj12(n, row, cols, end, recess=0.0):
    c = C
    pins = [(row, cols[0] + k, str(k + 1)) for k in range(6)]
    yc = (Y(cols[0]) + Y(cols[-1])) / 2
    s = -1 if end == 'A' else 1                               # toward the wall
    back = X(row) - s * c['rj_row']
    front = back + s * c['rj_bd']
    jface = front + s * c['rj_over']
    z0, z1 = c['hung_z0'], c['hung_z1']
    bx0, bx1 = sorted((back, front))
    jx0, jx1 = sorted((jface, jface - s * c['rj_jl']))
    hx = back + s * c['rj_hole']
    hy = c['rj_bw'] / 2 - c['rj_hole_side']
    boxes = [('RJ12 %d board' % n, bx0, bx1, yc - c['rj_bw'] / 2, yc + c['rj_bw'] / 2, z0, z1),
             ('RJ12 %d jack' % n, jx0, jx1, yc - c['rj_jw'] / 2, yc + c['rj_jw'] / 2, z1, z1 + c['rj_jh']),
             ('RJ12 %d jack pins' % n, min(front, front - s * 9), max(front, front - s * 9), yc - 5, yc + 5, c['floor'] + 0.05, z0),
             plastic_box('RJ12 %d header' % n, pins, z1, c['pb_z'])]
    return Part('RJ12 #%d' % n, 'Breakouts', pins, boxes, side='top', step=1), dict(
        n=n, yc=yc, jface=jface, s=s, end=end, holes=[(hx, yc - hy), (hx, yc + hy)], board=(bx0, bx1))


def usb_c(row, cols):
    c = C
    labels = ['VBUS', 'GND', 'CC1', 'D-', 'D+', 'CC2']
    pins = [(row, cols[0] + k, labels[k]) for k in range(6)]
    yc = (Y(cols[0]) + Y(cols[-1])) / 2
    back = X(row) - c['usb_row']
    front = back + c['usb_bd']
    y0, y1 = yc - c['usb_bw'] / 2, yc + c['usb_bw'] / 2 - c['usb_trim']
    z0, z1 = c['hung_z0'], c['hung_z1']
    boxes = [('USB-C board', back, front, y0, y1, z0, z1),
             ('USB-C socket', front - 7.35 + 0.2, front + 0.0, yc - 4.47, yc + 4.47, z1, z1 + 3.26),
             plastic_box('USB-C header', pins, z1, c['pb_z'])]
    return Part('USB-C', 'Breakouts', pins, boxes, side='top', step=1,
                note='file %.1f mm off its +Y end first' % c['usb_trim']), dict(yc=yc, front=front, y=(y0, y1), back=back)


def module(name, rows, l, w, t, extra=()):
    """rows: [([i...], [m...], [labels])]. Straight headers: plastic on top of the perfboard, soldered underneath."""
    pins, boxes = [], []
    for i_list, m_list, labs in rows:
        rp = [(i, m) for i in i_list for m in m_list]
        pins += [(i, m, lab) for (i, m), lab in zip(rp, labs)]
        boxes.append(plastic_box(name + ' header', [(i, m, '') for i, m in rp], C['pb_top'], C['mod_z']))
    xs, ys = [X(i) for i, m, _ in pins], [Y(m) for i, m, _ in pins]
    xc, yc = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    z0 = C['mod_z']
    boxes.insert(0, (name + ' PCB', xc - l / 2, xc + l / 2, yc - w / 2, yc + w / 2, z0, z0 + t))
    boxes += [(name + ' ' + nm, xc + a, xc + b, yc + d, yc + e, z0 + t + f, z0 + t + g) for nm, a, b, d, e, f, g in extra]
    return Part(name, 'Modules', pins, boxes, side='under', step=3)


def lying(name, i0, m0, i1, m1, d, length, step=4, side='under'):
    """Axial part lying flat between two holes on the same row or column."""
    t = C['pb_top']
    xa, ya, xb, yb = X(i0), Y(m0), X(i1), Y(m1)
    xm, ym = (xa + xb) / 2, (ya + yb) / 2
    ux, uy = (1, 0) if i0 != i1 else (0, 1)
    p1 = (xm - ux * length / 2, ym - uy * length / 2, t + d / 2)
    p2 = (xm + ux * length / 2, ym + uy * length / 2, t + d / 2)
    return Part(name, 'Passives', [(i0, m0, ''), (i1, m1, '')], cyls=[(name, p1, p2, d / 2)], step=step, side=side)


def upright(name, i, m, d=2.7, h=8.0):
    t = C['pb_top']
    UPRIGHT.add(name)
    return Part(name, 'Passives', [(i, m, ''), (i, m + 1, '')], cyls=[(name, (X(i), Y(m), t), (X(i), Y(m), t + h), d / 2)])


def disc(name, i, m0, m1, side='under'):
    t = C['pb_top']
    return Part(name, 'Passives', [(i, m0, ''), (i, m1, '')], side=side,
                boxes=[(name, X(i) - 1.25, X(i) + 1.25, Y(m0) - 0.8, Y(m1) + 0.8, t, t + 5.0)])


def layout():
    parts = []
    rj1, g1 = rj12(1, 2, list(range(-6, 0)), 'A')
    rj2, g2 = rj12(2, 2, list(range(2, 8)), 'A')
    rj3, g3 = rj12(3, ROW_USB - 5, list(range(2, 8)), 'B', recess=C['rj3_recess'])
    usb, gu = usb_c(ROW_USB, list(range(-6, 0)))
    parts += [rj1, rj2, rj3, usb]
    # DRV8833: OUT row toward the jacks (row 4), IN row toward the ESP (row 9); 6 pins along Y
    for n, cols in ((1, list(range(-6, 0))), (2, list(range(2, 8)))):
        parts.append(module('DRV8833 %d' % n,
                            [([4], cols, ['EEP', 'OUT1', 'OUT2', 'OUT3', 'OUT4', 'ULT']),
                             ([9], cols, ['IN4', 'IN3', 'GND', 'VCC', 'IN2', 'IN1'])],
                            16.0, 18.5, 1.6, extra=[('chip', -2, 2, -2.5, 2.5, 0, 1.0)]))
    # ESP32-C6: 10 pins a side along X (rows 11-20), USB-C toward +X; +Y row = 7..0 RX TX, -Y row = 8 9 14 15 18 19 20 3V3 GND 5V
    rows = list(range(11, 21))
    parts.append(module('ESP32-C6',
                        [(rows, [7], ['7', '6', '5', '4', '3', '2', '1', '0', 'RX17', 'TX16']),
                         (rows, [1], ['8', '9', '14', '15', '18', '19', '20', '3V3', 'GND', '5V'])],
                        26.0, 18.0, 1.0, extra=[('USB-C', 13.0 - 7.35 + 0.8, 13.0 + 0.8, -4.47, 4.47, 0, 3.26),
                                                ('chip', -6, -1, -2.5, 2.5, 0, 0.9)]))
    # charger: on 1 mm foam tape, pads wired to the holes beside it (col 8, row 30)
    t = C['pb_top']
    parts.append(Part('MCP73871', 'Modules', [], boxes=[
        ('MCP73871 PCB', 74.0, 93.6, -0.4, 17.9, t + 1.0, t + 2.6),
        ('MCP73871 parts', 80.0, 88.0, 3.0, 12.0, t + 2.6, t + 3.5),
        ('MCP73871 tape', 74.5, 93.1, 0.0, 17.5, t, t + 1.0)], side='top', step=2,
        note='foam tape; PWR/BATT/LOAD pads -> col 8 / row 30 holes; NTC replaces the THERM resistor'))
    # RC filters beside each jack. Over the hanging boards there is only 2.5 mm under the perfboard, so these are
    # soldered on TOP (double-sided board), after the breakouts (step 4)
    parts += [lying('R ADC1', 0, -6, 0, -3, 2.3, 6.3, side='top'), disc('C ADC1', 1, -6, -4, side='top'),
              lying('R ADC2', 0, 2, 0, 5, 2.3, 6.3, side='top'), disc('C ADC2', 1, 2, 4, side='top'),
              lying('R ADC3', 37, 2, 37, 5, 2.3, 6.3, side='top'), disc('C ADC3', 37, 6, 8, side='top')]
    # back column (col 8) beside the charger: D3 (LOAD -> ESP 5V), battery divider + filter
    parts += [lying('D3 1N5819', 21, 8, 25, 8, 2.7, 5.2), lying('R div top', 26, 8, 29, 8, 2.3, 6.3),
              lying('R div bot', 30, 8, 33, 8, 2.3, 6.3), disc('C div', 34, 8, 8)]
    parts[-1].pins = [(34, 8, ''), (35, 8, '')]
    parts[-1].boxes = [('C div', X(34) - 0.8, X(35) + 0.8, Y(8) - 1.25, Y(8) + 1.25, t, t + 5.0)]
    # charger's bulk electrolytic, radial, lying along Y beside the charger
    parts.append(Part('C bulk', 'Passives', [(31, 0, '+'), (32, 0, '-')],
                      cyls=[('C bulk', ((X(31) + X(32)) / 2, 0.6, t + 4.0), ((X(31) + X(32)) / 2, 13.6, t + 4.0), 4.0)]))
    # ear B: row 38 (cols -7..-1) stays clear for the battery lead's bend; D1, D2, zener upright, staggered
    parts += [upright('D1 1N5819 USB', 39, -7), upright('D2 1N5819 solar', 39, -4), upright('Z 6.2V', 40, -6)]
    parts.append(Part('Battery pins', 'Passives', [(38, 0, 'B+'), (39, 0, 'B-')],
                      boxes=[('Battery pins', X(38) - 1.27, X(39) + 1.27, Y(0) - 1.27, Y(0) + 1.27, t, t + 2.5),
                             ('XH plug', X(38) - 2.45, X(39) + 2.45, Y(0) - 2.45, Y(0) + 2.45, t + 2.5, t + 8.5)],
                      note='2 pins of straight header; the XH plug of the cell pushes on (2.5 vs 2.54 pitch)'))
    parts.append(Part('Solar pads', 'Passives', [(40, -3, 'S+'), (40, -2, 'S-')], step=5))
    return parts, dict(rj=[g1, g2, g3], usb=gu)


# ------------------------------------------------------------------ checks (plain Python)
def body_boxes(parts):
    out = []
    for p in parts:
        out += [(p.name, b) for b in p.boxes]
        for nm, p1, p2, r in p.cyls:
            lo = [min(p1[k], p2[k]) - (r if abs(p1[k] - p2[k]) < 1e-9 else 0) for k in range(3)]
            hi = [max(p1[k], p2[k]) + (r if abs(p1[k] - p2[k]) < 1e-9 else 0) for k in range(3)]
            out.append((p.name, (nm, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])))
    return out


def overlap(a, b):
    ra, rb = upright_r(a), upright_r(b)
    if ra and rb:                     # two upright cylinders: compare as circles
        d = math.hypot((a[1] + a[2] - b[1] - b[2]) / 2, (a[3] + a[4] - b[3] - b[4]) / 2)
        if d >= ra + rb:
            return False
    return all(max(a[1 + 2 * k], b[1 + 2 * k]) < min(a[2 + 2 * k], b[2 + 2 * k]) - 1e-6 for k in range(3))


UPRIGHT = set()


def upright_r(b):
    return (b[2] - b[1]) / 2 if b[0] in UPRIGHT else 0


def battery_hit(b):
    c = C
    if b[2] <= c['bat_x0'] or b[1] >= c['bat_x1']:
        return False
    dy = max(b[3] - c['bat_y'], 0, c['bat_y'] - b[4])
    dz = max(b[5] - c['bat_z'], 0, c['bat_z'] - b[6])
    return math.hypot(dy, dz) < c['bat_d'] / 2


def checks(parts):
    rep, used = [], {}
    for p in parts:
        for i, m, lab in p.pins:
            if (i, m) not in HOLES:
                rep.append('PIN OFF BOARD: %s %s (%d, %d)' % (p.name, lab, i, m))
            if (i, m) in used:
                rep.append('HOLE SHARED: (%d, %d) %s / %s' % (i, m, used[(i, m)], p.name))
            used[(i, m)] = p.name
    bb = body_boxes(parts)
    pb = [('Perfboard', ('Perfboard', X(i0) - 1.27, X(i1) + 1.27, Y(m0) - 1.27, Y(m1) + 1.27, C['pb_z'], C['pb_top']))
          for i0, i1, m0, m1 in BOARD]
    allb = bb + pb
    for a in range(len(allb)):
        for b in range(a + 1, len(allb)):
            if allb[a][0] != allb[b][0] and overlap(allb[a][1], allb[b][1]):
                rep.append('OVERLAP: %s / %s' % (allb[a][1][0], allb[b][1][0]))
    for nm, b in allb:
        if battery_hit(b):
            rep.append('OVERLAP: %s / 18650' % b[0])
    iw = C['half_w'] - C['wall']
    for nm, b in allb:
        if b[3] < -iw - 1e-6 or b[4] > iw + 1e-6 or b[1] < C['wall'] - 1e-6 or b[2] > E_IN + 0.3:
            if 'jack pins' not in b[0]:
                rep.append('OUTSIDE CASE: %s' % b[0])
    # top-side joints: plan distance from the joint to the nearest other body that stands above the board
    acc = []
    for p in parts:
        if p.side != 'top':
            continue
        for i, m, lab in p.pins:
            best, who = 99.0, ''
            for nm, b in bb:
                if nm == p.name or b[6] <= C['pb_top'] + 0.01:
                    continue
                d = math.hypot(max(b[1] - X(i), 0, X(i) - b[2]), max(b[3] - Y(m), 0, Y(m) - b[4]))
                if d < best:
                    best, who = d, b[0]
            acc.append((best, p.name, lab, i, m, who))
    acc.sort()
    # module pins soldered underneath: what is below each joint
    under = []
    for p in parts:
        if p.side != 'under':
            continue
        for i, m, lab in p.pins:
            for nm, b in bb:
                if nm != p.name and b[6] <= C['pb_z'] + 0.01 and b[1] - 1 < X(i) < b[2] + 1 and b[3] - 1 < Y(m) < b[4] + 1:
                    under.append('%s %s (%d,%d): %.1f mm above %s' % (p.name, lab, i, m, C['pb_z'] - b[6], b[0]))
    return rep, acc, under, used


def report(parts=None):
    parts = parts or layout()[0]
    rep, acc, under, used = checks(parts)
    lines = ['Case outer %.1f x %.1f x %.1f mm; perfboard %d holes cut, %d used, %d free' % (
        LO, 2 * C['half_w'], C['top'], len(HOLES), len(used), len(HOLES) - len(used)),
        'Heights: hung boards %.1f-%.1f, perfboard %.1f-%.1f, modules from %.1f; battery %.1f-%.1f' % (
            C['hung_z0'], C['hung_z1'], C['pb_z'], C['pb_top'], C['mod_z'], C['bat_z'] - C['bat_d'] / 2, C['bat_z'] + C['bat_d'] / 2)]
    lines += rep or ['Pins all on holes, no hole shared, no body overlaps, everything inside the case']
    lines.append('Tightest top-side joints (plan distance to the nearest body standing on the board):')
    lines += ['  %.2f mm  %s pin %s (%d,%d)  <- %s' % a for a in acc[:8]]
    lines.append('Module joints with something under them: %d' % len(under))
    lines += ['  ' + u for u in under[:10]]
    return lines, used


# ------------------------------------------------------------------ SVG hole map
def svg_map(parts, used, path):
    s = 9.0
    W, H = LO * s + 90, 2 * C['half_w'] * s + 150
    px = lambda x: 50 + x * s
    py = lambda y: 70 + (C['half_w'] - y) * s
    iw = C['half_w'] - C['wall']
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica,Arial">' % (W, H),
         '<rect width="100%" height="100%" fill="#fff"/>',
         '<text x="50" y="26" font-size="16" font-weight="bold">ControllerV2 dev board, top view (holes 2.54 mm)</text>',
         '<text x="50" y="46" font-size="11">End A left, end B right. Back wall (+Y) top, room side / battery bottom. '
         'Row numbers on top, column numbers left. Red = pin hole. Dashed = hanging under the board.</text>',
         '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#888" stroke-dasharray="6,4"/>' % (
             px(C['wall']), py(iw), (E_IN - C['wall']) * s, 2 * iw * s),
         '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="9" fill="#dfe4f7" stroke="#5566aa"/>' % (
             px(C['bat_x0']), py(C['bat_y'] + C['bat_d'] / 2), C['bat_l'] * s, C['bat_d'] * s),
         '<text x="%.1f" y="%.1f" font-size="13" fill="#334">18650 pack 68.1 x 19.05</text>' % (px(C['bat_x0']) + 12, py(C['bat_y']) + 4)]
    for i0, i1, m0, m1 in BOARD:
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#e9f4e1" stroke="#3a7a2a" stroke-width="2"/>' % (
            px(X(i0) - 1.27), py(Y(m1) + 1.27), (X(i1) - X(i0) + PITCH) * s, (Y(m1) - Y(m0) + PITCH) * s))
    col = {'Breakouts': '#222', 'Modules': '#1f6fb5', 'Passives': '#b5651d'}
    for p in parts:
        for b in p.boxes:
            if 'header' in b[0] or 'jack pins' in b[0] or 'tape' in b[0]:
                continue
            dash = ' stroke-dasharray="4,3"' if b[6] <= C['pb_z'] + 0.01 or p.group == 'Breakouts' else ''
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="%s" stroke-width="1.2"%s/>' % (
                px(b[1]), py(b[4]), (b[2] - b[1]) * s, (b[4] - b[3]) * s, col[p.group], dash))
        for nm, p1, p2, r in p.cyls:
            x0 = min(p1[0], p2[0]) - (r if abs(p1[0] - p2[0]) < 1e-9 else 0)
            x1 = max(p1[0], p2[0]) + (r if abs(p1[0] - p2[0]) < 1e-9 else 0)
            y0 = min(p1[1], p2[1]) - (r if abs(p1[1] - p2[1]) < 1e-9 else 0)
            y1 = max(p1[1], p2[1]) + (r if abs(p1[1] - p2[1]) < 1e-9 else 0)
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="4" fill="none" stroke="%s" stroke-width="1.2"/>' % (
                px(x0), py(y1), (x1 - x0) * s, (y1 - y0) * s, col[p.group]))
    for i, m in sorted(HOLES):
        o.append('<circle cx="%.1f" cy="%.1f" r="3.3" fill="%s" stroke="#555" stroke-width="0.7"/>' % (
            px(X(i)), py(Y(m)), '#c0392b' if (i, m) in used else '#fff'))
    for p in parts:
        for i, m, lab in p.pins:
            if lab:
                o.append('<text x="%.1f" y="%.1f" font-size="7" fill="#000">%s</text>' % (px(X(i)) + 3.6, py(Y(m)) - 3.6, lab))
    for p in parts:
        if p.boxes:
            b = p.boxes[0]
            o.append('<text x="%.1f" y="%.1f" font-size="10" font-weight="bold" fill="%s">%s</text>' % (
                px(b[1]) + 3, py(b[4]) + 12, col[p.group], p.name))
        elif p.cyls:
            nm, p1, p2, r = p.cyls[0]
            o.append('<text x="%.1f" y="%.1f" font-size="8" fill="%s">%s</text>' % (
                px(min(p1[0], p2[0])) - 4, py(max(p1[1], p2[1]) + r) - 3, col[p.group], p.name))
        elif p.pins:
            i, m, _ = p.pins[0]
            o.append('<text x="%.1f" y="%.1f" font-size="8" fill="%s">%s</text>' % (px(X(i)) - 6, py(Y(m)) + 15, col[p.group], p.name))
    for i in range(0, 42):
        if i % 5 == 0:
            o.append('<text x="%.1f" y="%.1f" font-size="10" fill="#666">%d</text>' % (px(X(i)) - 3, 62, i))
    for m in range(-7, 9):
        o.append('<text x="%.1f" y="%.1f" font-size="10" fill="#666">%d</text>' % (14, py(Y(m)) + 3, m))
    o.append('</svg>')
    with open(path, 'w') as f:
        f.write('\n'.join(o))


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    parts, geo = layout()
    lines, used = report(parts)
    print('\n'.join(lines))
    out = os.path.abspath(os.path.join(here, '../../../../docs/renders/ctrl-v2-holemap.svg'))
    svg_map(parts, used, out)
    print('SVG:', out)
