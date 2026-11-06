"""ControllerV3: controller box + hole-accurate dev board, after the drivers moved to the tilters.

One box per headrail-controller: ESP32-C6 SuperMini, MCP73871 charger, 18650, three RJ12 ports (all on end A), USB-C
charge-only port and the solar lead (end B). The box has the tilter's width and rounded long edges with a flat top just
under the rail lips, and slides into the rail from its end like the tilter. It sits under the tilt rod: the rod lies in
a groove along the lid's middle (0.97 mm under the rod's sweep), nothing to thread.

  python3 hardware/mechanical/fusion/ControllerV3/ControllerV3.py   # hole map SVG + wiring table, no Fusion needed
  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v3.py --timeout 1200

Assembly
  1. Trim each RJ12 breakout to 15 mm wide (cut off the two mounting-hole ears) and its jack pins to 0.4 mm under
     the board. Solder 6 leads to its header holes.
  2. RJ12 boards into the tray: tilt the board (back up), put the jack's nose into its window in end wall A, lower
     it: the front edge sits against the ledge step, the back edge drops behind the 1 mm lip. The lid holds them down.
  3. Dev board (modules + passives, wired and bench-tested) onto its posts; the USB-C breakout hangs under its end with
     the socket in end wall B. Solar lead through its hole in end wall B.
  4. 18650 into its saddles, its XH plug onto the two battery pins.
  5. Lid on: 3 x M3 x 8 flat head into heat-set inserts in the end-wall bosses.

RJ12 (pin 1 -> pin 1 cords): 1 VBAT, 2 IN1, 3 GND, 4 ANGLE, 5 EN, 6 IN2 (the DRV8833 is in the tilter's sensor module).

Coordinates (mm): X along the rail from end A's outer face, Y across (-Y room side), Z up from the rail floor.
"""

import math
import os

C = dict(
    half_w=27.7, floor_z=0.2, top=33.3, wall=1.8, floor=1.8, lid=1.8, end_t=2.0, edge_r=1.0,
    rail_w=55.5, rail_h=36.5, rail_wall=2.0, lip_in=4.5, lip_h=3.0,
    rod_z=24.0, rod=4.0,
    # the box sits UNDER the tilt rod: a groove along the lid's middle takes it (rod sweeps down to Z 21.17)
    groove_hw=4.5, groove_floor=20.2, groove_wall=1.2,
    # RJ12 breakouts, trimmed to 15 wide (jack 13.5 W x 14.7 L x 13 H, overhangs the board's front edge by 4.5)
    rj_w=15.0, rj_d=19.9, rj_t=1.6, rj_jw=13.5, rj_jl=14.7, rj_jh=13.0, rj_over=4.5, rj_z=2.6, rj_y=(-17.0, 0.0, 17.0),
    rj_mouth_w=9.9, rj_mouth_h=8.6,
    # 18650 pack (XINLANTECH, 68.1 x 19.05) along the room-side wall
    bat_d=19.05, bat_l=68.1, bat_x0=27.0,
    # perfboard on posts; modules on straight headers; USB-C breakout hung under its end
    pb_z=8.0, pb_t=1.6, plastic=2.5,
    usb_bw=22.1, usb_bd=13.05, usb_row=1.25,
    # lid screws: M3 x 8 flat head into inserts (Ø4.0 x 6.7) in bosses on the end walls
    ins_d=4.0, ins_depth=6.7, ins_wall=1.3,
)
c = C
C['iw'] = c['half_w'] - c['wall']
C['fz'] = c['floor_z'] + c['floor']
C['zl'] = c['top'] - c['lid']                         # lid underside / tray rim
C['pb_top'] = c['pb_z'] + c['pb_t']
C['mod_z'] = C['pb_top'] + c['plastic']
C['bat_y'] = -C['iw'] + 0.2 + c['bat_d'] / 2
C['bat_zc'] = C['fz'] + 0.3 + c['bat_d'] / 2
C['sweep_z'] = c['rod_z'] - c['rod'] * math.sqrt(2) / 2           # lowest point of the rod's corners
C['ch_hw'] = c['groove_hw'] + c['groove_wall']                     # the groove channel's outer half width
C['ch_z0'] = c['groove_floor'] - 1.2                               # its underside

PITCH = 2.54
PX0, PY0 = 28.5, -4.0
NI, NM = 25, 12                                       # perfboard holes: i 0..24 along X, m 0..11 across
HOLES = {(i, m) for i in range(NI) for m in range(NM)}


def X(i):
    return PX0 + PITCH * i


def Y(m):
    return PY0 + PITCH * m


PB = (X(0) - 1.27, X(NI - 1) + 1.27, Y(0) - 1.27, Y(NM - 1) + 1.27)
USB_ROW = 23                                           # USB-C breakout's pin row (i)
C['in_b'] = X(USB_ROW) - c['usb_row'] + c['usb_bd']   # end wall B inner face = USB-C socket mouth
C['L'] = C['in_b'] + c['end_t']
C['in_a'] = c['end_t']
C['rj_x0'] = c['rj_over']                              # RJ12 boards' front edge (jack face flush with end A)
C['rj_x1'] = C['rj_x0'] + c['rj_d']
LID_SCREWS = ((5.0, -12.0), (5.0, 12.0), (C['in_b'] - 3.0, 12.0))


class Part:
    def __init__(self, name, pins=(), boxes=(), cyls=(), note=''):
        self.name, self.pins, self.boxes, self.cyls, self.note = name, list(pins), list(boxes), list(cyls), note


def layout():
    """Dev-board parts with their holes. ESP32-C6 pin order from the listing photo (USB-C at the +X end):
    +Y row 7 6 5 4 3 2 1 0 RX TX, -Y row 8 9 14 15 18 19 20 3V3 GND 5V. Check against the board before soldering."""
    t = C['pb_top']
    parts = []
    rows = list(range(1, 11))
    esp_pins = [(i, 8, lab) for i, lab in zip(rows, ['7', '6', '5', '4', '3', '2', '1', '0', 'RX17', 'TX16'])] + \
               [(i, 2, lab) for i, lab in zip(rows, ['8', '9', '14', '15', '18', '19', '20', '3V3', 'GND', '5V'])]
    xc, yc = (X(1) + X(10)) / 2, (Y(2) + Y(8)) / 2
    z0 = C['mod_z']
    parts.append(Part('ESP32-C6', esp_pins, [
        ('ESP32-C6 PCB', xc - 13, xc + 13, yc - 9, yc + 9, z0, z0 + 1.0),
        ('ESP32-C6 USB-C', xc + 13 - 7.35 + 0.8, xc + 13 + 0.8, yc - 4.47, yc + 4.47, z0 + 1.0, z0 + 4.26),
        ('ESP32-C6 headers', X(1) - 1.27, X(10) + 1.27, Y(2) - 1.27, Y(2) + 1.27, t, z0),
        ('ESP32-C6 headers 2', X(1) - 1.27, X(10) + 1.27, Y(8) - 1.27, Y(8) + 1.27, t, z0)]))
    # charger on 1 mm foam tape, pads wired to the holes beside it
    parts.append(Part('MCP73871', [], [('MCP73871 PCB', X(12), X(12) + 19.6, Y(1), Y(1) + 18.3, t + 1.0, t + 2.6),
                                       ('MCP73871 parts', X(12) + 6, X(12) + 14, Y(1) + 4, Y(1) + 13, t + 2.6, t + 3.5),
                                       ('MCP73871 tape', X(12) + 0.5, X(12) + 19.1, Y(1) + 0.5, Y(1) + 17.8, t, t + 1.0)],
                      note='PWR, BATT, LOAD, THERM pads -> wire to the holes beside it'))

    def lying(name, i0, m0, i1, m1, d=2.3, ln=6.3):
        xa, ya, xb, yb = X(i0), Y(m0), X(i1), Y(m1)
        ux, uy = (1, 0) if m0 == m1 else (0, 1)
        xm, ym = (xa + xb) / 2, (ya + yb) / 2
        return Part(name, [(i0, m0, ''), (i1, m1, '')],
                    cyls=[(name, (xm - ux * ln / 2, ym - uy * ln / 2, t + d / 2), (xm + ux * ln / 2, ym + uy * ln / 2, t + d / 2), d / 2)])

    def disc(name, i0, i1, m):
        return Part(name, [(i0, m, ''), (i1, m, '')], [(name, X(i0) - 0.8, X(i1) + 0.8, Y(m) - 1.25, Y(m) + 1.25, t, t + 5.0)])

    # RC filters on the three angle lines (1 k + 100 n), along the +Y edge next to the ESP's ADC pins
    for k in range(3):
        parts += [lying('R ADC%d' % (k + 1), 4 * k, 11, 4 * k + 3, 11), disc('C ADC%d' % (k + 1), 4 * k + 1, 4 * k + 2, 10)]
    # battery divider (1 M / 1 M) + 100 n, charger STAT pull-up (10 k)
    parts += [lying('R div top', 0, 0, 3, 0), lying('R div bot', 4, 0, 7, 0), disc('C div', 18, 19, 0),
              lying('R stat', 14, 0, 17, 0)]
    # D3: charger LOAD -> ESP 5V; D1 (USB) and D2 (solar) into the charger's PWR; 6.2 V zener across PWR
    parts += [lying('D3 1N5819', 8, 0, 11, 0, 2.7, 5.2)]
    parts += [lying('D1 1N5819 USB', 21, 0, 21, 3, 2.7, 5.2), lying('D2 1N5819 solar', 24, 4, 24, 7, 2.7, 5.2)]
    parts += [lying('Z 6.2V', 21, 5, 21, 8, 2.7, 5.2)]
    # bulk electrolytic (charger kit's) on LOAD, 10 u ceramic at the ESP's 5V pin
    parts.append(Part('C bulk', [(20, 10, '+'), (21, 10, '-')],                       # 8 x 13 radial, standing
                      cyls=[('C bulk', ((X(20) + X(21)) / 2, Y(10), t), ((X(20) + X(21)) / 2, Y(10), t + 13.0), 4.0)]))
    parts.append(disc('C 10u', 12, 13, 0))
    # battery (XH plug pushes onto 2 header pins), solar pigtail pads
    parts.append(Part('Battery pins', [(23, 0, 'B+'), (24, 0, 'B-')],
                      [('Battery pins', X(23) - 1.27, X(24) + 1.27, Y(0) - 1.27, Y(0) + 1.27, t, t + 2.5),
                       ('XH plug', X(23) - 2.45, X(24) + 2.45, Y(0) - 2.45, Y(0) + 2.45, t + 2.5, t + 8.5)]))
    parts.append(Part('Solar pads', [(23, 2, 'S+'), (24, 2, 'S-')]))
    # USB-C breakout hung under the board's end on its own header (VBUS GND CC1 D- D+ CC2 along its back edge)
    hz1 = C['pb_z'] - c['plastic']
    hz0 = hz1 - 1.6
    upins = [(USB_ROW, 4 + k, lab) for k, lab in enumerate(['VBUS', 'GND', 'CC1', 'D-', 'D+', 'CC2'])]
    uy = (Y(4) + Y(9)) / 2
    back = X(USB_ROW) - c['usb_row']
    parts.append(Part('USB-C breakout', upins, [
        ('USB-C board', back, back + c['usb_bd'], uy - c['usb_bw'] / 2, uy + c['usb_bw'] / 2, hz0, hz1),
        ('USB-C socket', back + c['usb_bd'] - 7.35, back + c['usb_bd'], uy - 4.47, uy + 4.47, hz1, hz1 + 3.26),
        ('USB-C header', X(USB_ROW) - 1.27, X(USB_ROW) + 1.27, Y(4) - 1.27, Y(9) + 1.27, hz1, C['pb_z'])],
        note='only VBUS and GND are used (charge-only port)'))
    return parts


# ------------------------------------------------------------------ wiring (dev board), the reference for soldering
PORTS = [  # RJ12 pin -> net, per port: (IN1, IN2, EN, ADC)
    ('Port 1 (room side)', '18', '19', '4', '0'),
    ('Port 2 (middle)', '20', '14', '5', '1'),
    ('Port 3 (back side)', 'TX16', 'RX17', '6', '2'),
]


def wiring_md():
    o = ['| From | To | Note |', '|---|---|---|']
    for name, i1, i2, en, adc in PORTS:
        o += ['| %s pin 1 VBAT | charger LOAD | motor supply, ~250 mA per move |' % name,
              '| %s pin 2 IN1 | ESP GPIO %s | PWM |' % (name, i1),
              '| %s pin 3 GND | GND | |' % name,
              '| %s pin 4 ANGLE | R ADC (1 k) -> ESP GPIO %s, C ADC 100 n to GND | AS5600 OUT |' % (name, adc),
              '| %s pin 5 EN | ESP GPIO %s | powers the AS5600 and wakes the DRV8833 |' % (name, en),
              '| %s pin 6 IN2 | ESP GPIO %s | PWM |' % (name, i2)]
    o += ['| USB-C VBUS | D1 (band to charger) -> charger PWR | charge-only port |',
          '| Solar + (ZH pigtail) | D2 (band to charger) -> charger PWR | |',
          '| 6.2 V zener | across charger PWR / GND (band to PWR) | solar over-voltage clamp |',
          '| USB-C GND, solar -, charger GND | GND | |',
          '| Battery pins B+ / B- | charger BATT + / - | cell\'s XH plug pushes on |',
          '| 10 k NTC (taped to the cell) | charger THERM (replaces its fixed resistor) | stops charging when hot |',
          '| Charger LOAD | D3 (band to ESP) -> ESP 5V; C bulk + to LOAD | |',
          '| Charger LOAD | R div top 1 M -> ESP GPIO 3 -> R div bot 1 M -> GND; C div 100 n GPIO 3 to GND | battery voltage |',
          '| Charger STAT | ESP GPIO 7, R stat 10 k to 3V3 | charging / charged |',
          '| C 10 u | ESP 5V to GND | |']
    return '\n'.join(o)


# ------------------------------------------------------------------ SVG hole map
def svg_map(parts, path):
    s = 9.0
    W, H = (PB[1] - PB[0]) * s + 120, (PB[3] - PB[2]) * s + 120
    px = lambda x: 60 + (x - PB[0]) * s
    py = lambda y: 70 + (PB[3] - y) * s
    used = {(i, m) for p in parts for i, m, _ in p.pins}
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica,Arial">' % (W, H),
         '<rect width="100%" height="100%" fill="#fff"/>',
         '<text x="60" y="26" font-size="16" font-weight="bold">ControllerV3 dev board, top view (2.54 mm holes)</text>',
         '<text x="60" y="46" font-size="11">End A (ports) left, end B (USB-C) right; back wall (+Y) at the top. '
         'Red = pin hole. Rows (i) along the top, columns (m) on the left.</text>',
         '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#e9f4e1" stroke="#3a7a2a" stroke-width="2"/>' % (
             px(PB[0]), py(PB[3]), (PB[1] - PB[0]) * s, (PB[3] - PB[2]) * s)]
    for p in parts:
        for b in p.boxes:
            if 'header' in b[0] or 'tape' in b[0]:
                continue
            dash = ' stroke-dasharray="4,3"' if b[6] <= C['pb_z'] + 0.01 else ''
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#1f6fb5" stroke-width="1.2"%s/>' % (
                px(b[1]), py(b[4]), (b[2] - b[1]) * s, (b[4] - b[3]) * s, dash))
        for nm, p1, p2, r in p.cyls:
            x0 = min(p1[0], p2[0]) - (r if abs(p1[0] - p2[0]) < 1e-9 else 0)
            x1 = max(p1[0], p2[0]) + (r if abs(p1[0] - p2[0]) < 1e-9 else 0)
            y0 = min(p1[1], p2[1]) - (r if abs(p1[1] - p2[1]) < 1e-9 else 0)
            y1 = max(p1[1], p2[1]) + (r if abs(p1[1] - p2[1]) < 1e-9 else 0)
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="4" fill="none" stroke="#b5651d" stroke-width="1.2"/>' % (
                px(x0), py(y1), (x1 - x0) * s, (y1 - y0) * s))
    for i, m in sorted(HOLES):
        o.append('<circle cx="%.1f" cy="%.1f" r="3.3" fill="%s" stroke="#555" stroke-width="0.7"/>' % (
            px(X(i)), py(Y(m)), '#c0392b' if (i, m) in used else '#fff'))
    for p in parts:
        for i, m, lab in p.pins:
            if lab:
                o.append('<text x="%.1f" y="%.1f" font-size="7">%s</text>' % (px(X(i)) + 3.6, py(Y(m)) - 3.6, lab))
        anchor = p.boxes[0] if p.boxes else None
        if anchor:
            o.append('<text x="%.1f" y="%.1f" font-size="10" font-weight="bold" fill="#1f6fb5">%s</text>' % (
                px(anchor[1]) + 3, py(anchor[4]) + 12, p.name))
        elif p.cyls:
            nm, p1, p2, r = p.cyls[0]
            o.append('<text x="%.1f" y="%.1f" font-size="8" fill="#b5651d">%s</text>' % (
                px(min(p1[0], p2[0])), py(max(p1[1], p2[1]) + r) - 3, p.name))
        elif p.pins:
            i, m, _ = p.pins[0]
            o.append('<text x="%.1f" y="%.1f" font-size="8" fill="#b5651d">%s</text>' % (px(X(i)) - 6, py(Y(m)) + 15, p.name))
    for i in range(0, NI, 5):
        o.append('<text x="%.1f" y="62" font-size="10" fill="#666">%d</text>' % (px(X(i)) - 3, i))
    for m in range(NM):
        o.append('<text x="24" y="%.1f" font-size="10" fill="#666">%d</text>' % (py(Y(m)) + 3, m))
    o.append('</svg>')
    open(path, 'w').write('\n'.join(o))


def check(parts):
    rep, used = [], {}
    for p in parts:
        for i, m, lab in p.pins:
            if (i, m) not in HOLES:
                rep.append('PIN OFF BOARD: %s %s (%d,%d)' % (p.name, lab, i, m))
            if (i, m) in used:
                rep.append('HOLE SHARED: (%d,%d) %s / %s' % (i, m, used[(i, m)], p.name))
            used[(i, m)] = p.name
    return rep or ['pins: all on holes, none shared (%d of %d holes used)' % (len(used), len(HOLES))]


# ------------------------------------------------------------------ Fusion bodies
def build(tbm, bx, cyl, cone, uni, cut, obox):
    """{group: [(name, body)]}. obox(center, u, w, L, W, H) makes a rotated box."""
    import adsk.fusion
    INTER = adsk.fusion.BooleanTypes.IntersectionBooleanType
    L, iw, fz, zl = C['L'], C['iw'], C['fz'], C['zl']
    hw, w = c['half_w'], c['wall']
    out = {}
    # ---------------- tray
    tray = cut(bx(0, L, -hw, hw, c['floor_z'], zl), bx(C['in_a'], C['in_b'], -iw, iw, fz, zl + 1))
    # RJ12 ledges: rails under each board's edges (shared between neighbors), front step, 1 mm rear lip
    zb = c['rj_z']
    edges = sorted({round(y + s * c['rj_w'] / 2, 3) for y in c['rj_y'] for s in (-1, 1)})
    rails = [(-iw - 0.5, edges[0] + 0.8)]
    for a, b in zip(edges[1:-1:2], edges[2:-1:2]):
        rails.append((a - 0.8, b + 0.8))
    rails.append((edges[-1] - 0.8, iw + 0.5))
    for y0, y1 in rails:
        tray = uni(tray, bx(C['in_a'] - 0.01, C['rj_x1'] + 1.2, y0, y1, fz - 0.1, zb),                 # ledge
                   bx(C['in_a'] - 0.01, C['rj_x0'], y0, y1, fz - 0.1, zb + 1.4),                     # front step
                   bx(C['rj_x1'] + 0.2, C['rj_x1'] + 1.2, y0, y1, fz - 0.1, zb + 1.0))              # rear lip
    jz0 = zb + c['rj_t']
    for y in c['rj_y']:                                                                           # jack windows
        tray = cut(tray, bx(-1, C['in_a'] + 0.01, y - c['rj_jw'] / 2 - 0.15, y + c['rj_jw'] / 2 + 0.15,
                            jz0 - 0.15, jz0 + c['rj_jh'] + 0.15))
    # 18650 saddles
    for sx in (c['bat_x0'] + 8, c['bat_x0'] + c['bat_l'] - 12):
        tray = uni(tray, cut(bx(sx, sx + 4, -iw - 0.5, C['bat_y'] + 7.0, fz - 0.1, C['bat_zc'] - 3.0),
                             cyl((sx - 1, C['bat_y'], C['bat_zc']), (sx + 5, C['bat_y'], C['bat_zc']), c['bat_d'] / 2 + 0.2)))
    # perfboard posts (between holes) + ledge along the back wall
    for i in (0, 11, 21):
        xx = X(i) + 1.27
        for m in (0, 11):
            yy = Y(m) + (1.27 if m == 0 else -1.27)
            tray = uni(tray, bx(xx - 0.6, xx + 0.6, yy - 0.6, yy + 0.6, fz - 0.1, c['pb_z']))
    # end wall B: USB-C plug opening, solar lead hole
    usb = next(p for p in layout() if p.name == 'USB-C breakout')
    sk = next(b for b in usb.boxes if b[0] == 'USB-C socket')
    ucz, ucy = (sk[5] + sk[6]) / 2, (sk[3] + sk[4]) / 2
    tray = cut(tray, bx(C['in_b'] - 0.01, L + 1, ucy - 6.4, ucy + 6.4, ucz - 3.5, ucz + 3.5))
    tray = cut(tray, cyl((C['in_b'] - 1, -3.5, 12.0), (L + 1, -3.5, 12.0), 1.75))
    # groove: a notch in both end walls where the lid's channel passes
    for xa, xb in ((-1, C['in_a'] + 0.01), (C['in_b'] - 0.01, L + 1)):
        tray = cut(tray, bx(xa, xb, -C['ch_hw'] - 0.1, C['ch_hw'] + 0.1, C['ch_z0'] - 0.1, zl + 1))
    # lid screw bosses on the end walls, 45° conical undersides, inserts from the top
    ir = c['ins_d'] / 2 + c['ins_wall']
    for sx, sy in LID_SCREWS:
        zb0 = zl - c['ins_depth'] - 1.5
        tray = uni(tray, cyl((sx, sy, zb0), (sx, sy, zl), ir), cone((sx, sy, zb0), ir, (sx, sy, zb0 - ir + 0.3), 0.3))
        wx = (C['in_a'] - 0.5, sx) if sx < L / 2 else (sx, C['in_b'] + 0.5)
        tray = uni(tray, bx(wx[0], wx[1], sy - ir, sy + ir, zb0, zl))
    for sx, sy in LID_SCREWS:
        tray = cut(tray, cyl((sx, sy, zl + 1), (sx, sy, zl - c['ins_depth']), c['ins_d'] / 2))
    out['Tray'] = [('Tray', tray)]

    # ---------------- lid
    lid = bx(0, L, -hw, hw, zl, c['top'])
    lid = uni(lid, cut(bx(C['in_a'] + 0.15, C['in_b'] - 0.15, -iw + 0.15, iw - 0.15, zl - 1.2, zl + 0.01),   # register
                       bx(C['in_a'] + 1.35, C['in_b'] - 1.35, -iw + 1.35, iw - 1.35, zl - 2, zl + 1)))
    for sx, sy in LID_SCREWS:                                    # clear the bosses' tops
        lid = cut(lid, cyl((sx, sy, zl - 1.3), (sx, sy, zl + 0.01), ir + 0.3))
    # groove channel for the rod: floor + two walls, the full length (it fills the end-wall notches)
    lid = cut(lid, bx(-1, L + 1, -C['ch_hw'], C['ch_hw'], C['ch_z0'], c['top'] + 1))
    lid = uni(lid, cut(bx(0, L, -C['ch_hw'], C['ch_hw'], C['ch_z0'], c['top']),
                       bx(-1, L + 1, -c['groove_hw'], c['groove_hw'], c['groove_floor'], c['top'] + 1)))
    # hold-downs: on each jack's top, on the cell
    jtop = jz0 + c['rj_jh']
    for y in c['rj_y']:
        ztop = C['ch_z0'] + 0.01 if abs(y) < C['ch_hw'] + 2 else zl + 0.01      # the middle one hangs from the groove
        lid = uni(lid, bx(C['in_a'] + 7, C['in_a'] + 11, y - 2.0, y + 2.0, jtop + 0.1, ztop))
    btop = C['bat_zc'] + c['bat_d'] / 2
    for fx in (c['bat_x0'] + 20, c['bat_x0'] + c['bat_l'] - 24):
        lid = uni(lid, bx(fx, fx + 4, C['bat_y'] - 2, C['bat_y'] + 2, btop + 0.1, zl + 0.01))
    for sx, sy in LID_SCREWS:                                    # countersunk M3 holes
        lid = cut(lid, cyl((sx, sy, zl - 2), (sx, sy, c['top'] + 1), 1.7),
                  cone((sx, sy, c['top'] + 0.01), 3.2, (sx, sy, c['top'] - 1.5), 1.7))
    lid = cut(lid, tbm.copy(tray))                               # register clears every boss and web
    out['Lid'] = [('Lid', lid)]

    # ---------------- parts
    parts = []
    for n, y in enumerate(c['rj_y']):
        b = bx(C['rj_x0'], C['rj_x1'], y - c['rj_w'] / 2, y + c['rj_w'] / 2, zb, jz0)
        jack = bx(0, c['rj_jl'], y - c['rj_jw'] / 2, y + c['rj_jw'] / 2, jz0, jtop)
        mz = jz0 + c['rj_jh'] / 2 - 0.5
        jack = cut(jack, bx(-1, 13, y - c['rj_mouth_w'] / 2, y + c['rj_mouth_w'] / 2, mz - c['rj_mouth_h'] / 2, mz + c['rj_mouth_h'] / 2))
        parts += [('RJ12 %d board' % (n + 1), b), ('RJ12 %d jack' % (n + 1), jack),
                  ('RJ12 %d pins' % (n + 1), bx(C['rj_x0'] + 1, C['rj_x0'] + 10, y - 5, y + 5, zb - 0.4, zb))]
    parts.append(('18650', cyl((c['bat_x0'], C['bat_y'], C['bat_zc']), (c['bat_x0'] + c['bat_l'], C['bat_y'], C['bat_zc']), c['bat_d'] / 2)))
    parts.append(('Perfboard', bx(PB[0], PB[1], PB[2], PB[3], c['pb_z'], C['pb_top'])))
    for p in layout():
        for b in p.boxes:
            parts.append((b[0], bx(*b[1:])))
        for nm, p1, p2, r in p.cyls:
            parts.append((nm, cyl(p1, p2, r)))
    out['Parts'] = parts
    return out


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, '../../../..'))
    parts = layout()
    print('\n'.join(check(parts)))
    print('Box: %.1f x %.1f x %.1f mm (end A ports, end B USB-C at X %.2f)' % (C['L'], 2 * c['half_w'], c['top'], C['in_b']))
    svg_map(parts, os.path.join(repo, 'docs/renders/ctrl-v3-holemap.svg'))
    open(os.path.join(repo, 'docs/renders/ctrl-v3-wiring.md'), 'w').write(wiring_md() + '\n')
    print('wrote docs/renders/ctrl-v3-holemap.svg, docs/renders/ctrl-v3-wiring.md')
