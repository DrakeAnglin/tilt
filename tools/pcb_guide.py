"""Build guide for the controller carrier PCB (hardware/pcb, v2.1): writes docs/pcb-build.md and one picture per step
(docs/renders/pcb-build-NN.svg/.png), all drawn from the real board file (controller.kicad_pcb) and netlist.py, so the
pictures, part lists and positions always match the board you're holding.

In each picture the current step's parts are in color and labeled, earlier steps are gray, later ones are only their
pads. End A (the RJ12 jacks) is on the left, end B (the USB-C socket) on the right; you're looking at the top (parts) side.

Run with KiCad's Python (it has pcbnew):
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 tools/pcb_guide.py --png
"""
import html
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '../hardware/pcb'))
import netlist as N  # noqa: E402

PCB = os.path.join(HERE, '../hardware/pcb/controller/controller.kicad_pcb')
OUT = os.path.join(HERE, '../docs/renders')
DOC = os.path.join(HERE, '../docs/pcb-build.md')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

S = 9.0                              # px per mm
MX, MY = 60, 70                      # margins
BW, BL = 47.0, 125.0                 # board: 47 across the jack strip (x), 125 long (y)
W, HGT = int(MX * 2 + BL * S + 40), int(MY + BW * S + 60)
mm = pcbnew.ToMM

board = pcbnew.LoadBoard(PCB)
FPS = {fp.GetReference(): fp for fp in board.GetFootprints()}
NOTE = {ref: (val, note) for ref, val, _, _, note in N.PARTS}


def V(x, y):
    """Board mm (x across, y along, y down) -> picture px: turned 90 deg so end A is on the left (top view, not mirrored)."""
    return MX + y * S, MY + (BW - x) * S


def pt(p):
    return V(mm(p.x), mm(p.y))


# ------------------------------------------------------------------ the steps (lowest parts first)
PORT_R = {k: ('R%d' % (9 + 4 * (k - 1)), 'R%d' % (10 + 4 * (k - 1)), 'R%d' % (11 + 4 * (k - 1)), 'R%d' % (8 + 4 * (k - 1)))
          for k in (1, 2, 3)}       # behind each jack, left to right on the board: IN2 220, EN 10, pull-down 100k, IN1 220
STEPS = [
    ('Resistors, power and angle filters', ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'], '#e8a33a'),
    ('Resistors behind the jacks', [r for k in (1, 2, 3) for r in PORT_R[k]], '#e8a33a'),
    ('Diodes', ['D1', 'D2', 'D3', 'D4'], '#555555'),
    ('Ceramic capacitors', ['C1', 'C2', 'C3', 'C4', 'C5', 'C6'], '#4a90d9'),
    ('ESP and USB-C sockets', ['J1', 'J2', 'J3'], '#333333'),
    ('JST headers: battery, charger, solar', ['J4', 'J5', 'J8'], '#f2f2f2'),
    ('RJ12 jacks', ['J9', 'J10', 'J11'], '#3a3a3a'),
    ('470 µF capacitor', ['C9'], '#2c5aa0'),
    ('Fuses (then fold them)', ['F1', 'F2', 'F3'], '#e0c040'),
]
LATER = {'TP1', 'TP2', 'TP3', 'TP4', 'TP5', 'H1', 'H2', 'H3'}

# resistor color codes (4-band carbon film / 5-band metal film)
BANDS = {'1M': ('brown black green gold', 'brown black black yellow brown'),
         '1k': ('brown black red gold', 'brown black black brown brown'),
         '220': ('red red brown gold', 'red red black black brown'),
         '10': ('brown black black gold', 'brown black black gold brown'),
         '100k': ('brown black yellow gold', 'brown black black orange brown')}
SILK = {'1M': '1M', '1k': '1k', '100nF': '100n', '10uF': '10u', '1N5819': '1N5819', '1N5920B 6.2V 3W': '6V2 3W Z',
        '220': '220', '10': '10', '100k': '100k', '470uF 10V': '470u', '0.75A PTC': 'PTC'}


def fab_items(fp):
    items = [g for g in fp.GraphicalItems() if isinstance(g, pcbnew.PCB_SHAPE) and g.GetLayer() == pcbnew.F_Fab]
    return items or [g for g in fp.GraphicalItems() if isinstance(g, pcbnew.PCB_SHAPE) and g.GetLayer() == pcbnew.F_CrtYd]


def bbox(fp):
    bb = None
    for g in fab_items(fp):
        b = g.GetBoundingBox()
        if bb is None:
            bb = pcbnew.BOX2I(b.GetPosition(), b.GetSize())
        else:
            bb.Merge(b)
    if bb is None:
        bb = fp.GetBoundingBox(False)
    x0, y0 = V(mm(bb.GetLeft()), mm(bb.GetTop()))
    x1, y1 = V(mm(bb.GetRight()), mm(bb.GetBottom()))
    return min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)


def shape_svg(g, col, wpx, fill='none'):
    t = g.GetShape()
    if t == pcbnew.SHAPE_T_SEGMENT:
        (a, b), (c, d) = pt(g.GetStart()), pt(g.GetEnd())
        return '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.1f"/>' % (a, b, c, d, col, wpx)
    if t == pcbnew.SHAPE_T_RECT:
        (a, b), (c, d) = pt(g.GetStart()), pt(g.GetEnd())
        return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" stroke="%s" stroke-width="%.1f"/>' % (
            min(a, c), min(b, d), abs(c - a), abs(d - b), fill, col, wpx)
    if t == pcbnew.SHAPE_T_CIRCLE:
        a, b = pt(g.GetCenter())
        return '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="%.1f"/>' % (a, b, mm(g.GetRadius()) * S, fill, col, wpx)
    if t == pcbnew.SHAPE_T_ARC:
        (a, b), (c, d), (e, f) = pt(g.GetStart()), pt(g.GetArcMid()), pt(g.GetEnd())
        return '<polyline points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="%.1f"/>' % (a, b, c, d, e, f, col, wpx)
    if t == pcbnew.SHAPE_T_POLY:
        ps = g.GetPolyShape()
        o = ps.Outline(0)
        pts = ' '.join('%.1f,%.1f' % pt(o.CPoint(i)) for i in range(o.PointCount()))
        return '<polygon points="%s" fill="%s" stroke="%s" stroke-width="%.1f"/>' % (pts, fill, col, wpx)
    return ''


def pad_svg(p, fill, stroke='#8a6d1f'):
    try:
        sz, sh = p.GetSize(pcbnew.F_Cu), p.GetShape(pcbnew.F_Cu)
    except TypeError:
        sz, sh = p.GetSize(), p.GetShape()
    cx, cy = pt(p.GetPosition())
    w, h = mm(sz.x) * S, mm(sz.y) * S
    rot = p.GetOrientationDegrees()
    if abs(rot) % 180 == 90:
        w, h = h, w
    dr = mm(p.GetDrillSize().x) * S / 2
    o = []
    if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        return '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#fff" stroke="#999" stroke-width="1"/>' % (cx, cy, dr)
    # the picture is turned 90 deg: swap the pad's width and height
    w, h = h, w
    if sh in (pcbnew.PAD_SHAPE_CIRCLE,) or (sh == pcbnew.PAD_SHAPE_OVAL and abs(w - h) < 0.01):
        o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="0.8"/>' % (cx, cy, w / 2, fill, stroke))
    else:
        rx = min(w, h) / 2 if sh == pcbnew.PAD_SHAPE_OVAL else (min(w, h) * 0.15 if sh == pcbnew.PAD_SHAPE_ROUNDRECT else 0)
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" stroke="%s" stroke-width="0.8"/>' % (
            cx - w / 2, cy - h / 2, w, h, rx, fill, stroke))
    o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#fff"/>' % (cx, cy, dr))
    return ''.join(o)


def text(x, y, s, size=11, col='#222', weight='normal', anchor='middle', rot=0, halo=True):
    h = ' stroke="#fff" stroke-width="3" paint-order="stroke"' if halo else ''
    tr = ' transform="rotate(%d %.1f %.1f)"' % (rot, x, y) if rot else ''
    return '<text x="%.1f" y="%.1f" font-size="%.1f" fill="%s" font-weight="%s" text-anchor="%s"%s%s>%s</text>' % (
        x, y, size, col, weight, anchor, h, tr, html.escape(s))


def base():
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica,Arial">' % (W, HGT),
         '<rect width="100%" height="100%" fill="#fff"/>']
    pts = [(0, 0), (BW, 0), (BW, 47.0), (27.0, 47.0), (27.0, BL), (0, BL)]
    o.append('<polygon points="%s" fill="#2f6b3a" stroke="#1d4426" stroke-width="2"/>' % ' '.join('%.1f,%.1f' % V(x, y) for x, y in pts))
    # silkscreen: the board's own lines and words, faint, so the picture looks like the board
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.F_SilkS:
            if isinstance(d, pcbnew.PCB_TEXT):
                x, y = pt(d.GetPosition())
                ang = d.GetTextAngleDegrees()
                o.append(text(x, y + 2, d.GetText(), mm(d.GetTextHeight()) * S * 1.05, '#e9efe9', rot=-90 if abs(ang) < 1 else 0,
                              halo=False))
            elif isinstance(d, pcbnew.PCB_SHAPE):
                o.append(shape_svg(d, '#cfdccf', 1.0))
    for fp in board.GetFootprints():
        for g in fp.GraphicalItems():
            if isinstance(g, pcbnew.PCB_SHAPE) and g.GetLayer() == pcbnew.F_SilkS:
                o.append(shape_svg(g, '#cfdccf', 1.0))
    # the trim band at the jack edge (step 0): 3-4 mm comes off for the V5 box
    (tx0, ty0), (tx1, ty1) = V(BW, 0), V(0, 4.0)
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#d62728" opacity="0.25"/>' % (tx0, ty0, tx1 - tx0, ty1 - ty0))
    for yy in (3.0, 4.0):
        (lx0, ly0), (lx1, ly1) = V(BW, yy), V(0, yy)
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#d62728" stroke-width="1.2" stroke-dasharray="5 3"/>' % (lx0, ly0, lx1, ly1))
    o.append(text(tx0 + 18, ty0 - 6, 'trim 3–4 mm', 11, '#d62728', 'bold', halo=False))
    o.append(text(MX - 10, MY + BW * S / 2, 'END A: ports', 13, '#333', 'bold', rot=-90, halo=False))
    o.append(text(MX + BL * S + 24, MY + (BW - 13.5) * S, 'END B: USB-C', 13, '#333', 'bold', rot=-90, halo=False))
    return o


def draw_part(o, ref, mode, col):
    fp = FPS[ref]
    x, y, w, h = bbox(fp)
    if mode == 'done':
        if ref == 'C9':
            o.extend(shape_svg(g, '#888', 1.2, '#bdbdbd') for g in fab_items(fp) if g.GetShape() == pcbnew.SHAPE_T_CIRCLE)
        else:
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#bdbdbd" stroke="#888" stroke-width="1" opacity="0.9"/>' % (x, y, w, h))
        return
    if mode == 'now':
        if ref == 'C9':
            o.extend(shape_svg(g, '#111', 2.0, col) for g in fab_items(fp) if g.GetShape() == pcbnew.SHAPE_T_CIRCLE)
        else:
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" stroke="#111" stroke-width="2" opacity="0.92"/>' % (x, y, w, h, col))
        for g in fab_items(fp):
            if g.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                o.append(shape_svg(g, '#111', 1.4))


def label(o, ref, step_idx):
    fp = FPS[ref]
    x, y, w, h = bbox(fp)
    val = SILK.get(fp.GetValue(), '')
    cx, cy = x + w / 2, y + h / 2
    if ref.startswith('R') and step_idx == 1:            # the jack resistors are thin and close: ref above, value inside
        o.append(text(cx, cy + 4, '%s  %s' % (ref, val), 10, '#000', 'bold'))
        return
    if ref == 'C9':                                      # round can over its pads: label beside it
        o.append(text(x + w + 8, cy - 2, ref, 12, '#000', 'bold', 'start'))
        o.append(text(x + w + 8, cy + 12, val, 11, '#000', anchor='start'))
        return
    o.append(text(cx, cy - 2, ref, 12, '#000', 'bold'))
    if val:
        o.append(text(cx, cy + 12, val, 11, '#000'))


def marks(o, ref):
    """Direction marks: + on the 470 uF, K (band) on the diodes, pin 1 on the sockets / headers."""
    fp = FPS[ref]
    p1 = [p for p in fp.Pads() if p.GetNumber() == '1']
    if not p1:
        return
    x, y = pt(p1[0].GetPosition())
    tag = {'C9': '+', 'D1': 'K', 'D2': 'K', 'D3': 'K', 'D4': 'K'}.get(ref, '1' if ref[0] == 'J' and ref not in ('J9', 'J10', 'J11') else None)
    if tag:
        o.append('<circle cx="%.1f" cy="%.1f" r="8" fill="#d62728" stroke="#fff" stroke-width="1.5"/>' % (x - 16, y))
        o.append(text(x - 16, y + 4, tag, 11, '#fff', 'bold', halo=False))


def picture(k, title, done, now, col, fname):
    o = base()
    o.append(text(MX, 26, 'Step %d: %s' % (k, title) if k else title, 18, '#111', 'bold', 'start', halo=False))
    o.append(text(MX, 46, 'top side, end A (jacks) left, end B (USB-C) right. Color: this step. Gray: done. Gold: holes still empty.',
                  12, '#555', anchor='start', halo=False))
    occupied = set(done) | set(now)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            o.append(pad_svg(p, '#bfbfbf' if fp.GetReference() in occupied else '#d9b44a',
                             '#888' if fp.GetReference() in occupied else '#8a6d1f'))
    for ref in done:
        draw_part(o, ref, 'done', None)
    for ref in now:
        draw_part(o, ref, 'now', col if isinstance(col, str) else col[ref])
    for ref in now:                                     # this step's holes on top of the part, so pin 1 is visible
        for p in FPS[ref].Pads():
            o.append(pad_svg(p, '#d9b44a'))
    for ref in now:
        marks(o, ref)
    for ref in now:
        label(o, ref, k - 1)
    o.append('</svg>')
    open(os.path.join(OUT, fname), 'w').write('\n'.join(o))
    return fname


def charger_picture():
    """The Comimark MCP73871 module (front, as in the owner's photo; positions scaled from it, about +/-0.5 mm) and where
    each of its wires goes on the PCB: the 4-wire J5 harness, the NTC pair, the capacitor."""
    k, ox, oy = 14.0, 330, 110
    bw, bh = 30.5, 31.5

    def P(x, y):
        return ox + k * x, oy + k * y
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="1010" font-family="Helvetica,Arial">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         text(20, 32, 'Charger module (MCP73871, 30.5 × 31.5 mm): wiring it for the PCB', 20, '#111', 'bold', 'start', halo=False),
         text(20, 56, 'Front side. Drawn from the listing photo, so positions are approximate. 4 wires to J5, 2 NTC wires, the capacitor.',
              13, '#444', anchor='start', halo=False)]
    x0, y0 = P(0, 0)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="10" fill="#1a1a1a"/>' % (x0, y0, bw * k, bh * k))
    chip = P(13.0, 13.0)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="#333" stroke="#666"/>' % (chip[0], chip[1], 4.5 * k, 4.5 * k))
    o.append(text(chip[0] + 2.25 * k, chip[1] + 2.5 * k, 'MCP73871', 11, '#aaa', halo=False))
    for i in range(3):
        lx, ly = P(5.5, 9.0 + 1.6 * i)
        o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="#c33"/>' % (lx, ly, 3.5 * k, 0.9 * k))
    for i in range(5):
        ex, ey = P(1.6, 7.6 + 2.54 * i)
        o.append('<circle cx="%.0f" cy="%.0f" r="9" fill="#c9a400"/><circle cx="%.0f" cy="%.0f" r="4" fill="#1a1a1a"/>' % (ex, ey, ex, ey))
    cx, cy = P(22.4, 3.1)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="none" stroke="#fff" stroke-width="2"/>' % (cx, cy, 3.8 * k, 5.0 * k))
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="#fff"/>' % (cx + 2.6 * k, cy, 1.2 * k, 5.0 * k))
    o.append(text(cx + 0.9 * k, cy + 3.0 * k, '+', 18, '#fff', 'bold', halo=False))
    tx, ty = P(23.2, 19.3)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="#555" stroke="#0a7a3a" stroke-width="3"/>' % (tx - 0.8 * k, ty - 0.5 * k, 1.6 * k, 1.0 * k))
    holes = [('GND', 4.2, 3.5, 'pin 1  G', '#222'), ('PWR', 8.8, 3.5, 'pin 6  P+', '#d62728'),
             ('GND', 3.8, 27.9, 'empty', '#999'), ('BATT', 8.8, 27.9, 'pin 2  B+', '#d62728'),
             ('LOAD', 20.8, 27.9, 'pin 4  L+', '#d62728'), ('GND', 25.6, 27.9, 'empty', '#999')]
    for name, x, y, to, c in holes:
        px, py = P(x, y)
        up = -1 if y < 15 else 1
        o.append('<circle cx="%.0f" cy="%.0f" r="24" fill="#c9a400"/><circle cx="%.0f" cy="%.0f" r="12" fill="#fff"/>' % (px, py, px, py))
        ty_ = py + up * 66
        o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="3"%s/>' % (
            px, py + up * 24, px, ty_ - up * 12, c, ' stroke-dasharray="4 4"' if c == '#999' else ''))
        # the pad's name beside its wire, not across it
        o.append('<text x="%.0f" y="%.0f" font-size="11" fill="#fff" font-weight="bold" text-anchor="end">%s</text>' % (
            px - 6, py + (-30 if up < 0 else 40), name))
        o.append('<rect x="%.0f" y="%.0f" width="74" height="22" rx="4" fill="#fff" stroke="%s" stroke-width="2"/>' % (px - 37, ty_ - 11, c))
        o.append(text(px, ty_ + 4, to, 12, c, 'bold', halo=False))

    def call(px, py, tx_, ty_, lines, c='#0a7a3a', anchor='start'):
        o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="2"/>' % (px, py, tx_, ty_, c))
        o.append('<circle cx="%.0f" cy="%.0f" r="4" fill="%s"/>' % (px, py, c))
        for i, t in enumerate(lines):
            o.append(text(tx_ + (6 if anchor == 'start' else -6), ty_ + 4 + 17 * i, t, 14 if i == 0 else 12,
                          c if i == 0 else '#333', 'bold' if i == 0 else 'normal', anchor, halo=False))
    call(cx + 1.9 * k, cy, 790, 110, ['Capacitor: LAST', 'long leg (+) in the hole on the + side,', 'legs bent 90° 1.5 mm from the body,',
                                     'lying over the LOAD / BATT edge,', 'held 2 mm up on a spacer while soldering'])
    call(tx + 0.8 * k, ty, 790, 300, ['THERM: remove the 103 (10 kΩ)', 'solder the NTC\'s own two leads (9 cm)', 'one to each pad, joints sleeved;',
                                     'the NTC bead gets taped on the cell'])
    lx, ly = P(20.8, 27.9)
    call(lx + 18, ly - 18, 790, 470, ['LOAD: soldered from UNDERNEATH', 'wire up through the hole from the back,', 'joint on top kept low (the capacitor',
                                     'lies 2.1 mm over it); wire flat under', 'the module'], '#d62728')
    ex, ey = P(1.6, 12.7)
    call(ex - 10, ey, 300, 330, ['Small edge pads: leave empty', '(CE, TE, PROG2, SEL)'], '#666', 'end')
    # the J5 housing
    by = oy + bh * k + 150
    # JST XH drawing (eXH.pdf p.2, PCB layout "viewed from the connector mounting surface"): with the LOCK SIDE toward
    # you, circuit 1 is on the right; so from the wire side with the lock side UP, pin 1 is on the LEFT. On this board
    # the header's lock wall (the one with the two slots, KiCad's -y side) faces end A.
    o.append(text(40, by - 34, 'J5 plug: one 6-pin JST-XH housing (XHP-6), 4 wires, pins 3 and 5 empty', 15, '#111', 'bold', 'start', halo=False))
    o.append(text(40, by - 14, 'Seen from the WIRE side, with the LOCK side up: pin 1 is on the LEFT (JST\'s XH drawing).', 13, '#d62728', 'bold', 'start', halo=False))
    cav = [('1', 'G', 'GND', '#222', '76 mm'), ('2', 'B+', 'BATT', '#d62728', '76 mm'), ('3', '·', 'empty', '#999', ''),
           ('4', 'L+', 'LOAD', '#d62728', '100 mm'), ('5', '·', 'empty', '#999', ''), ('6', 'P+', 'PWR', '#d62728', '52 mm')]
    hx0, hy0 = 60, by + 30
    hw = 110 * 6 + 16
    # the lock: a raised ramp along one long face, between the end walls
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="14" fill="#e3dccb" stroke="#555" stroke-width="2"/>' % (hx0 + 40, hy0 - 14, hw - 80))
    o.append(text(hx0 + hw / 2, hy0 - 20, 'LOCK side: the raised ramp along this face (it clicks into the header\'s slotted wall)', 12, '#555', 'bold', halo=False))
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="86" rx="6" fill="#f4f1e8" stroke="#555" stroke-width="2"/>' % (hx0, hy0, hw))
    for q, (pin, silk, pad, c, cut) in enumerate(cav):
        x_ = hx0 + 8 + 110 * q
        o.append('<rect x="%.0f" y="%.0f" width="100" height="70" rx="4" fill="#fff" stroke="#bbb"/>' % (x_, hy0 + 8))
        o.append(text(x_ + 50, hy0 + 28, 'pin %s (%s)' % (pin, silk), 12, '#444', halo=False))
        o.append(text(x_ + 50, hy0 + 50, pad, 15, c, 'bold', halo=False))
        o.append(text(x_ + 50, hy0 + 68, cut, 12, '#444', halo=False))
    # pin 1 arrow
    o.append('<polygon points="%.0f,%.0f %.0f,%.0f %.0f,%.0f" fill="#d62728"/>' % (hx0 + 58, hy0 + 100, hx0 + 48, hy0 + 116, hx0 + 68, hy0 + 116))
    o.append(text(hx0 + 58, hy0 + 134, 'PIN 1', 13, '#d62728', 'bold', halo=False))
    o.append(text(hx0 + 8 + 110 * 5 + 50, hy0 + 108, 'flat side (no ramp) down', 12, '#555', halo=False))
    ty0 = hy0 + 160
    for i, t in enumerate([
            'How to tell pin 1 for sure: before crimping anything in, push the EMPTY housing into the soldered J5. It only goes in one way:',
            'its lock ramp faces the header wall with the two slots, which on this board is the wall toward end A (the ESP side).',
            'Now look straight down: the cavity over the silkscreen G is pin 1. Put a marker dot on the housing beside it, pull it out, crimp.',
            'Lengths: the pre-crimped 152 mm JST leads cut to length (crimp end in the housing, bare end on the module), 1.5 leads per box.']):
        o.append(text(40, ty0 + 20 * i, t, 12, '#222' if i < 3 else '#444', 'bold' if i == 2 else 'normal', 'start', halo=False))
    o.append('</svg>')
    open(os.path.join(OUT, 'pcb-build-charger.svg'), 'w').write('\n'.join(o))
    return 'pcb-build-charger.svg'


def usb_picture():
    """The Cermant USB-C breakout (22.1 x 13.05) seen from its component side, its 6 pins, and the 2-wire lead to J3."""
    k, ox, oy = 18.0, 120, 230
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="660" font-family="Helvetica,Arial">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         text(20, 32, 'USB-C board: the 2-wire lead to J3', 20, '#111', 'bold', 'start', halo=False),
         text(20, 56, 'Component side. Only VBUS and GND are wired (the board has its 5.1 k CC resistors, the data pins aren\'t used).',
              13, '#444', anchor='start', halo=False)]
    bw, bd = 22.1, 13.05
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="6" fill="#1f4fa0"/>' % (ox, oy, bw * k, bd * k))
    sx = ox + (bw - 9.1) / 2 * k                                   # the socket on the front edge, sticking out 1.45
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="18" fill="#c8c8c8" stroke="#888" stroke-width="2"/>' % (
        sx, oy + (bd - 7.35 + 1.45) * k, 9.1 * k, 7.35 * k))
    o.append(text(ox + bw * k / 2, oy + (bd + 1.45) * k + 18, 'USB-C socket (out through end wall B)', 12, '#333', halo=False))
    names = ['VBUS', 'GND', 'CC1', 'D−', 'D+', 'CC2']
    py = oy + 1.04 * k
    for i, n in enumerate(names):
        px = ox + (bw / 2 - 6.35 + 2.54 * i) * k
        c = '#d62728' if n == 'VBUS' else '#222' if n == 'GND' else '#999'
        o.append('<rect x="%.0f" y="%.0f" width="22" height="22" fill="#c9a400" stroke="#8a6d1f"/>' % (px - 11, py - 11))
        o.append(text(px, py + 30, n, 12, '#fff', 'bold', halo=False))
        if n in ('VBUS', 'GND'):
            yy = oy - 50 - (0 if n == 'VBUS' else 30)
            o.append('<polyline points="%.0f,%.0f %.0f,%.0f %.0f,%.0f" fill="none" stroke="%s" stroke-width="5"/>' % (
                px, py - 11, px, yy, 620 + (0 if n == 'VBUS' else 0), yy, c))
    # the 2-pin male header on the far end
    o.append('<rect x="620" y="%.0f" width="30" height="60" fill="#222"/>' % (oy - 110))
    o.append(text(660, oy - 76, 'pin 2  GND (black)', 13, '#222', 'bold', 'start', halo=False))
    o.append(text(660, oy - 46, 'pin 1  VBUS (red)', 13, '#d62728', 'bold', 'start', halo=False))
    o.append(text(660, oy - 20, '2-pin male header, into J3 pins 1-2', 12, '#444', anchor='start', halo=False))
    o.append(text(660, oy - 4, '(J3 pin 1 = square pad, room-side edge)', 12, '#444', anchor='start', halo=False))
    y2 = oy + bd * k + 70
    for i, t in enumerate(['1. Clip the board\'s 6 header pins to 3 mm past their plastic (the charger sits beside them in the box).',
                           '2. Two wires, 65 mm each (the route in the box is 50 / 57 mm): red to VBUS, black to GND. Sleeve both joints.',
                           '3. Other ends: a 2-pin piece of male header, VBUS on pin 1, GND on pin 2. Mark the VBUS end.',
                           '4. Check: the pin names are printed beside the pins on the board; go by those, not by this drawing\'s order.']):
        o.append(text(40, y2 + 22 * i, t, 13, '#222', anchor='start', halo=False))
    o.append('</svg>')
    open(os.path.join(OUT, 'pcb-build-usb.svg'), 'w').write('\n'.join(o))
    return 'pcb-build-usb.svg'


def where(ref):
    x, y = mm(FPS[ref].GetPosition().x), mm(FPS[ref].GetPosition().y)
    return '%.0f mm from end A' % y


# ------------------------------------------------------------------ the markdown
def md():
    pics = []
    done = []
    for k, (title, refs, col) in enumerate(STEPS, 1):
        pics.append(picture(k, title, list(done), refs, col, 'pcb-build-%02d.svg' % k))
        done += refs
    allcol = {}
    for _, refs, col in STEPS:
        for r in refs:
            allcol[r] = col
    o = base()
    o.append(text(MX, 26, 'Finished: every part on the board', 18, '#111', 'bold', 'start', halo=False))
    for r, c in allcol.items():
        draw_part(o, r, 'now', c)
    for r in allcol:
        fp = FPS[r]
        x, y, w, h = bbox(fp)
        o.append(text(x + w / 2, y + h / 2 + 4, r, 10, '#000', 'bold'))
    o.append('</svg>')
    open(os.path.join(OUT, 'pcb-build-done.svg'), 'w').write('\n'.join(o))
    pics.append('pcb-build-done.svg')
    pics.append(charger_picture())
    pics.append(usb_picture())

    def rows(refs, cols):
        return '\n'.join('| ' + ' | '.join(c(r) for c in cols) + ' |' for r in refs)

    val = lambda r: NOTE[r][0]
    L = []
    a = L.append
    a('# Building the controller PCB, step by step')
    a('')
    a('For the carrier PCB, v2.1 ([hardware/pcb](../hardware/pcb/README.md)). Every picture, part list and position here is')
    a('generated from the real board file by [`tools/pcb_guide.py`](../tools/pcb_guide.py), so it matches the board you hold.')
    a('It is the PCB counterpart of the [dev board guide](dev-board-build.md): the circuit is the same, but there is no hand')
    a('wiring. Every part drops into its own holes, and the copper does the rest.')
    a('')
    a('**Order:** lowest parts first, so the board lies flat on the bench while you solder: resistors, diodes, small')
    a('capacitors, then the sockets and headers, the jacks, the big capacitor and the fuses (tallest) last. Then meter checks,')
    a('the leads, and plugging in. In each picture the step\'s parts are in color and labeled; done parts are gray; the')
    a('gold holes are still empty. End A (the RJ12 jacks) is on the left, end B (the USB-C socket) on the right.')
    a('')
    a('**The silkscreen prints each part\'s value** (1M, 220, 100n, 1N5819 …), not its reference, so you can match parts to the')
    a('board without the picture. The references (R1, D3 …) are only in this guide.')
    a('')
    a('**For the V5 box:** after each step, **trim every lead to 1.8 mm or less under the board**. The PCB sits 2.4 mm off')
    a('the box floor.')
    a('')
    a('## Parts for one board')
    a('')
    a('| Part | Qty | References | Step |')
    a('|---|---|---|---|')
    groups = {}
    for k, (title, refs, _) in enumerate(STEPS, 1):
        for r in refs:
            groups.setdefault(val(r), []).append((r, k))
    for v, lst in groups.items():
        a('| %s | %d | %s | %s |' % (v, len(lst), ', '.join(r for r, _ in lst), ', '.join(sorted({str(k) for _, k in lst}))))
    a('| ESP32-C6 SuperMini (male pins on, flashed on the bench) | 1 | plugs into J1 / J2 | 13 |')
    a('| USB-C breakout (Cermant) + its 2-wire lead to J3 | 1 | | 11 |')
    a('| MCP73871 charger module + 4-wire harness (6-pin XH housing) | 1 | J5 | 11 |')
    a('| 18650 cell with its JST-XH plug | 1 | J4 | 12 |')
    a('| Solar panel lead with a JST-ZH 2-pin plug (optional) | 1 | J8 | 11 |')
    a('')
    a('Nothing goes in the five square **test pads** (TP1 BAT+, TP2 5V, TP3 3V3, TP4 PWR, TP5 GND, a row near the middle and')
    a('one by the 470 µF). They\'re for the meter. The three big holes (H1–H3) take the box\'s M3 screws.')
    a('')
    a('## Which parts have a direction?')
    a('')
    a('| Part | Direction matters? | How to tell |')
    a('|---|---|---|')
    a('| Resistors, ceramic capacitors, fuses | **No** | either way round |')
    a('| **1N5819 diodes (D1–D3), 6.2 V zener (D4)** | **YES** | the **band** on the part goes over the **square pad**, where the silkscreen has its thick band line (red **K** in the pictures) |')
    a('| **470 µF capacitor (C9)** | **YES** | **long leg (+) in the square pad**, by the silkscreen\'s **+**; the can\'s stripe (−) on the shaded half of the circle |')
    a('| **Sockets J1, J2, J3** | fit either way, but **solder them straight** | pin 1 is the square pad |')
    a('| **JST headers J4, J5, J8** | **YES** | match the silkscreen outline. Before soldering, push the plug in and hold it over the board: the wires must land on the pads named on the silkscreen (J4: **−  +**, J5: **G  B+  ·  L+  ·  P+**, J8: **−  +**) |')
    a('| **RJ12 jacks** | fit only one way | two plastic pegs |')
    a('| **ESP32-C6** | **YES** | **chip up, its USB toward end B** (silkscreen: "ESP32-C6: chip up, USB this way"); its 5V pin in J1 pin 1 |')
    a('| **Battery** | **YES** | **red wire on +** of J4. Check with the meter before plugging in |')
    a('')
    a('A reversed diode just won\'t conduct. A reversed electrolytic, battery or charger plug can damage parts. Check those twice.')
    a('')
    a('![board](renders/pcb-build-done.png)')
    a('')

    # ---- step 1
    a('## Step 0: Trim the jack edge (for the V5 box)')
    a('')
    a('**v2.1 boards only** (back silkscreen "controller v2"). v2.2 boards come with this edge already in place: skip this step.')
    a('')
    a('Cut **3 to 4 mm** off the board\'s jack edge (end A, the 47 mm wide end), straight across. The V5 box (rev M) has the')
    a('jacks come through its end wall, which needs that edge out of the way. Any cut between 3 and 4 mm fits: the box locates')
    a('the board by its three screws, not by this edge.')
    a('')
    a('- Draw the line 3.5 mm in from the edge on both sides, then score it deeply along a straightedge on both faces and snap')
    a('  it over the edge of a bench, or cut with a fine-tooth saw. Sand the edge flat.')
    a('- Fiberglass dust is an irritant: cut it damp, or wear a mask, and wipe up afterward.')
    a('- Only the ground copper fill reaches that edge, no traces, so the cut can\'t break a connection. The jacks\' peg holes')
    a('  stay 2.8–3.8 mm in from the new edge.')
    a('- Do it **before** soldering anything, so the board lies flat and nothing gets knocked.')
    a('')
    a('## Step 1: Resistors under the ESP and in the power section (7)')
    a('')
    a('![step 1](renders/pcb-build-01.png)')
    a('')
    a('Flat on the board, legs bent at the body to the hole spacing (7.62 mm), either way round. The three 1k (angle filters)')
    a('sit where the ESP goes: they have to go in before its sockets.')
    a('')
    a('| Ref | Value | Bands (4-band / 5-band) | What it does |')
    a('|---|---|---|---|')
    for r in STEPS[0][1]:
        v = val(r)
        a('| %s | %s | %s / %s | %s |' % (r, v, BANDS[v][0], BANDS[v][1], NOTE[r][1]))
    a('')
    a('Not sure of a color? Measure it (1M reads 0.98–1.02 MΩ).')
    a('')
    # ---- step 2
    a('## Step 2: Resistors behind the jacks (12)')
    a('')
    a('![step 2](renders/pcb-build-02.png)')
    a('')
    a('Four behind each jack, in a row across the board, the same order at every port. Starting from the board\'s long straight')
    a('edge (bottom in the picture): **220, 10, 100k, 220** (silkscreen shows the values). Mixing up the 10 Ω and')
    a('a 220 Ω is the easy mistake: the 10 Ω powers the tilter\'s angle sensor, and through 220 Ω it won\'t read.')
    a('')
    a('| Port | 220 (IN2) | 10 (EN) | 100k (EN pull-down) | 220 (IN1) |')
    a('|---|---|---|---|---|')
    for k in (1, 2, 3):
        a('| %d | %s | %s | %s | %s |' % ((k,) + PORT_R[k]))
    a('')
    a('Bands: 220 **red red brown** (5-band: red red black black), 10 **brown black black** (brown black black gold),')
    a('100k **brown black yellow** (brown black black orange).')
    a('')
    # ---- step 3
    a('## Step 3: Diodes (4)')
    a('')
    a('![step 3](renders/pcb-build-03.png)')
    a('')
    a('**Band over the square pad** (the silkscreen draws the band). The zener is the bigger one (D4, "6V2 3W Z", its holes')
    a('10 mm apart).')
    a('')
    a('| Ref | Part | What it does |')
    a('|---|---|---|')
    for r in STEPS[2][1]:
        a('| %s | %s | %s |' % (r, val(r), {'D1': 'USB-C in → PWR (stops the panel feeding back into USB)',
                                             'D2': 'solar in → PWR (stops USB feeding back into the panel)',
                                             'D3': 'battery + → the ESP\'s 5V pin',
                                             'D4': 'clamps PWR at 6.2 V (a sunny panel\'s open-circuit voltage)'}[r]))
    a('')
    # ---- step 4
    a('## Step 4: Ceramic capacitors (6)')
    a('')
    a('![step 4](renders/pcb-build-04.png)')
    a('')
    a('Either way round, pushed down to the board. **C1 is the 10 µF ("106")**, the other five are 100 nF ("104"). C3–C5')
    a('sit under the ESP, beside the 1k resistors from step 1.')
    a('')
    a('| Ref | Value | Marking | What it does |')
    a('|---|---|---|---|')
    for r in STEPS[3][1]:
        a('| %s | %s | %s | %s |' % (r, val(r), '106' if val(r) == '10uF' else '104', NOTE[r][1]))
    a('')
    # ---- step 5
    a('## Step 5: ESP and USB-C sockets (3)')
    a('')
    a('![step 5](renders/pcb-build-05.png)')
    a('')
    a('1. **ESP sockets J1, J2 (10-way):** push both onto the ESP32-C6\'s pins, set the ESP and sockets into the board')
    a('   (chip up, USB toward end B), solder one pin at each end of each socket, check they sit flat and square, solder the')
    a('   rest, then lift the ESP back out. That way the two rows end up exactly the ESP\'s width apart.')
    a('2. **USB-C socket J3 (6-way)**, at end B. In the V5 box the USB-C board sits on the end wall, and a 2-wire lead plugs')
    a('   into **J3 pins 1 (VBUS) and 2 (GND)** (step 11), so only those two pins are used, but solder all six for strength.')
    a('   Pin 1 is the square pad, at the room-side edge.')
    a('')
    # ---- step 6
    a('## Step 6: JST headers (3)')
    a('')
    a('![step 6](renders/pcb-build-06.png)')
    a('')
    a('Three different headers, so no plug fits the wrong one:')
    a('')
    a('| Ref | Header | For | Pins (silkscreen) |')
    a('|---|---|---|---|')
    a('| J4 | JST-XH 2-pin (B2B-XH-A) | the 18650 | **−  +** (red wire on +) |')
    a('| J5 | JST-XH 6-pin (B6B-XH-A) | the charger harness | **G  B+  ·  L+  ·  P+** (pins 3 and 5 empty) |')
    a('| J8 | JST-ZH 2-pin (B2B-ZR), the small one | solar (optional) | **−  +** |')
    a('')
    a('**Orientation is everything here.** The headers only take a plug one way, so a header soldered backwards puts the')
    a('battery in backwards. On the two XH headers (J4, J5) **the wall with the two slots faces end A** (toward the ESP); the')
    a('silkscreen outline shows those slots. That\'s the side the plug\'s lock ramp clicks into. Then, before soldering, push the')
    a('actual plug in and hold it over the board: the cell\'s **red wire must sit over +**. Solder one pin, check it sits flat,')
    a('then the rest.')
    a('')
    # ---- step 7
    a('## Step 7: RJ12 jacks (3)')
    a('')
    a('![step 7](renders/pcb-build-07.png)')
    a('')
    a('Amphenol 87180-066LF, opening out over end A (past the trimmed edge). Their two pegs only fit one way. **Press each one')
    a('fully down and square** before soldering the six pins: in the box each jack slides through an opening cut to its own')
    a('outline with 0.3 mm to spare, so a tilted jack won\'t go in. Solder the two outer pins, check from the front, then the')
    a('rest.')
    a('')
    # ---- step 8
    a('## Step 8: 470 µF capacitor (1)')
    a('')
    a('![step 8](renders/pcb-build-08.png)')
    a('')
    a('C9, beside the jack strip. **Long leg (+) into the square pad** by the silkscreen\'s **+**. The silkscreen circle\'s')
    a('**shaded half is the − side**: the stripe on the can goes there. Push it right down: in the V5 box it has 2–3 mm under')
    a('the lid\'s groove.')
    a('')
    # ---- step 9
    a('## Step 9: Fuses, then fold them (3)')
    a('')
    a('![step 9](renders/pcb-build-09.png)')
    a('')
    a('F1–F3, the yellow 0.75 A resettable fuses (Bel 0ZRE0075FF), one behind each jack, either way round. Solder them')
    a('fully seated. **Then fold each one** for the box: bend both legs over **toward the ESP (end B)**, about **1.6 mm')
    a('below the body** (not at the body: the coating can crack), so the disc lies flat over its own four resistors, roughly')
    a('8–13 mm above the board. Fold them straight, not skewed: in the box, F1\'s disc ends 0.35 mm from a screw post and')
    a('F3\'s 1.3 mm from the 470 µF.')
    a('')
    # ---- step 10
    a('## Step 10: Meter checks, nothing plugged in')
    a('')
    a('Set the meter to beep (continuity). Black probe on **TP5 (GND)**:')
    a('')
    a('| Red probe on | Expect | If it beeps |')
    a('|---|---|---|')
    a('| TP1 BAT+ | no beep (a short chirp is the 470 µF charging, fine) | short on battery +: look at C9, the fuses, D3 |')
    a('| TP2 5V | no beep (the 10 µF may chirp) | short on the ESP\'s 5V: C1, D3, the sockets |')
    a('| TP3 3V3 | no beep | short on the ESP\'s 3V3: the sockets |')
    a('| TP4 PWR | no beep | short on the charger input: D1, D2, **D4 backwards** |')
    a('| each jack\'s pin 1 (battery +, after the fuse) | no beep | solder bridge at the jack |')
    a('')
    a('Then **diode mode**, red on TP4 (PWR), black on TP5 (GND): about 0.7–0.9 V is wrong (D4 is in backwards: its band must')
    a('be on the square pad); open ("OL") is right.')
    a('')
    a('Finally, look at the underside in good light for bridges between neighboring pads, especially the sockets and')
    a('jacks, and check every lead is trimmed to 1.8 mm or less.')
    a('')
    # ---- step 11
    a('## Step 11: Wiring the charger module, the USB-C board, the battery and solar')
    a('')
    a('Everything off the PCB connects by a plug. Build these leads on the bench; nothing is soldered to the PCB itself.')
    a('')
    a('**Cut list (one box):**')
    a('')
    a('| Lead | Wire | Cut | From → to |')
    a('|---|---|---|---|')
    a('| Charger LOAD | 22 AWG, pre-crimped JST lead | **100 mm** | J5 pin 4 → LOAD pad (from underneath) |')
    a('| Charger BATT | 22 AWG, pre-crimped JST lead | 76 mm (half a lead) | J5 pin 2 → BATT pad |')
    a('| Charger GND | 22 AWG, pre-crimped JST lead | 76 mm (half a lead) | J5 pin 1 → the GND pad next to PWR |')
    a('| Charger PWR | 22 AWG, pre-crimped JST lead | 52 mm (the LOAD lead\'s leftover) | J5 pin 6 → PWR pad |')
    a('| NTC | its own leads (9 cm) | as is, or trimmed to ~50 mm | THERM pads → NTC bead on the cell |')
    a('| USB-C lead | 22 AWG, red + black | 2 × 65 mm | USB-C board VBUS / GND → 2-pin male header in J3 pins 1–2 |')
    a('| Battery | the cell\'s own JST-XH lead (needs ≥ 45 mm) | as is | cell → J4 |')
    a('| Solar (optional) | the panel\'s flat 2-core cable | to suit | through end wall B → JST-ZH plug in J8 |')
    a('')
    a('The pre-crimped JST leads are 152 mm with a crimp on both ends: cut them so the crimp end goes in the J5 housing.')
    a('One lead and a half makes a harness.')
    a('')
    a('### 11a: Charger module (build it as one piece)')
    a('')
    a('![charger wiring](renders/pcb-build-charger.png)')
    a('')
    a('The order matters, because the capacitor lies over the LOAD pad and the THERM pads once it\'s on:')
    a('')
    a('1. **LOAD (J5 pin 4) first, from underneath:** push the bare end up through the LOAD hole from the back, solder it on')
    a('   top with a low joint (the capacitor will lie 2.1 mm over it), and lay the wire flat along the underside. In the box the')
    a('   module stands 2.4 mm off the floor and this wire runs under it.')
    a('2. **PWR (pin 6), BATT (pin 2), GND (pin 1, the GND next to PWR)** from the top. The module\'s GND pads are all one')
    a('   connection, so any GND works; the one next to PWR keeps the wire short.')
    a('3. **NTC:** remove the small **103** resistor beside the THERM label (it reads 10 kΩ before you take it off). Solder the')
    a('   NTC\'s own two leads (they come 9 cm long) straight to its two pads, either way round, joints sleeved. No extra wire.')
    a('   Lay the pair flat along the module toward the capacitor\'s leg end; they leave from under the capacitor there. The')
    a('   route to the cell\'s top is about 40 mm: trim the leads to ~50 mm, or coil the spare beside the cell.')
    a('4. **Capacitor, last:** bend both legs 90° about 1.5 mm from the body, so it lies over the LOAD / BATT edge. **Long leg')
    a('   (+) in the hole by the "+" mark** (the stripe on the can is −). Hold it 2 mm up on a spacer (a scrap of 1.6 mm board')
    a('   plus a business card) while you solder, so it sits clear of the parts on its legs.')
    a('5. **Check:** the capacitor\'s + leg beeps to the PWR pad, its − leg to GND.')
    a('6. **Crimp ends into the 6-pin housing:** pin 1 GND, pin 2 BATT, pin 4 LOAD, pin 6 PWR; 3 and 5 empty. If you have a')
    a('   pre-made 6-wire lead, pull the pin 3 and 5 wires out (lift the tab over each crimp with a pin) or cut them flush.')
    a('7. **Which end is pin 1:** from the wire side with the housing\'s **lock ramp up**, pin 1 is on the **left** (JST\'s XH')
    a('   drawing). To be sure, do it before crimping: push the **empty** housing into the soldered J5 (it only fits one way, lock')
    a('   ramp toward the header\'s slotted wall, which faces end A), look down, and mark the cavity over the silkscreen **G** with')
    a('   a dot. That\'s pin 1.')
    a('')
    a('The dev board wired all six pads (three − wires onto one GND rail). That\'s the same circuit: the PCB\'s J5 has room for one')
    a('GND, and the heavy motor current returns to the battery through the PCB, not through this wire.')
    a('')
    a('### 11b: USB-C board lead')
    a('')
    a('![USB-C lead](renders/pcb-build-usb.png)')
    a('')
    a('1. **Clip the USB-C board\'s six header pins to 3 mm** past their plastic (in the box the charger sits beside them).')
    a('2. **Two 22 AWG wires, 65 mm each:** red soldered to **VBUS**, black to **GND**. Go by the names printed beside the pins on')
    a('   your board. The dev board used the order VBUS, GND, CC1, D−, D+, CC2. Sleeve both joints.')
    a('3. Other ends onto a **2-pin piece of male header**: VBUS on one pin, GND on the other. Mark the VBUS end.')
    a('4. It plugs into **J3 pins 1 (VBUS) and 2 (GND)**. Pin 1 is J3\'s square pad, at the room-side edge.')
    a('5. CC1 / D− / D+ / CC2 stay unwired: the board has its own 5.1 kΩ CC resistors ("512"), so USB-C chargers give it 5 V.')
    a('')
    a('In the box the lead runs from those pins low along the room side, along the room-side wall, and up into J3.')
    a('')
    a('### 11c: Battery')
    a('')
    a('The 18650 plugs into **J4** with its own JST-XH lead: nothing to make. Before it ever goes in:')
    a('')
    a('1. Hold its plug against J4: the **red wire must sit over the silkscreen +**.')
    a('2. Meter on volts, red probe on the plug\'s red wire: **+3.0 to +4.2 V**. A minus sign means the plug is wired backwards:')
    a('   don\'t plug it in.')
    a('3. In the box, its lead leaves the cell\'s end-B face, goes down the PCB side and along the channel between the cell and')
    a('   the PCB\'s back edge to J4 (the two wires one above the other). It needs at least 45 mm.')
    a('4. **The NTC** from 11a gets taped onto the top of the cell, about 4 mm from its end-B end (Kapton tape or a dab of')
    a('   thermal glue).')
    a('')
    a('### 11d: Solar (optional)')
    a('')
    a('The panel\'s flat 2-core cable comes in through the slot in end wall B and gets a **JST-ZH 2-pin plug**: **− on pin 1**')
    a('(silk −), **+ on pin 2** (silk +). Check the panel\'s polarity with the meter in sun before crimping.')
    a('')
    # ---- step 12
    a('## Step 12: First power (no ESP yet)')
    a('')
    a('1. **Battery polarity:** before the cell goes on, hold its plug against J4 and check the red wire is over **+**. Then')
    a('   with the meter on volts, measure the plug: red probe on its red wire should read **+3.0 to +4.2 V**. A minus sign')
    a('   means the plug is wired backwards. Don\'t plug it in.')
    a('2. Plug the **charger harness into J5**, then the **battery into J4**. The battery reaches the board only through the')
    a('   charger, so J5 goes first.')
    a('3. Measure against **TP5 (GND)**:')
    a('')
    a('| Pad | Expect |')
    a('|---|---|')
    a('| TP1 BAT+ | about the cell\'s voltage (3.0–4.2 V) |')
    a('| TP2 5V | 0.1–0.4 V under TP1 (it comes through D3) |')
    a('| TP3 3V3 | 0 V (it comes from the ESP, not plugged in yet) |')
    a('| TP4 PWR | 0 V. Plug USB-C into the USB-C board: **4.6–4.8 V**, and the charger\'s LEDs light |')
    a('')
    a('If TP1 reads 0, check the J5 harness (pins 2 and 4) and that the cell isn\'t flat.')
    a('')
    # ---- step 13
    a('## Step 13: Plug in the ESP')
    a('')
    a('1. **Unplug the battery** (J4).')
    a('2. Flash the ESP32-C6 on the bench first (through its own USB-C). In the box there\'s no room for a cable.')
    a('3. Plug it into J1 / J2: **chip up, its USB toward end B**, its 5V pin in J1\'s square pad. Push it fully down.')
    a('4. Battery back in. **TP3 should read 3.3 V**, and the ESP boots.')
    a('')
    a('Then it goes into the box: [V5 assembly](controller-v5.md#assembly).')
    a('')
    a('## Regenerate this guide')
    a('')
    a('```bash')
    a('/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 tools/pcb_guide.py --png')
    a('```')
    a('')
    open(DOC, 'w').write('\n'.join(L))
    return pics


if __name__ == '__main__':
    names = md()
    if '--png' in sys.argv:
        for n in names:
            svg = os.path.abspath(os.path.join(OUT, n))
            head = open(svg).read(300)
            w_, h_ = (int(head.split('%s="' % k)[1].split('"')[0]) for k in ('width', 'height'))
            subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                            '--window-size=%d,%d' % (w_, h_), '--screenshot=' + svg[:-4] + '.png', 'file://' + svg],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print('wrote', ', '.join(names), 'and docs/pcb-build.md')
