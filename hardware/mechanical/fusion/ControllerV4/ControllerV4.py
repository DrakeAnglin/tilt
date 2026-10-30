"""ControllerV4: controller box + hole-accurate dev board (ESP32-C6, MCP73871, 18650, 3 x RJ12, USB-C, solar).

Design rules (V3 broke the first two):
  * nothing floats: every boss, ledge, saddle and post grows straight up from the tray floor (the tray prints floor
    down); the lid's features grow from its top face (it prints top face down). No supports anywhere.
  * every part has its own bay with room round it: ports | dev board beside the cell | USB-C, with the lid's four
    screw pillars between the bays, built into the side walls.
  * a finished outside: 55.4 x 33.3 section like the tilter, all outer edges rounded (vertical corners r4, the rest
    r1.5), a rounded rod groove along the lid, flush jacks with engraved port marks (1, 2, 3 dots) under them, flush
    M3 heads in countersinks.

The box sits under the tilt rod: the rod runs in the lid's groove, 1 mm above the groove floor at its lowest sweep.

  python3 hardware/mechanical/fusion/ControllerV4/ControllerV4.py    # hole map + wiring table
  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v4.py --timeout 1500

Coordinates (mm): X along the rail from end A's outer face (ports), Y across (-Y room side), Z up from the rail floor.
"""

import math
import os

C = dict(
    half_w=27.7, floor_z=0.2, top=33.3, wall=2.0, floor=2.0, lid=2.0, end_t=2.4, corner_r=4.0, edge_r=1.5,
    rail_w=55.5, rail_h=36.5, rail_wall=2.0, lip_in=4.5, lip_h=3.0, rod_z=24.0, rod=4.0,
    groove_hw=6.0, groove_floor=20.2, groove_wall=1.6, groove_r=1.5,   # rod sweeps down to Z 21.17: 0.97 clear
    # RJ12 breakouts trimmed to 15 wide, jack 13.5 W x 14.7 L x 13 H, front overhang 4.5
    rj_w=15.0, rj_d=19.9, rj_t=1.6, rj_jw=13.5, rj_jl=14.7, rj_jh=13.0, rj_over=4.5, rj_z=2.6, rj_y=(-17.0, 0.0, 17.0),
    rj_mouth_w=9.9, rj_mouth_h=8.6,
    # 18650 pack along the room-side wall
    bat_d=19.05, bat_l=68.1, bat_x0=40.0,
    # dev board (perfboard) beside the cell
    pb_z=8.0, pb_t=1.6, plastic=2.5,
    # USB-C breakout (22.1 x 13.05) standing in its own pocket at end B
    usb_bw=22.1, usb_bd=13.05, usb_y=6.0, usb_z=2.8,
    # lid screws: M3 x 8 flat head into heat-set inserts (Ø4.0 x 6.7) in four pillars
    ins_d=4.0, ins_depth=6.7, pillar_r=3.6,
)
c = C
C['iw'] = c['half_w'] - c['wall']
C['fz'] = c['floor_z'] + c['floor']
C['zl'] = c['top'] - c['lid']
C['pb_top'] = c['pb_z'] + c['pb_t']
C['mod_z'] = C['pb_top'] + c['plastic']
C['bat_y'] = -C['iw'] + 0.3 + c['bat_d'] / 2
C['bat_zc'] = C['fz'] + 0.5 + c['bat_d'] / 2
C['gw_out'] = c['groove_hw'] + c['groove_wall']
C['g_under'] = c['groove_floor'] - 1.2                   # the groove channel's underside
C['rj_x0'] = c['end_t'] + 2.1                             # board front edge (jack face flush with the outer face)
C['rj_over'] = C['rj_x0']
C['rj_x1'] = C['rj_x0'] + c['rj_d']

PITCH = 2.54
NI, NM = 26, 12
PX0 = c['bat_x0'] + 1.27
PY0 = C['bat_y'] + c['bat_d'] / 2 + 2.6
HOLES = {(i, m) for i in range(NI) for m in range(NM)}


def X(i):
    return PX0 + PITCH * i


def Y(m):
    return PY0 + PITCH * m


PB = (X(0) - 1.27, X(NI - 1) + 1.27, Y(0) - 1.27, Y(NM - 1) + 1.27)
C['usb_x0'] = PB[1] + 6.0                                  # USB-C pocket starts 6 mm past the dev board
C['in_b'] = max(C['usb_x0'] + c['usb_bd'], c['bat_x0'] + c['bat_l'] + 14.0)
C['L'] = C['in_b'] + c['end_t']
# pillars: two between the port bay and the electronics bay, two at end B; centred 0.5 inside the side walls' faces
PY = C['iw'] - c['pillar_r'] + 0.5
PILLARS = ((C['rj_x1'] + 6.5, -PY), (C['rj_x1'] + 6.5, PY), (C['in_b'] - c['pillar_r'] - 1.0, -PY), (C['in_b'] - c['pillar_r'] - 1.0, PY))


class Part:
    def __init__(self, name, pins=(), boxes=(), cyls=(), note=''):
        self.name, self.pins, self.boxes, self.cyls, self.note = name, list(pins), list(boxes), list(cyls), note


def layout():
    """Dev-board parts on their holes. ESP32-C6 SuperMini pins (listing photo; check the board): +Y row 7 6 5 4 3 2 1 0
    RX TX, -Y row 8 9 14 15 18 19 20 3V3 GND 5V, USB-C at +X."""
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
    parts.append(Part('MCP73871', [], [('MCP73871 PCB', X(13), X(13) + 19.6, Y(2), Y(2) + 18.3, t + 1.0, t + 2.6),
                                       ('MCP73871 parts', X(13) + 6, X(13) + 14, Y(2) + 4, Y(2) + 13, t + 2.6, t + 3.5),
                                       ('MCP73871 tape', X(13) + 0.5, X(13) + 19.1, Y(2) + 0.5, Y(2) + 17.8, t, t + 1.0)],
                      note='PWR, BATT, LOAD, THERM pads wired to the holes beside it'))

    def lying(name, i0, m0, i1, m1, d=2.3, ln=6.3):
        xa, ya, xb, yb = X(i0), Y(m0), X(i1), Y(m1)
        ux, uy = (1, 0) if m0 == m1 else (0, 1)
        xm, ym = (xa + xb) / 2, (ya + yb) / 2
        return Part(name, [(i0, m0, ''), (i1, m1, '')],
                    cyls=[(name, (xm - ux * ln / 2, ym - uy * ln / 2, t + d / 2), (xm + ux * ln / 2, ym + uy * ln / 2, t + d / 2), d / 2)])

    def disc(name, i0, i1, m):
        return Part(name, [(i0, m, ''), (i1, m, '')], [(name, X(i0) - 0.8, X(i1) + 0.8, Y(m) - 1.25, Y(m) + 1.25, t, t + 5.0)])

    # RC filters on the three angle lines, along the +Y edge next to the ESP's ADC pins
    for k in range(3):
        parts += [lying('R ADC%d' % (k + 1), 4 * k + 1, 11, 4 * k + 4, 11), disc('C ADC%d' % (k + 1), 4 * k + 2, 4 * k + 3, 10)]
    # battery divider, STAT pull-up, 10 u at the ESP's 5V, D3 (charger LOAD -> ESP 5V) along the -Y edge
    parts += [lying('R div top', 1, 0, 4, 0), lying('R div bot', 5, 0, 8, 0), disc('C div', 9, 10, 0),
              disc('C 10u', 11, 12, 0), lying('R stat', 14, 0, 17, 0), lying('D3 1N5819', 18, 0, 21, 0, 2.7, 5.2)]
    parts += [lying('D1 1N5819 USB', 24, 2, 24, 5, 2.7, 5.2), lying('D2 1N5819 solar', 24, 6, 24, 9, 2.7, 5.2),
              lying('Z 6.2V', 22, 4, 22, 7, 2.7, 5.2)]
    parts.append(Part('C bulk', [(22, 10, '+'), (23, 10, '-')],                     # 8 x 13 radial, standing
                      cyls=[('C bulk', ((X(22) + X(23)) / 2, Y(10), t), ((X(22) + X(23)) / 2, Y(10), t + 13.0), 4.0)]))
    parts.append(Part('Battery pins', [(25, 0, 'B+'), (25, 1, 'B-')],
                      [('Battery pins', X(25) - 1.27, X(25) + 1.27, Y(0) - 1.27, Y(1) + 1.27, t, t + 2.5),
                       ('XH plug', X(25) - 2.45, X(25) + 2.45, Y(0) - 2.45, Y(1) + 2.45, t + 2.5, t + 8.5)]))
    parts.append(Part('USB pads', [(25, 3, 'V+'), (25, 4, 'V-')]))
    parts.append(Part('Solar pads', [(25, 10, 'S+'), (25, 11, 'S-')]))
    return parts


PORTS = [('Port 1 (room side)', '18', '19', '4', '0'), ('Port 2 (middle)', '20', '14', '5', '1'),
         ('Port 3 (back side)', 'TX16', 'RX17', '6', '2')]


def wiring_md():
    o = ['| From | To | Note |', '|---|---|---|']
    for name, i1, i2, en, adc in PORTS:
        o += ['| %s pin 1 VBAT | charger LOAD | motor supply |' % name,
              '| %s pin 2 IN1 | ESP GPIO %s | PWM |' % (name, i1),
              '| %s pin 3 GND | GND | |' % name,
              '| %s pin 4 ANGLE | R ADC 1 k -> ESP GPIO %s; C ADC 100 n to GND | AS5600 OUT |' % (name, adc),
              '| %s pin 5 EN | ESP GPIO %s | AS5600 power + DRV8833 sleep |' % (name, en),
              '| %s pin 6 IN2 | ESP GPIO %s | PWM |' % (name, i2)]
    o += ['| USB-C VBUS / GND (2 leads) | USB pads V+ / V- -> D1 (band to charger) -> charger PWR | charge only |',
          '| Solar + / - (ZH pigtail through end wall B) | Solar pads S+ / S- -> D2 (band to charger) -> charger PWR | |',
          '| 6.2 V zener | across charger PWR / GND, band to PWR | solar over-voltage clamp |',
          '| Battery pins B+ / B- | charger BATT + / - | the cell\'s XH plug pushes on |',
          '| 10 k NTC taped to the cell | charger THERM (replaces its fixed resistor) | stops charging when hot |',
          '| Charger LOAD | D3 (band to ESP) -> ESP 5V; C bulk + on LOAD | |',
          '| Charger LOAD | R div top 1 M -> GPIO 3 -> R div bot 1 M -> GND; C div 100 n on GPIO 3 | battery voltage |',
          '| Charger STAT | GPIO 7, R stat 10 k to 3V3 | charging / charged |',
          '| C 10 u | ESP 5V to GND | |']
    return '\n'.join(o)


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


def svg_map(parts, path):
    s = 9.0
    W, H = (PB[1] - PB[0]) * s + 120, (PB[3] - PB[2]) * s + 120
    px = lambda x: 60 + (x - PB[0]) * s
    py = lambda y: 70 + (PB[3] - y) * s
    used = {(i, m) for p in parts for i, m, _ in p.pins}
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica,Arial">' % (W, H),
         '<rect width="100%" height="100%" fill="#fff"/>',
         '<text x="60" y="26" font-size="16" font-weight="bold">ControllerV4 dev board, top view (2.54 mm holes)</text>',
         '<text x="60" y="46" font-size="11">Ports (end A) to the left, USB-C (end B) to the right; back wall (+Y) at the top. '
         'Red = pin hole. Rows (i) along the top, columns (m) on the left.</text>',
         '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#e9f4e1" stroke="#3a7a2a" stroke-width="2"/>' % (
             px(PB[0]), py(PB[3]), (PB[1] - PB[0]) * s, (PB[3] - PB[2]) * s)]
    for p in parts:
        for b in p.boxes:
            if 'header' in b[0] or 'tape' in b[0]:
                continue
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#1f6fb5" stroke-width="1.2"/>' % (
                px(b[1]), py(b[4]), (b[2] - b[1]) * s, (b[4] - b[3]) * s))
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
        if p.boxes:
            b = p.boxes[0]
            o.append('<text x="%.1f" y="%.1f" font-size="10" font-weight="bold" fill="#1f6fb5">%s</text>' % (px(b[1]) + 3, py(b[4]) + 12, p.name))
        elif p.cyls:
            nm, p1, p2, r = p.cyls[0]
            o.append('<text x="%.1f" y="%.1f" font-size="8" fill="#b5651d">%s</text>' % (px(min(p1[0], p2[0])), py(max(p1[1], p2[1]) + r) - 3, p.name))
        elif p.pins:
            i, m, _ = p.pins[0]
            o.append('<text x="%.1f" y="%.1f" font-size="8" fill="#b5651d">%s</text>' % (px(X(i)) - 26, py(Y(m)) + 3, p.name))
    for i in range(0, NI, 5):
        o.append('<text x="%.1f" y="62" font-size="10" fill="#666">%d</text>' % (px(X(i)) - 3, i))
    for m in range(NM):
        o.append('<text x="24" y="%.1f" font-size="10" fill="#666">%d</text>' % (py(Y(m)) + 3, m))
    o.append('</svg>')
    open(path, 'w').write('\n'.join(o))


# ------------------------------------------------------------------ Fusion bodies
def build(tbm, bx, cyl, cone, uni, cut, rbox):
    """{group: [(name, body)]}. rbox(x0, x1, y0, y1, z0, z1, r) = box with its four vertical edges rounded."""
    L, iw, fz, zl = C['L'], C['iw'], C['fz'], C['zl']
    hw = c['half_w']
    out = {}
    # ---------------- tray: rounded-corner shell
    tray = cut(rbox(0, L, -hw, hw, c['floor_z'], zl, c['corner_r']),
               rbox(c['end_t'], C['in_b'], -iw, iw, fz, zl + 1, c['corner_r'] - c['wall']))
    # the lid's groove channel passes over both end walls
    for xa, xb in ((-1, c['end_t'] + 0.01), (C['in_b'] - 0.01, L + 1)):
        tray = cut(tray, bx(xa, xb, -C['gw_out'] - 0.15, C['gw_out'] + 0.15, C['g_under'] - 0.15, zl + 1))
    # pillars (lid screws): full height from the floor, built into the side walls
    for px, py in PILLARS:
        sy = 1 if py > 0 else -1
        tray = uni(tray, cyl((px, py, fz - 0.1), (px, py, zl), c['pillar_r']),
                   bx(px - c['pillar_r'], px + c['pillar_r'], py, sy * (iw + 0.5), fz - 0.1, zl))
    for px, py in PILLARS:
        tray = cut(tray, cyl((px, py, zl + 1), (px, py, zl - c['ins_depth']), c['ins_d'] / 2))
    # port bay: ledges for the RJ12 boards (shared between neighbours), front step + 1 mm rear lip; jack windows
    zb = c['rj_z']
    edges = sorted({round(y + s * c['rj_w'] / 2, 3) for y in c['rj_y'] for s in (-1, 1)})
    rails = [(-iw - 0.5, edges[0] + 0.8)] + [(a - 0.8, b + 0.8) for a, b in zip(edges[1:-1:2], edges[2:-1:2])] + \
            [(edges[-1] - 0.8, iw + 0.5)]
    for y0, y1 in rails:
        tray = uni(tray, bx(c['end_t'] - 0.01, C['rj_x1'] + 1.4, y0, y1, fz - 0.1, zb),
                   bx(c['end_t'] - 0.01, C['rj_x0'], y0, y1, fz - 0.1, zb + 1.4),
                   bx(C['rj_x1'] + 0.2, C['rj_x1'] + 1.4, y0, y1, fz - 0.1, zb + 1.0))
    jz0 = zb + c['rj_t']
    for y in c['rj_y']:
        tray = cut(tray, bx(-1, c['end_t'] + 0.01, y - c['rj_jw'] / 2 - 0.15, y + c['rj_jw'] / 2 + 0.15, jz0 - 0.15, jz0 + c['rj_jh'] + 0.15))
    # port marks: 1, 2, 3 engraved dots under each jack (0.5 deep)
    for n, y in enumerate(c['rj_y']):
        for k in range(n + 1):
            dy = (k - n / 2.0) * 2.4
            tray = cut(tray, cyl((-1, y + dy, 2.75), (0.5, y + dy, 2.75), 0.6))
    # cell bay: two saddles + end stops
    bc = C['bat_zc']
    for sx in (c['bat_x0'] + 10, c['bat_x0'] + c['bat_l'] - 14):
        tray = uni(tray, cut(bx(sx, sx + 4, -iw - 0.5, C['bat_y'] + 6.0, fz - 0.1, bc - 2.0),
                             cyl((sx - 1, C['bat_y'], bc), (sx + 5, C['bat_y'], bc), c['bat_d'] / 2 + 0.2)))
    for sx in (c['bat_x0'] - 2.2, c['bat_x0'] + c['bat_l'] + 0.2):
        tray = uni(tray, bx(sx, sx + 2.0, C['bat_y'] - 5, C['bat_y'] + 5, fz - 0.1, bc - 3.0))
    # dev board: 6 posts between holes
    for i in (0, 12, 24):
        for m in (0, 10):
            xx, yy = X(i) + 1.27, Y(m) + 1.27
            tray = uni(tray, bx(xx - 0.7, xx + 0.7, yy - 0.7, yy + 0.7, fz - 0.1, c['pb_z']))
    # USB-C breakout: pocket of 4 corner posts, socket in end wall B; plug opening; solar lead hole
    ux0, ux1 = C['usb_x0'], C['usb_x0'] + c['usb_bd']
    uy0, uy1 = c['usb_y'] - c['usb_bw'] / 2, c['usb_y'] + c['usb_bw'] / 2
    for xa, ya in ((ux0 - 1.6, uy0 - 1.6), (ux0 - 1.6, uy1), (ux1 - 6.0, uy0 - 1.6), (ux1 - 6.0, uy1)):
        tray = uni(tray, bx(xa, xa + 1.6 if xa < ux0 else ux1 - 2.0, ya, ya + 1.6, fz - 0.1, c['usb_z'] + 1.6 + 1.0))
    tray = uni(tray, bx(ux0, ux1 - 7.4, uy0 + 1.0, uy1 - 1.0, fz - 0.1, c['usb_z']))        # board rests on this pad
    sz = c['usb_z'] + 1.6 + 1.63
    tray = cut(tray, bx(C['in_b'] - 0.01, L + 1, c['usb_y'] - 6.3, c['usb_y'] + 6.3, sz - 3.4, sz + 3.4))
    tray = cut(tray, cyl((C['in_b'] - 1, -12.0, 9.0), (L + 1, -12.0, 9.0), 1.75))
    out['Tray'] = [('Tray', tray)]

    # ---------------- lid
    lid = rbox(0, L, -hw, hw, zl, c['top'], c['corner_r'])
    reg = cut(rbox(c['end_t'] + 0.2, C['in_b'] - 0.2, -iw + 0.2, iw - 0.2, zl - 1.4, zl + 0.01, c['corner_r'] - c['wall'] - 0.2),
              rbox(c['end_t'] + 1.6, C['in_b'] - 1.6, -iw + 1.6, iw - 1.6, zl - 2, zl + 1, max(c['corner_r'] - c['wall'] - 1.6, 0.3)))
    lid = uni(lid, reg)
    # groove channel: open rounded groove on top, the full length
    lid = cut(lid, bx(-1, L + 1, -C['gw_out'], C['gw_out'], C['g_under'], c['top'] + 1))
    lid = uni(lid, cut(bx(0, L, -C['gw_out'], C['gw_out'], C['g_under'], c['top']),
                       bx(-1, L + 1, -c['groove_hw'], c['groove_hw'], c['groove_floor'], c['top'] + 1)))
    # hold-downs: jacks (the middle one from the groove's underside), cell, dev board corners, USB-C board
    jtop = jz0 + c['rj_jh']
    for y in c['rj_y']:
        ztop = C['g_under'] + 0.01 if abs(y) < C['gw_out'] + 2 else zl + 0.01
        lid = uni(lid, bx(c['end_t'] + 7, c['end_t'] + 11, y - 2.0, y + 2.0, jtop + 0.1, ztop))
    btop = bc + c['bat_d'] / 2
    for fx in (c['bat_x0'] + 22, c['bat_x0'] + c['bat_l'] - 26):
        lid = uni(lid, bx(fx, fx + 4, C['bat_y'] - 2, C['bat_y'] + 2, btop + 0.1, zl + 0.01))
    for xx in (PB[0] + 0.3, PB[1] - 2.3):
        lid = uni(lid, bx(xx, xx + 2.0, PB[3] - 2.0, PB[3] - 0.3, C['pb_top'] + 0.1, zl + 0.01))
    for fy in (uy0 + 1.0, uy1 - 3.0):                       # under the groove they hang from the groove's underside
        ztop = C['g_under'] + 0.01 if abs(fy + 1.0) < C['gw_out'] + 1.0 else zl + 0.01
        lid = uni(lid, bx(ux0 + 1, ux0 + 3, fy, fy + 2.0, c['usb_z'] + 1.7, ztop))
    lid = cut(lid, tbm.copy(tray))
    for px, py in PILLARS:
        lid = cut(lid, cyl((px, py, zl - 2), (px, py, c['top'] + 1), 1.7),
                  cone((px, py, c['top'] + 0.01), 3.2, (px, py, c['top'] - 1.5), 1.7))
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
    parts.append(('18650', cyl((c['bat_x0'], C['bat_y'], bc), (c['bat_x0'] + c['bat_l'], C['bat_y'], bc), c['bat_d'] / 2)))
    parts.append(('Perfboard', bx(PB[0], PB[1], PB[2], PB[3], c['pb_z'], C['pb_top'])))
    for p in layout():
        for b in p.boxes:
            parts.append((b[0], bx(*b[1:])))
        for nm, p1, p2, r in p.cyls:
            parts.append((nm, cyl(p1, p2, r)))
    parts.append(('USB-C board', bx(ux0, ux1, uy0, uy1, c['usb_z'], c['usb_z'] + 1.6)))
    rec = bx(ux1 - 7.35, ux1, c['usb_y'] - 4.47, c['usb_y'] + 4.47, c['usb_z'] + 1.6, c['usb_z'] + 1.6 + 3.26)
    parts.append(('USB-C socket', rec))
    out['Parts'] = parts
    return out


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, '../../../..'))
    parts = layout()
    print('\n'.join(check(parts)))
    print('Box %.1f x %.1f x %.1f mm; dev board %.1f x %.1f; pillars at %s' % (
        C['L'], 2 * c['half_w'], c['top'], PB[1] - PB[0], PB[3] - PB[2], ', '.join('(%.1f, %.1f)' % q for q in PILLARS)))
    svg_map(parts, os.path.join(repo, 'docs/renders/ctrl-v4-holemap.svg'))
    open(os.path.join(repo, 'docs/renders/ctrl-v4-wiring.md'), 'w').write(wiring_md() + '\n')
