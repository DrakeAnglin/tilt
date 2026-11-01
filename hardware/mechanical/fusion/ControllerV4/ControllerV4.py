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
    # USB-C breakout: Cermant 16P (B0CB2VFJ54), 21.6 x 12.8 (listing drawing). Scaled from its photo (confirm on the
    # board): socket 8.94 x 3.26 sticks out ~1.8 past the front edge; two ~Ø3.6 holes ~2.4 from the front edge,
    # ~17.3 apart; pin row (VBUS GND CC1 D- D+ CC2) centred, 1.3 from the back edge
    usb_bw=21.6, usb_bd=12.8, usb_y=6.0, usb_z=2.8, usb_stick=1.8, usb_sw=8.94, usb_sh=3.26, usb_sl=7.5,
    usb_hole=3.6, usb_hole_x=2.4, usb_hole_y=8.65,
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
# the owner's perfboard (3 x 7 cm from the kit): 10 columns a-j across, 24 rows 1-24 along the box.
# Orientation in the box: row 1 toward the ports (end A), column a toward the battery (room side).
NI, NM = 24, 10
COLS = 'abcdefghij'
PX0 = c['bat_x0'] + 1.27
PY0 = C['bat_y'] + c['bat_d'] / 2 + 2.6
HOLES = {(i, m) for i in range(NI) for m in range(NM)}


def H(name):
    """'b12' -> (i, m)"""
    return int(name[1:]) - 1, COLS.index(name[0])


def HN(i, m):
    return '%s%d' % (COLS[m], i + 1)


def X(i):
    return PX0 + PITCH * i


def Y(m):
    return PY0 + PITCH * m


PB = (X(0) - 1.27, X(NI - 1) + 1.27, Y(0) - 1.27, Y(NM - 1) + 1.27)
C['usb_x0'] = PB[1] + 6.0                                  # USB-C board's back edge, 6 mm past the dev board
# the socket's face is flush with end B's outer face, so the board's front edge sits 1.45 inside it, in a pocket in the wall
C['in_b'] = max(C['usb_x0'] + c['usb_bd'] + c['usb_stick'] - c['end_t'], c['bat_x0'] + c['bat_l'] + 14.0)
C['usb_x0'] = C['in_b'] + c['end_t'] - c['usb_stick'] - c['usb_bd']
C['L'] = C['in_b'] + c['end_t']
# pillars: two between the port bay and the electronics bay, two at end B; centred 0.5 inside the side walls' faces
PY = C['iw'] - c['pillar_r'] + 0.5
PILLARS = ((C['rj_x1'] + 6.5, -PY), (C['rj_x1'] + 6.5, PY), (C['in_b'] - c['pillar_r'] - 1.0, -PY), (C['in_b'] - c['pillar_r'] - 1.0, PY))


class Part:
    def __init__(self, name, pins=(), boxes=(), cyls=(), note=''):
        self.name, self.pins, self.boxes, self.cyls, self.note = name, list(pins), list(boxes), list(cyls), note


def layout():
    """Dev-board parts on named holes (column letter + row number). ESP32-C6 SuperMini pins confirmed by the owner
    (2026-11-01, board photo): chip side up, USB-C toward row 1, TX/RX/0-7 in column b and 5V/GND/3V3 in column h,
    using the board's INNER header holes (rows 15.24 apart, b-h)."""
    t = C['pb_top']
    parts = []
    left = ['TX16', 'RX17', '0', '1', '2', '3', '4', '5', '6', '7']
    right = ['5V', 'GND', '3V3', '20', '19', '18', '15', '14', '9', '8']
    esp_pins = [H('b%d' % (k + 1)) + (lab,) for k, lab in enumerate(left)] + \
               [H('h%d' % (k + 1)) + (lab,) for k, lab in enumerate(right)]
    xc, yc = (X(0) + X(9)) / 2, (Y(1) + Y(7)) / 2
    z0 = C['mod_z']
    parts.append(Part('ESP32-C6', esp_pins, [
        ('ESP32-C6 PCB', xc - 13, xc + 13, yc - 9, yc + 9, z0, z0 + 1.0),
        ('ESP32-C6 USB-C', xc - 13 - 0.8, xc - 13 - 0.8 + 7.35, yc - 4.47, yc + 4.47, z0 + 1.0, z0 + 4.26),
        ('ESP32-C6 headers', X(0) - 1.27, X(9) + 1.27, Y(1) - 1.27, Y(1) + 1.27, t, z0),
        ('ESP32-C6 headers 2', X(0) - 1.27, X(9) + 1.27, Y(7) - 1.27, Y(7) + 1.27, t, z0)]))
    # charger on 1 mm foam tape over rows 15-22, columns c-h
    cx0, cy0 = (X(14) + X(21)) / 2 - 9.8 - 0.25, (Y(2) + Y(7)) / 2 - 9.15
    parts.append(Part('MCP73871', [], [('MCP73871 PCB', cx0, cx0 + 19.6, cy0, cy0 + 18.3, t + 1.0, t + 2.6),
                                       ('MCP73871 parts', cx0 + 6, cx0 + 14, cy0 + 4, cy0 + 13, t + 2.6, t + 3.5),
                                       ('MCP73871 tape', cx0 + 0.5, cx0 + 19.1, cy0 + 0.5, cy0 + 17.8, t, t + 1.0)],
                      note='foam tape; its pads are wired to the board (see the wiring list)'))

    def upright(name, h_body, h_lead, d=2.3, h=8.0, labels=('', '')):
        """Resistor / diode standing up: body over the first hole, the hairpin lead in the second."""
        i0, m0 = H(h_body)
        i1, m1 = H(h_lead)
        return Part(name, [(i0, m0, labels[0]), (i1, m1, labels[1])],
                    cyls=[(name, (X(i0), Y(m0), t + 0.5), (X(i0), Y(m0), t + 0.5 + h), d / 2)])

    def disc(name, ha, hb, labels=('', '')):
        """Monolithic ceramic capacitor from the kit: leads 5.08 mm apart (3 holes: the middle one stays free under it),
        body ~4.8 wide along its leads, 2 mm thick, 5 mm tall. Diagonal (j1-i2): legs pulled in slightly to 3.6 mm."""
        (i0, m0), (i1, m1) = H(ha), H(hb)
        assert abs(i0 - i1) + abs(m0 - m1) == 2, name + ': ceramic caps span 3 holes or one diagonal'
        xm, ym = (X(i0) + X(i1)) / 2, (Y(m0) + Y(m1)) / 2
        if i0 != i1 and m0 != m1:                    # diagonal: bounding box of the tilted body, leaned 0.6 mm away from the ESP
            box = (name, xm - 2.4, xm + 2.4, ym - 1.8, ym + 3.0, t, t + 5.0)
        elif i0 == i1:
            box = (name, xm - 1.0, xm + 1.0, ym - 2.4, ym + 2.4, t, t + 5.0)
        else:
            box = (name, xm - 2.4, xm + 2.4, ym - 1.0, ym + 1.0, t, t + 5.0)
        return Part(name, [(i0, m0, labels[0]), (i1, m1, labels[1])], [box])

    # next to the ESP (column j rows 1-11; the middle hole of a ceramic cap stays empty under it)
    parts += [disc('C 10u', 'j1', 'i2', ('5V', 'G')),
              upright('R stat 10k', 'j4', 'j5'),
              upright('D3 1N5819', 'j6', 'j7', 2.7, 8.0, ('K', 'A')),
              upright('R div top 1M', 'j8', 'j9'),
              upright('R div bot 1M', 'j10', 'j11'),
              disc('C div 100n', 'i11', 'i13')]
    # angle filters, rows 12-14 (1 k standing, 100 n spanning 3 holes)
    parts += [upright('R ADC1 1k', 'b12', 'c12'), disc('C ADC1 100n', 'a14', 'c14'),
              upright('R ADC2 1k', 'd12', 'd13'), disc('C ADC2 100n', 'd14', 'f14'),
              upright('R ADC3 1k', 'f12', 'f13'), disc('C ADC3 100n', 'g12', 'g14')]
    # the charger's own bulk electrolytic is soldered on the charger board (not on the perfboard)
    # power row: diodes and zener (row 23), connectors (row 24)
    parts += [upright('D1 1N5819 USB', 'e23', 'd23', 2.7, 8.0, ('A', 'K')),
              upright('D2 1N5819 solar', 'h23', 'g23', 2.7, 8.0, ('A', 'K')),
              upright('Z 6.2V', 'f24', 'f23', 2.7, 8.0, ('A', 'K'))]
    parts.append(Part('Battery pins', [H('b24') + ('B-',), H('c24') + ('B+',)],
                      [('Battery pins', X(23) - 1.27, X(23) + 1.27, Y(1) - 1.27, Y(2) + 1.27, t, t + 2.5),
                       ('XH plug', X(23) - 2.45, X(23) + 2.45, Y(1) - 2.45, Y(2) + 2.45, t + 2.5, t + 8.5)]))
    parts.append(Part('USB leads', [H('d24') + ('V-',), H('e24') + ('V+',)]))
    parts.append(Part('Solar leads', [H('h24') + ('S+',), H('i24') + ('S-',)]))
    # port leads (18), soldered into these holes from the top
    parts.append(Part('Port leads', [H(n) + (lab,) for n, lab in (
        ('a1', 'P3 IN1'), ('a2', 'P3 IN2'), ('i6', 'P1 IN1'), ('i5', 'P1 IN2'), ('i4', 'P2 IN1'), ('i8', 'P2 IN2'),
        ('a7', 'P1 EN'), ('a8', 'P2 EN'), ('a9', 'P3 EN'), ('b11', 'P1 ANG'), ('d11', 'P2 ANG'), ('f11', 'P3 ANG'),
        ('j15', 'P1 VBAT'), ('j16', 'P2 VBAT'), ('j17', 'P3 VBAT'), ('a15', 'P1 GND'), ('a16', 'P2 GND'), ('a17', 'P3 GND'))]))
    return parts


# underside wiring: (from, to, note). 'bridge' = adjacent pads joined with a short bare wire / solder bridge
WIRES = [
    # rails (bare tinned wire along the column, soldered at every hole)
    ('a12', 'a24', 'GND rail: bare wire down column a, rows 12-24'),
    ('j12', 'j24', 'VBAT rail: bare wire down column j, rows 12-24'),
    # ESP pins to their neighbours
    ('a1', 'b1', 'bridge: port 3 IN1 -> GPIO16'), ('a2', 'b2', 'bridge: port 3 IN2 -> GPIO17'),
    ('a3', 'b3', 'bridge: angle 1 -> GPIO0'), ('a4', 'b4', 'bridge: angle 2 -> GPIO1'), ('a5', 'b5', 'bridge: angle 3 -> GPIO2'),
    ('a6', 'b6', 'bridge: battery divider -> GPIO3'),
    ('a7', 'b7', 'bridge: port 1 EN -> GPIO4'), ('a8', 'b8', 'bridge: port 2 EN -> GPIO5'), ('a9', 'b9', 'bridge: port 3 EN -> GPIO6'),
    ('a10', 'b10', 'bridge: charger STAT -> GPIO7'),
    ('h1', 'j1', 'bridge (over i1): ESP 5V -> C 10u'), ('h2', 'j2', 'bridge (over i2): ESP GND -> C 10u'),
    ('h3', 'i3', 'bridge: ESP 3V3'),
    ('h4', 'i4', 'bridge: port 2 IN1 -> GPIO20'), ('h5', 'i5', 'bridge: port 1 IN2 -> GPIO19'),
    ('h6', 'i6', 'bridge: port 1 IN1 -> GPIO18'), ('h8', 'i8', 'bridge: port 2 IN2 -> GPIO14'),
    # power to the ESP, STAT, divider
    ('i3', 'j4', 'wire: 3V3 -> R stat'), ('j5', 'a10', 'wire: R stat -> STAT / GPIO7'),
    ('j6', 'j1', 'wire: D3 cathode -> ESP 5V'), ('j7', 'j12', 'wire: D3 anode -> VBAT rail'),
    ('j2', 'a12', 'wire: ESP GND -> GND rail'),
    ('j8', 'j12', 'wire: R div top -> VBAT rail'), ('j9', 'j10', 'bridge: divider node'),
    ('j9', 'i11', 'wire: divider node -> C div'), ('i11', 'a6', 'wire: divider node -> GPIO3'),
    ('j11', 'a13', 'wire: R div bot -> GND rail'), ('i13', 'a13', 'wire: C div -> GND rail'),
    # angle filters
    ('b11', 'b12', 'bridge: port 1 ANGLE -> R ADC1'), ('d11', 'd12', 'bridge: port 2 ANGLE -> R ADC2'),
    ('f11', 'f12', 'bridge: port 3 ANGLE -> R ADC3'),
    ('c12', 'c13', 'bridge: R ADC1 -> filter 1 node'), ('c13', 'c14', 'bridge: filter 1 node -> C ADC1'), ('d13', 'd14', 'bridge: R ADC2 -> C ADC2'),
    ('f13', 'g12', 'wire: R ADC3 -> C ADC3'),
    ('c13', 'a3', 'wire: filter 1 -> GPIO0'), ('d13', 'a4', 'wire: filter 2 -> GPIO1'), ('f13', 'a5', 'wire: filter 3 -> GPIO2'),
    ('f14', 'a15', 'wire: C ADC2 -> GND rail'), ('g14', 'a16', 'wire: C ADC3 -> GND rail'),
    # power row
    ('e23', 'e24', 'bridge: USB V+ -> D1 anode'), ('h23', 'h24', 'bridge: solar + -> D2 anode'),
    ('d23', 'f23', 'wire: D1 cathode -> PWR node (zener cathode)'), ('f23', 'g23', 'bridge: PWR node -> D2 cathode'),
    ('b24', 'a24', 'bridge: battery - -> GND rail'), ('d24', 'a24', 'wire: USB V- -> GND rail'),
    ('f24', 'a24', 'wire: zener anode -> GND rail'), ('i24', 'j24', 'NO: do not bridge (j is VBAT); see the charger table'),
]
WIRES = [w for w in WIRES if not w[2].startswith('NO')] + [('i24', 'a24', 'wire: solar - -> GND rail (run it under the board)')]

CHARGER = [  # charger pad -> board
    ('PWR + (input)', 'g23', 'PWR node: D1 + D2 cathodes, zener'),
    ('PWR - / GND', 'a20', 'GND rail'),
    ('BATT +', 'c24', 'battery pin B+'),
    ('BATT -', 'a21', 'GND rail'),
    ('LOAD + (output)', 'j20', 'VBAT rail'),
    ('LOAD -', 'a22', 'GND rail'),
    ('STAT', 'a10', 'GPIO7 (pulled up by R stat)'),
    ('THERM', '(NTC)', 'remove the board\'s THERM resistor; NTC from THERM to GND, taped to the cell'),
]


def wiring_md():
    o = ['Step-by-step guide with pictures and which parts have a direction: [dev-board-build.md](../dev-board-build.md).', '',
         '## Parts: where each one goes', '', '| Part | Holes | Note |', '|---|---|---|']
    for p in layout():
        if p.pins and p.name not in ('ESP32-C6', 'Port leads'):
            o.append('| %s | %s | %s |' % (p.name, ', '.join('%s%s' % (HN(i, m), (' (' + lab + ')') if lab else '')
                                                         for i, m, lab in p.pins), p.note))
    o += ['', 'Ceramic capacitors have legs 3 holes apart: the middle hole stays empty. The 10 u goes corner to corner (j1-i2) with its legs pulled in slightly.',
          'The bulk electrolytic that comes with the charger is soldered onto the charger board itself (+ to its LOAD side).', '',
          'ESP32-C6: chip side up, header pins in its **inner** holes, into **b1-b10** (TX16, RX17, 0, 1, 2, 3, 4, 5, 6, 7) and',
          '**h1-h10** (5V, GND, 3V3, 20, 19, 18, 15, 14, 9, 8), USB-C overhanging row 1 (confirmed against the board).',
          'Leave its inner pads (12, 13, 21, 22, 23) and BAT pad unconnected. Charger: foam tape over **c15-h22**.', '',
          'D3 (j6-j7) drops ~0.3 V, so the ESP browns out near 3.4-3.5 V on the cell (last ~10-15 %). Optional: 2 header',
          'pins + jumper at j6-j7 instead of D3 (zero drop; pull the jumper before plugging USB into the ESP).', '',
          '## Port leads (from the RJ12 boards)', '', '| Lead | Hole | Lead | Hole | Lead | Hole |', '|---|---|---|---|---|---|']
    leads = {lab: HN(i, m) for i, m, lab in next(p for p in layout() if p.name == 'Port leads').pins}
    for sig in ('IN1', 'IN2', 'EN', 'ANG', 'VBAT', 'GND'):
        o.append('| ' + ' | '.join('P%d %s | %s' % (k, sig, leads['P%d %s' % (k, sig)]) for k in (1, 2, 3)) + ' |')
    o += ['', 'RJ12 pin -> signal: 1 VBAT, 2 IN1, 3 GND, 4 ANG, 5 EN, 6 IN2. Port 1 = room side, port 3 = back side.', '',
          '## Underside wiring', '', '| From | To | What |', '|---|---|---|']
    o += ['| %s | %s | %s |' % w for w in WIRES]
    o += ['', '## Charger pads', '', '| Pad | Board hole | Net |', '|---|---|---|']
    o += ['| %s | %s | %s |' % w for w in CHARGER]
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
    W, H = (PB[1] - PB[0]) * s + 140, (PB[3] - PB[2]) * s + 120
    px = lambda x: 70 + (x - PB[0]) * s
    py = lambda y: 70 + (PB[3] - y) * s
    used = {(i, m) for p in parts for i, m, _ in p.pins}
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica,Arial">' % (W, H),
         '<rect width="100%" height="100%" fill="#fff"/>',
         '<text x="60" y="26" font-size="16" font-weight="bold">ControllerV4 dev board (perfboard a-j x 1-24), top view</text>',
         '<text x="60" y="46" font-size="11">Row 1 (left) toward the ports, column a (bottom) toward the battery. '
         'Red = used hole. Row numbers on top, column letters on the left.</text>',
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
                o.append('<text x="%.1f" y="%.1f" font-size="6">%s</text>' % (px(X(i)) + 3.6, py(Y(m)) - 3.6, lab))
        if p.boxes:
            b = p.boxes[0]
            o.append('<text x="%.1f" y="%.1f" font-size="10" font-weight="bold" fill="#1f6fb5">%s</text>' % (px(b[1]) + 3, py(b[4]) + 12, p.name))
        elif p.cyls:
            nm, p1, p2, r = p.cyls[0]
            o.append('<text x="%.1f" y="%.1f" font-size="8" fill="#b5651d">%s</text>' % (px(min(p1[0], p2[0])), py(max(p1[1], p2[1]) + r) - 3, p.name))
        elif p.pins:
            i, m, _ = p.pins[0]
            o.append('<text x="%.1f" y="%.1f" font-size="8" fill="#b5651d">%s</text>' % (px(X(i)) - 26, py(Y(m)) + 3, p.name))
    for i in range(NI):
        o.append('<text x="%.1f" y="62" font-size="10" fill="#666">%d</text>' % (px(X(i)) - 4, i + 1))
    for m in range(NM):
        o.append('<text x="30" y="%.1f" font-size="11" font-weight="bold" fill="#666">%s</text>' % (py(Y(m)) + 4, COLS[m]))
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
    for i in (1, 13, 22):
        for m in (0, 8):
            xx, yy = X(i) + 1.27, Y(m) + 1.27
            tray = uni(tray, bx(xx - 0.7, xx + 0.7, yy - 0.7, yy + 0.7, fz - 0.1, c['pb_z']))
    # USB-C breakout: two posts with locating pegs through its mounting holes; its front edge in a pocket in end wall B
    # so the socket's face is flush with the outside; socket window; solar lead hole
    ux0, ux1 = C['usb_x0'], C['usb_x0'] + c['usb_bd']
    uy0, uy1 = c['usb_y'] - c['usb_bw'] / 2, c['usb_y'] + c['usb_bw'] / 2
    hx = ux1 - c['usb_hole_x']
    bz0, bz1 = c['usb_z'], c['usb_z'] + 1.6
    for hy in (c['usb_y'] - c['usb_hole_y'], c['usb_y'] + c['usb_hole_y']):
        tray = uni(tray, cyl((hx, hy, fz - 0.1), (hx, hy, bz0), 2.8))          # flat-topped post: the board slides over it
    for hy in (c['usb_y'] - c['usb_hole_y'], c['usb_y'] + c['usb_hole_y']):
        tray = cut(tray, cyl((hx, hy, bz0 + 0.01), (hx, hy, bz0 - 1.2), 1.5))   # socket for the lid's locating pin
    tray = cut(tray, bx(C['in_b'] - 0.01, ux1 + 0.2, uy0 - 0.2, uy1 + 0.2, bz0 - 0.2, bz1 + 0.2))      # board-edge pocket
    sz0 = bz1
    wr = c['usb_sh'] / 2 + 0.2                                       # stadium window: the socket has round ends
    wzc = sz0 + c['usb_sh'] / 2
    hwx = c['usb_sw'] / 2 - c['usb_sh'] / 2
    tray = cut(tray, bx(ux1 - 1, L + 1, c['usb_y'] - hwx, c['usb_y'] + hwx, wzc - wr, wzc + wr),
               cyl((ux1 - 1, c['usb_y'] - hwx, wzc), (L + 1, c['usb_y'] - hwx, wzc), wr),
               cyl((ux1 - 1, c['usb_y'] + hwx, wzc), (L + 1, c['usb_y'] + hwx, wzc), wr))
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
    for fi, fm in ((10, 0), (18, 9)):                   # hold the board down on empty holes a11 and j19
        fx, fy = X(fi), Y(fm)
        ztop = C['g_under'] + 0.01 if abs(fy) < C['gw_out'] + 1.5 else zl + 0.01
        lid = uni(lid, bx(fx - 0.8, fx + 0.8, fy - 0.6, fy + 0.6, C['pb_top'] + 0.1, ztop))
    # USB-C board: two pins under the lid drop through its mounting holes into the posts' sockets (tapered tips), and a
    # collar round each presses the board onto its post. The board slides in flat; the lid locks it.
    for hy in (c['usb_y'] - c['usb_hole_y'], c['usb_y'] + c['usb_hole_y']):
        ztop = C['g_under'] + 0.01 if abs(hy) < C['gw_out'] + 2.0 else zl + 0.01
        cr = min(1.95, C['in_b'] - hx - 0.1)                                                    # clear of end wall B
        lid = uni(lid, cyl((hx, hy, bz1 + 0.1), (hx, hy, ztop), cr),                           # collar
                  cyl((hx, hy, bz0 - 0.6), (hx, hy, bz1 + 0.2), 1.3),                        # pin, Ø2.6 in the Ø3.0 hole
                  cone((hx, hy, bz0 - 0.59), 1.3, (hx, hy, bz0 - 1.0), 0.9))                 # tapered tip
    # the register lip simply stops at each pillar: a square-ended gap across that side of the lip (no slivers)
    for px, py in PILLARS:
        sy = 1 if py > 0 else -1
        gx = c['pillar_r'] + 0.4
        lid = cut(lid, bx(px - gx, px + gx, sy * (abs(py) - c['pillar_r'] - 0.4), sy * (iw + 1), zl - 3, zl + 0.01))
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
    ub = bx(ux0, ux1, uy0, uy1, bz0, bz1)
    for hy in (c['usb_y'] - c['usb_hole_y'], c['usb_y'] + c['usb_hole_y']):
        ub = cut(ub, cyl((hx, hy, bz0 - 1), (hx, hy, bz1 + 1), c['usb_hole'] / 2))
    parts.append(('USB-C board', ub))
    sx0, sx1 = ux1 + c['usb_stick'] - c['usb_sl'], ux1 + c['usb_stick']
    sr, szc, shx = c['usb_sh'] / 2, bz1 + c['usb_sh'] / 2, c['usb_sw'] / 2 - c['usb_sh'] / 2
    parts.append(('USB-C socket', uni(bx(sx0, sx1, c['usb_y'] - shx, c['usb_y'] + shx, bz1, bz1 + c['usb_sh']),
                                      cyl((sx0, c['usb_y'] - shx, szc), (sx1, c['usb_y'] - shx, szc), sr),
                                      cyl((sx0, c['usb_y'] + shx, szc), (sx1, c['usb_y'] + shx, szc), sr))))
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
    open(os.path.join(repo, 'docs/renders/ctrl-v4-wiring.md'), 'w').write('# ControllerV4 dev board: placement and wiring\n\n' + wiring_md() + '\n')
