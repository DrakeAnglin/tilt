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
# v2.1 outline (47 across the jack strip, 125 long, jack edge at y = 0): this guide is for the hand-trimmed v2.1 boards,
# while board.py now builds v2.2 with the jack edge already 3.5 mm in (TRIM)
V21_W, V21_L, V21_BODY_W, V21_BAR_D = 47.0, 125.0, 27.0, 47.0
W, HGT = int(MX * 2 + V21_L * S + 40), int(MY + V21_W * S + 60)
mm = pcbnew.ToMM

board = pcbnew.LoadBoard(PCB)
FPS = {fp.GetReference(): fp for fp in board.GetFootprints()}
NOTE = {ref: (val, note) for ref, val, _, _, note in N.PARTS}


def V(x, y):
    """Board mm (x across, y along, y down) -> picture px: turned 90 deg so end A is on the left (top view, not mirrored)."""
    return MX + y * S, MY + (V21_W - x) * S


def pt(p):
    return V(mm(p.x), mm(p.y))


# ------------------------------------------------------------------ the steps (lowest parts first)
PORT_R = {k: tuple(N.PORT_R[k][sig] for sig in ('IN2', 'EN', 'PD', 'IN1'))
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
    pts = [(0, 0), (V21_W, 0), (V21_W, V21_BAR_D), (V21_BODY_W, V21_BAR_D), (V21_BODY_W, V21_L), (0, V21_L)]
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
    (tx0, ty0), (tx1, ty1) = V(V21_W, 0), V(0, 4.0)
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#d62728" opacity="0.25"/>' % (tx0, ty0, tx1 - tx0, ty1 - ty0))
    for yy in (3.0, 4.0):
        (lx0, ly0), (lx1, ly1) = V(V21_W, yy), V(0, yy)
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#d62728" stroke-width="1.2" stroke-dasharray="5 3"/>' % (lx0, ly0, lx1, ly1))
    o.append(text(tx0 + 18, ty0 - 6, 'trim 3–4 mm', 11, '#d62728', 'bold', halo=False))
    o.append(text(MX - 10, MY + V21_W * S / 2, 'END A: ports', 13, '#333', 'bold', rot=-90, halo=False))
    o.append(text(MX + V21_L * S + 24, MY + (V21_W - 13.5) * S, 'END B: USB-C', 13, '#333', 'bold', rot=-90, halo=False))
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
    val = N.SHORT.get(fp.GetValue(), '')
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


def meter_picture():
    """Step 10: where each meter probe goes. Every part in gray; the probe points ringed and numbered in check order."""
    o = base()
    o.append(text(MX, 26, 'Step 10: Meter checks, where the probes go', 18, '#111', 'bold', 'start', halo=False))
    o.append(text(MX, 46, 'top side, nothing plugged in. Black probe stays on TP5 (GND). Red probe on each numbered point in turn.',
                  12, '#555', anchor='start', halo=False))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            o.append(pad_svg(p, '#bfbfbf', '#888'))
    for _, refs, _ in STEPS:
        for r in refs:
            draw_part(o, r, 'done', None)
    for r in ('TP1', 'TP2', 'TP3', 'TP4', 'TP5', 'H1', 'H2', 'H3'):
        for p in FPS[r].Pads():
            o.append(pad_svg(p, '#d9b44a'))

    def pad(ref, num='1'):
        return pt([p for p in FPS[ref].Pads() if p.GetNumber() == num][0].GetPosition())

    def ring(x, y, c, r=13):
        o.append('<circle cx="%.1f" cy="%.1f" r="%d" fill="none" stroke="%s" stroke-width="3"/>' % (x, y, r, c))

    def badge(x, y, s, c):
        o.append('<circle cx="%.1f" cy="%.1f" r="11" fill="%s" stroke="#fff" stroke-width="1.5"/>' % (x, y, c))
        o.append(text(x, y + 4.5, s, 12, '#fff', 'bold', halo=False))

    red, blk = '#d62728', '#111'
    # the test-point row near end B: labels run out to the right on their own line
    lx = MX + 112 * S
    for ref, n, name in (('TP5', 'B', 'TP5  GND: black probe'), ('TP4', '5', 'TP4  PWR'),
                         ('TP3', '4', 'TP3  3V3'), ('TP2', '3', 'TP2  5V')):
        x, y = pad(ref)
        c = blk if ref == 'TP5' else red
        ring(x, y, c)
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.6"/>' % (x + 13, y, lx - 14, y, c))
        badge(lx, y, n, c)
        o.append(text(lx + 18, y + 5, name, 13, c, 'bold', 'start'))
    # TP1 (battery +) by the jacks
    x, y = pad('TP1')
    ring(x, y, red)
    badge(x + 26, y - 22, '2', red)
    o.append(text(x + 42, y - 17, 'TP1  BAT+', 13, red, 'bold', 'start'))
    # each fuse's jack-side leg = that jack's pin 1 (battery + after the fuse)
    for ref, n in (('F3', '6'), ('F2', '7'), ('F1', '8')):
        x, y = pad(ref, '2')
        ring(x, y, red, 11)
        badge(x + 24, y + 2, n, red)
        o.append(text(x + 12, y + 32, '%s leg = port %s pin 1' % (ref, ref[1]), 12, red, 'bold', 'start'))
    # legend in the empty corner over the narrow part of the board
    gx, gy = MX + 52 * S, MY + 18
    rows = [('B', blk, 'Black probe on TP5 (GND) for every check'),
            ('2–8', red, 'Beep mode: red probe on each. Expect NO beep (a short chirp at 2 and 3 is the caps charging)'),
            ('D', '#7a3fb0', 'Diode mode: red on TP4, black on TP5. "OL" is right; 0.7–0.9 V means D4 is backwards'),
            ('', '#555', 'Then flip the board: look for solder bridges, leads trimmed to 1.8 mm or less')]
    for i, (n, c, s_) in enumerate(rows):
        yy = gy + i * 26
        if n:
            o.append('<rect x="%.1f" y="%.1f" width="34" height="20" rx="10" fill="%s"/>' % (gx, yy - 14, c))
            o.append(text(gx + 17, yy + 1, n, 12, '#fff', 'bold', halo=False))
        o.append(text(gx + 44, yy + 1, s_, 12, '#222', anchor='start', halo=False))
    x4, y4 = pad('TP4')
    x5, y5 = pad('TP5')
    o.append('<path d="M%.1f %.1f C %.1f %.1f, %.1f %.1f, %.1f %.1f" fill="none" stroke="#7a3fb0" stroke-width="2" stroke-dasharray="4 3"/>'
             % (x4 - 13, y4, x4 - 45, y4, x5 - 45, y5, x5 - 13, y5))
    badge(x4 - 52, (y4 + y5) / 2, 'D', '#7a3fb0')
    o.append('</svg>')
    open(os.path.join(OUT, 'pcb-build-meter.svg'), 'w').write('\n'.join(o))
    return 'pcb-build-meter.svg'


LETTERS = ['G', 'B+', '', 'L+', '', 'P+']          # printed on the board beside the charger socket, in order ('' = unmarked)


def housing_h(o, hx, hy, cav, w=80):
    """The charger plug as a row of 6 slots, each named by the letter printed beside it on the board (G B+ · L+ · P+),
    so there's no pin numbering to get backwards. Returns each slot's wire exit point."""
    n = len(cav)
    W, H = n * w + 10, 78
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="#f4f1e8" stroke="#555" stroke-width="2"/>' % (hx, hy, W, H))
    out = {}
    for q, (pin, what, c) in enumerate(cav):
        x_ = hx + 5 + w * q
        o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="#fff" stroke="#bbb"/>' % (x_, hy + 6, w - 6, H - 12))
        o.append(text(x_ + (w - 6) / 2, hy + 32, LETTERS[q] or '(none)', 18 if LETTERS[q] else 12, '#111' if LETTERS[q] else '#999', 'bold', halo=False))
        o.append(text(x_ + (w - 6) / 2, hy + 56, what, 12, c, 'bold', halo=False))
        out[pin] = (x_ + (w - 6) / 2, hy + H)
    return out


def plug_picture():
    """Where each charger-plug wire goes, shown ON THE BOARD: the end-B corner from the real board file, with the letters
    printed beside the charger socket (G B+ · L+ · P+) and the battery socket."""
    Z, ox, oy, x0b, y0b = 24.0, 60, 110, 27.0, 97.0

    def P(x, y):                                    # board mm -> px, same turn as the other pictures (end B to the right)
        return ox + (y - y0b) * Z, oy + (x0b - x) * Z
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1560" height="960" font-family="Helvetica,Arial">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         text(20, 34, 'Charger plug: which wire goes in which slot, shown on the board', 20, '#111', 'bold', 'start', halo=False),
         text(20, 58, 'Looking down on the parts side, USB-C end on the right. Each wire sits next to the letter printed on the board.',
              13, '#444', anchor='start', halo=False)]
    (bx0, by0), (bx1, by1) = P(x0b, y0b), P(0, 125.0)
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="#2f6b3a" stroke="#1d4426" stroke-width="2"/>' % (bx0, by0, bx1 - bx0, by1 - by0))

    def pad(x, y, sq=False, col='#d9b44a'):
        cx, cy = P(x, y)
        if sq:
            o.append('<rect x="%d" y="%d" width="26" height="26" rx="3" fill="%s" stroke="#8a6d1f" stroke-width="2"/>' % (cx - 13, cy - 13, col))
        else:
            o.append('<circle cx="%d" cy="%d" r="13" fill="%s" stroke="#8a6d1f" stroke-width="2"/>' % (cx, cy, col))
        o.append('<circle cx="%d" cy="%d" r="5" fill="#555"/>' % (cx, cy))
        return cx, cy
    # charger socket outline and its 6 pins, with the board's letters beside them
    (sx0, sy0), (sx1, sy1) = P(17.9, 110.9), P(0.6, 116.1)
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="#f2f2f2" opacity="0.25" stroke="#e9efe9" stroke-width="2"/>' % (
        min(sx0, sx1), min(sy0, sy1), abs(sx1 - sx0), abs(sy1 - sy0)))
    lab = P(9.25, 111.6)
    o.append(text(lab[0] - 34, lab[1] + 5, 'CHARGER', 15, '#e9efe9', 'bold', rot=-90, halo=False))
    dest = [('wire to the charger\'s G', '#222'), ('BAT splice wire', '#d62728'), ('empty (no letter)', '#999'),
            ('BAT splice wire', '#d62728'), ('empty (no letter)', '#999'), ('wire to the charger\'s VIN', '#d62728')]
    for k, (x, letter) in enumerate(zip((3.0, 5.5, 8.0, 10.5, 13.0, 15.5), LETTERS)):
        cx, cy = pad(x, 113.5, sq=(k == 0))
        tx, ty = P(x, 118.4)
        if letter:
            o.append('<rect x="%d" y="%d" width="40" height="26" rx="4" fill="#fff"/>' % (tx - 20, ty - 13))
            o.append(text(tx, ty + 7, letter, 18, '#111', 'bold', halo=False))
        d, c = dest[k]
        o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="%d"%s/>' % (
            tx + 22, cy, bx1 + 30, cy, c, 4 if c != '#999' else 2, ' stroke-dasharray="6 5"' if c == '#999' else ''))
        o.append(text(bx1 + 40, cy + 5, d, 15, c, 'bold', 'start', halo=False))
    # battery socket, solar socket, test pads (for orientation)
    for x, sgn in ((17.5, '−'), (20.0, '+')):
        cx, cy = pad(x, 105.0, sq=(sgn == '−'))
        tx, ty = P(x, 109.8)
        o.append(text(tx, ty + 6, sgn, 18, '#fff', 'bold', halo=False))
    bl = P(18.75, 101.2)
    o.append(text(bl[0], bl[1], 'BATTERY plug', 13, '#ffd', 'bold', rot=-90, halo=False))
    for x in (22.0, 23.5):
        pad(x, 113.5)
    sl = P(22.75, 110.0)
    o.append(text(sl[0], sl[1], 'SOLAR', 12, '#e9efe9', 'bold', rot=-90, halo=False))
    for x, nm in ((13.5, '5V'), (17.0, '3V3'), (20.5, 'PWR'), (24.0, 'GND')):
        cx, cy = P(x, 99.0)
        o.append('<rect x="%d" y="%d" width="22" height="22" fill="#d9b44a" stroke="#8a6d1f"/>' % (cx - 11, cy - 11))
        o.append(text(cx - 18, cy + 5, nm, 12, '#fff', 'bold', 'end', halo=False))
    for k_, t in enumerate([
            'Plug the charger plug in, look straight down, and check each wire against the letter beside it:',
            'G = the wire to the charger\'s G.   B+ and L+ = the two BAT splice wires.   P+ = the wire to the charger\'s VIN.',
            'The two slots with no letter stay empty. If a wire doesn\'t sit at its letter, unplug and move it before the battery goes in.',
            'Then the beep check (meter on beep): charger G to GND, charger BAT to BAT+, charger VIN to PWR: all beep.']):
        o.append(text(40, 830 + 26 * k_, t, 14, '#d62728' if k_ == 2 else '#222', 'bold' if k_ in (0, 3) else 'normal', 'start', halo=False))
    o.append('</svg>')
    open(os.path.join(OUT, 'pcb-build-plug.svg'), 'w').write('\n'.join(o))
    return 'pcb-build-plug.svg'


def charger_picture():
    """The Adafruit 6092 (bq25185) charger, used as a charger ONLY, and its 3-wire J5 harness. Drawn as a wiring diagram:
    the pad names are the ones printed on the board (Adafruit's guide); positions on the real board differ, so go by the
    printed labels."""
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1260" height="1200" font-family="Helvetica,Arial">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         text(20, 32, 'Charger: Adafruit 6092 (bq25185), wired as a charger only', 20, '#111', 'bold', 'start', halo=False),
         text(20, 56, 'Top view, drawn from Adafruit\'s photo (not to scale). Go by the name printed beside each pad.', 13, '#444', anchor='start', halo=False)]
    # the module, top view, drawn from Adafruit's photo: USB-C at the top end, the screw terminal at the bottom end, the
    # JST-PH socket just below the USB-C, and the row of 8 pads down the left edge (VIN at the USB end, EN at the terminal end)
    mx0, my0, mw, mh = 700, 330, 300, 470
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="16" fill="#1a1a1a" stroke="#c9c9a0" stroke-width="3"/>' % (mx0, my0, mw, mh))
    for hx_, hy_ in ((mx0 + 30, my0 + 30), (mx0 + mw - 30, my0 + 30), (mx0 + 30, my0 + mh - 30), (mx0 + mw - 30, my0 + mh - 30)):
        o.append('<circle cx="%d" cy="%d" r="18" fill="#c9a400"/><circle cx="%d" cy="%d" r="11" fill="#fff"/>' % (hx_, hy_, hx_, hy_))
    # USB-C, sticking out of the top end
    o.append('<rect x="%d" y="%d" width="110" height="80" rx="14" fill="#c8c8c8" stroke="#777" stroke-width="2"/>' % (mx0 + 95, my0 - 18))
    o.append('<rect x="%d" y="%d" width="70" height="14" rx="7" fill="#555"/>' % (mx0 + 115, my0 - 8))
    o.append(text(mx0 + mw / 2, my0 - 30, 'USB-C (top end): plug USB power in HERE', 13, '#333', 'bold', halo=False))
    # JST-PH socket below the USB-C, toward the right
    o.append('<rect x="%d" y="%d" width="90" height="62" rx="4" fill="#f1e2c8" stroke="#a89070" stroke-width="2"/>' % (mx0 + 175, my0 + 85))
    o.append(text(mx0 + 220, my0 + 121, 'JST-PH', 12, '#6b5a40', 'bold', halo=False))
    o.append(text(mx0 + mw + 14, my0 + 112, 'JST-PH battery socket:', 12, '#666', 'bold', 'start', halo=False))
    o.append(text(mx0 + mw + 14, my0 + 128, 'not used (the battery is on J4)', 12, '#666', anchor='start', halo=False))
    # LEDs C and F, left of the socket
    for k_, (lab, col) in enumerate((('C', '#ff8c00'), ('F', '#d62728'))):
        o.append('<circle cx="%d" cy="%d" r="7" fill="%s"/>' % (mx0 + 150, my0 + 96 + 24 * k_, col))
        o.append(text(mx0 + 132, my0 + 101 + 24 * k_, lab, 12, '#fff', 'bold', 'end', halo=False))
    o.append(text(mx0 + mw + 14, my0 + 168, 'orange C = charging', 12, '#c06000', 'bold', 'start', halo=False))
    o.append(text(mx0 + mw + 14, my0 + 184, 'red F = fault: unplug', 12, '#d62728', 'bold', 'start', halo=False))
    o.append('<rect x="%d" y="%d" width="40" height="40" fill="#222" stroke="#444"/>' % (mx0 + 150, my0 + 230))   # the chip
    # the 8-pad row down the left edge, names printed beside each pad
    used = {'VIN': ('#d62728', 'pin 6 PWR'), 'G': ('#222', 'pin 1 GND'), 'BAT': ('#d62728', 'pin 2 BATT')}
    pads = []
    for k_, name in enumerate(('VIN', 'VU', 'D−', 'D+', 'G', 'BAT', '3V', 'EN')):
        y = 110 + 40 * k_
        on = name in used
        o.append('<circle cx="%d" cy="%d" r="13" fill="%s"/><circle cx="%d" cy="%d" r="6" fill="#fff"/>' % (
            mx0 + 28, my0 + y, '#c9a400' if on else '#8a7a40', mx0 + 28, my0 + y))
        o.append(text(mx0 + 50, my0 + y + 5, name, 14, '#fff' if on else '#999', 'bold', 'start', halo=False))
        if on:
            o.append('<circle cx="%d" cy="%d" r="18" fill="none" stroke="%s" stroke-width="3"/>' % (mx0 + 28, my0 + y, '#ffd24a'))
            pads.append((name, used[name][0], y, used[name][1]))
    o.append(text(mx0 + 100, my0 + 205, 'VU, D−, D+: USB-C side, empty', 11, '#aaa', anchor='start', halo=False))
    o.append(text(mx0 + 100, my0 + 375, '3V, EN: empty', 11, '#aaa', anchor='start', halo=False))
    # screw terminal at the bottom end: 4.5V, −, 3V (4.5V on the pad-row side)
    for k_, name in enumerate(('4.5V', '−', '3V')):
        x_ = mx0 + 72 + 54 * k_
        o.append('<rect x="%d" y="%d" width="50" height="50" fill="#2e9e4f" stroke="#145a2a" stroke-width="2"/>' % (x_, my0 + mh - 66))
        o.append('<circle cx="%d" cy="%d" r="13" fill="#c8c8c8" stroke="#777"/>' % (x_ + 25, my0 + mh - 41))
        o.append(text(x_ + 25, my0 + mh + 22, name, 14, '#2e7a3f', 'bold', halo=False))
    o.append(text(mx0 + mw / 2, my0 + mh + 46, 'Screw terminal (bottom end): all three stay EMPTY', 13, '#2e7a3f', 'bold', halo=False))
    o.append(text(mx0 + mw / 2, my0 + mh + 64, '(the battery feeds the board directly; see the J5 splice)', 12, '#555', halo=False))
    # the J5 plug, as you hold it, wires down to the module's pads
    hx, hy = 110, 170
    cav = [('1', 'GND', '#222'), ('2', 'BATT', '#d62728'), ('3', 'empty', '#999'),
           ('4', 'BATT', '#d62728'), ('5', 'empty', '#999'), ('6', 'PWR', '#d62728')]
    o.append(text(40, hy - 50, 'Charger plug: each slot named by the letter printed beside it on the board', 14, '#111', 'bold', 'start', halo=False))
    o.append(text(40, hy - 30, 'Go by the board picture (pcb-build-plug) to put each wire in the right slot', 12, '#d62728', 'bold', 'start', halo=False))
    ex = housing_h(o, hx, hy, cav, w=70)
    sx, sy = (ex['2'][0] + ex['4'][0]) / 2, hy + 190            # the splice: slots 2 and 4 joined, one wire on to BAT
    for name, col, y, lab in pads:
        ty = my0 + y
        if name == 'BAT':
            for pin in ('2', '4'):
                x0, y0 = ex[pin]
                o.append('<path d="M%d %d C %d %d, %d %d, %d %d" fill="none" stroke="%s" stroke-width="4"/>' % (
                    x0, y0, x0, y0 + 60, sx, sy - 60, sx, sy, col))
            o.append('<path d="M%d %d C %d %d, %d %d, %d %d" fill="none" stroke="%s" stroke-width="4"/>' % (
                sx, sy, sx, sy + 120, mx0 - 200, ty, mx0 - 16, ty, col))
            o.append('<rect x="%d" y="%d" width="18" height="34" rx="6" fill="#333"/>' % (sx - 9, sy - 17))
            o.append(text(sx + 16, sy + 5, 'splice', 12, '#333', 'bold', 'start'))
            continue
        x0, y0 = ex[{'G': '1', 'VIN': '6'}[name]]
        o.append('<path d="M%d %d C %d %d, %d %d, %d %d" fill="none" stroke="%s" stroke-width="4"/>' % (
            x0, y0, x0, y0 + 160, mx0 - 220, ty, mx0 - 16, ty, col))
    o.append(text(40, hy + 560, 'pins 2 and 4 both carry BATT: one splice, two crimps (11a)', 12, '#666', anchor='start', halo=False))
    ty0 = 960
    for k_, t in enumerate([
            '3 pads wired: GND (pin 1) to G, BATT (pins 2 + 4, spliced) to BAT, PWR (pin 6) to VIN. Nothing else is wired.',
            'No temperature probe and no big capacitor with this module (the old one needed both).',
            'Orange C on = charging; off = full (or its fixed 6-hour charge limit: unplug and replug power to restart).',
            'Red F = fault: unplug and check the wiring.',
            'USB plugs into this module\'s USB-C. The PCB\'s USB-C board and J3 are not used.',
            'USB in the module also shows on VIN (about 4.35 V, measured), so the ESP can see USB is plugged in.',
            'Do not plug in USB-C and the solar panel at the same time (not yet checked how the module joins them).']):
        o.append(text(40, ty0 + 24 * k_, t, 13, '#d62728' if k_ >= 4 else '#222', 'bold' if k_ == 0 else 'normal', 'start', halo=False))
    o.append('</svg>')
    open(os.path.join(OUT, 'pcb-build-charger.svg'), 'w').write('\n'.join(o))
    return 'pcb-build-charger.svg'


def splice_picture():
    """The J5 plug's battery splice: slot 2 and slot 4 both carry BATT, joined in one splice that goes on to the 6092's BAT.
    The battery then feeds the board directly (J4 -> J5 pin 2 -> splice -> J5 pin 4 -> the board supply), with no change
    to the PCB."""
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="600" font-family="Helvetica,Arial">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         text(20, 32, 'J5 splice: slots 2 and 4 joined (no change to the PCB)', 20, '#111', 'bold', 'start', halo=False),
         text(20, 56, 'The battery then feeds the whole board directly; the charger only charges it.', 13, '#444', anchor='start', halo=False)]
    hx, hy = 90, 140
    cav = [('1', 'GND', '#222'), ('2', 'BATT', '#d62728'), ('3', 'empty', '#999'), ('4', 'BATT', '#d62728'),
           ('5', 'empty', '#999'), ('6', 'PWR', '#d62728')]
    o.append(text(40, hy - 30, 'Charger plug: each slot named by the letter printed beside it on the board', 14, '#d62728', 'bold', 'start', halo=False))
    ex = housing_h(o, hx, hy, cav, w=80)
    sx, sy = (ex['2'][0] + ex['4'][0]) / 2, hy + 190
    for pin in ('2', '4'):
        x0, y0 = ex[pin]
        o.append('<path d="M%d %d C %d %d, %d %d, %d %d" fill="none" stroke="#d62728" stroke-width="5"/>' % (x0, y0, x0, y0 + 60, sx, sy - 60, sx, sy - 14))
    o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#d62728" stroke-width="5"/>' % (sx, sy + 14, sx, sy + 90))
    o.append('<rect x="%d" y="%d" width="22" height="40" rx="8" fill="#333"/>' % (sx - 11, sy - 20))
    o.append(text(sx - 22, sy + 5, 'splice: soldered, heat-shrink over it', 13, '#333', 'bold', 'end'))
    o.append(text(sx, sy + 110, 'to the 6092\'s BAT', 14, '#d62728', 'bold'))
    for pin, lab, c in (('1', 'to G', '#222'), ('6', 'to VIN', '#d62728')):
        x0, y0 = ex[pin]
        o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="4"/>' % (x0, y0, x0, sy + 90, c))
        o.append(text(x0, sy + 110, lab, 14, c, 'bold'))
    for k_, t in enumerate([
            'Two short legs with XH crimp pins (in slots 2 and 4) and the wire to BAT, all 22 AWG, joined in one soldered splice.',
            'Keep the two crimped legs short (about 30 mm), so the motor current\'s loop through the plug is short.',
            'Push both crimps in until they click, then tug-test each one. A loose crimp here cuts power to the whole board.',
            'With the J5 plug out, the board has no power: the battery reaches it only through this plug.',
            'Check: battery in J4, J5 plugged in, TP1 reads the battery voltage.']):
        o.append(text(40, 480 + 22 * k_, t, 13, '#d62728' if k_ in (2, 3) else '#222', 'bold' if k_ == 0 else 'normal', 'start', halo=False))
    o.append('</svg>')
    open(os.path.join(OUT, 'pcb-build-splice.svg'), 'w').write('\n'.join(o))
    return 'pcb-build-splice.svg'


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
    pics.append(meter_picture())
    pics.append(plug_picture())
    pics.append(splice_picture())
    pics.append(charger_picture())

    def rows(refs, cols):
        return '\n'.join('| ' + ' | '.join(c(r) for c in cols) + ' |' for r in refs)

    val = lambda r: NOTE[r][0]
    L = []
    a = L.append
    a('# Building the controller PCB, step by step')
    a('')
    a('For the carrier PCB, v2.1 and v2.2 ([hardware/pcb](../hardware/pcb/README.md)); on v2.2 skip step 0. Every picture, part list and position here is')
    a('generated from the real board file by [`tools/pcb_guide.py`](../tools/pcb_guide.py), so it matches the board you hold.')
    a('The circuit was proven on a hand-wired dev board first. On the PCB there is no hand')
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
    a('**For the box:** after each step, **trim every lead to 1.8 mm or less under the board**. The PCB sits 2.4 mm off')
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
        a('| %s | %d | %s | %s |' % (v + (' (optional, not used with the 6092)' if any(r == 'J3' for r, _ in lst) else ''), len(lst),
                                   ', '.join(r for r, _ in lst), ', '.join(sorted({str(k) for _, k in lst}))))
    a('| ESP32-C6 SuperMini (male pins on, flashed on the bench) | 1 | plugs into J1 / J2 | 13 |')
    a('| Adafruit 6092 charger (bq25185), charging only, + 3-wire harness (6-pin XH housing) | 1 | J5 | 11 |')
    a('| JST-XH crimp pins on 22 AWG wire (or the optional pre-crimped leads) for the J5 harness, + heat-shrink | 4 | J5 plug | 11 |')
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
    a('| **JST headers J4, J5, J8** | **YES** | match the silkscreen outline. Before soldering, push the plug in and hold it over the board: the wires must land on the pads named on the silkscreen (J4: **−  +**, J5: **G  B+  (blank)  L+  (blank)  P+**, J8: **−  +**) |')
    a('| **RJ12 jacks** | fit only one way | two plastic pegs |')
    a('| **ESP32-C6** | **YES** | **chip up, its USB toward end B** (silkscreen: "ESP32-C6: chip up, USB this way"); its 5V pin in J1 pin 1 |')
    a('| **Battery** | **YES** | **red wire on +** of J4. Check with the meter before plugging in |')
    a('')
    a('A reversed diode just won\'t conduct. A reversed electrolytic, battery or charger plug can damage parts. Check those twice.')
    a('')
    a('![board](renders/pcb-build-done.png)')
    a('')

    # ---- step 1
    a('## Step 0: Trim the jack edge (for the box)')
    a('')
    a('**v2.1 boards only** (back silkscreen "controller v2"). v2.2 boards come with this edge already in place: skip this step.')
    a('')
    a('Cut **3 to 4 mm** off the board\'s jack edge (end A, the 47 mm wide end), straight across. The controller box has the')
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
    a('**Out of 100 nF?** Any **ceramic** capacitor from 47 nF to 1 µF works in C2–C6 ("473", "104", "224", "474", "105"),')
    a('and they can be mixed: each one works on its own. They only smooth a reading; the value changes how fast a reading')
    a('settles, never the number it settles to. Use the same value on C3–C5 if you can, so the three ports respond alike. A')
    a('missing C2–C6 doesn\'t stop anything working (the readings are just noisier). **Not** an electrolytic like 100 µF, and')
    a('**C1 must be the 10 µF.**')
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
    a('2. **USB-C socket J3 (6-way): optional, not used.** USB now plugs into the charger\'s own USB-C (step 11), so nothing')
    a('   plugs into J3. Leave it empty, or solder it anyway (harmless; it keeps the option of the old USB-C board).')
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
    a('| J5 | JST-XH 6-pin (B6B-XH-A) | the charger harness | **G  B+  (blank)  L+  (blank)  P+** (pins 3 and 5 empty; with the 6092, pins 2 and 4 both get the battery wire: step 11) |')
    a('| J8 | JST-ZH 2-pin (B2B-ZR), the small one | solar (optional) | **−  +** |')
    a('')
    a('**Orientation is everything here.** The headers only take a plug one way, so a header soldered backwards puts the')
    a('battery in backwards. On the two XH headers (J4, J5) **the wall with the two slots faces end A** (toward the ESP); the')
    a('silkscreen outline shows those slots. That\'s the side the plug\'s two little hooks click into. Then, before soldering, push the')
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
    a('**shaded half is the − side**: the stripe on the can goes there. Push it right down: in the box it has 2–3 mm under')
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
    a('![where the probes go](renders/pcb-build-meter.png)')
    a('')
    a('Set the meter to beep (continuity). Black probe on **TP5 (GND)** (black ring "B" in the picture) for every check;')
    a('the red probe goes on each numbered point in turn:')
    a('')
    a('| # | Red probe on | Expect | If it beeps |')
    a('|---|---|---|---|')
    a('| 2 | TP1 BAT+ | no beep (a short chirp is the 470 µF charging, fine) | short on battery +: look at C9, the fuses, D3 |')
    a('| 3 | TP2 5V | no beep (the 10 µF may chirp) | short on the ESP\'s 5V: C1, D3, the sockets |')
    a('| 4 | TP3 3V3 | no beep | short on the ESP\'s 3V3: the sockets |')
    a('| 5 | TP4 PWR | no beep | short on the charger input: D1, D2, **D4 backwards** |')
    a('| 6–8 | each fuse\'s jack-side leg (same as that jack\'s pin 1: battery + after the fuse) | no beep | solder bridge at that jack or fuse |')
    a('')
    a('Then **diode mode** ("D" in the picture), red on TP4 (PWR), black on TP5 (GND): about 0.7–0.9 V is wrong (D4 is in backwards: its band must')
    a('be on the square pad); open ("OL") is right.')
    a('')
    a('Finally, look at the underside in good light for bridges between neighboring pads, especially the sockets and')
    a('jacks, and check every lead is trimmed to 1.8 mm or less.')
    a('')
    # ---- step 11
    a('## Step 11: The charger, the battery and solar')
    a('')
    a('**Charger: Adafruit 6092 (bq25185), used as a charger only.** The battery feeds the whole board directly (motors and')
    a('ESP), and the charger just keeps it topped up. A charger\'s own load output can only supply about 1 A, not enough for')
    a('three motors at once; an 18650 supplies 3 A or more. (The first build used a no-name MCP73871 module. It charged at')
    a('only 0.05–0.15 A instead of 0.35 A, even off the PCB, and starved the ESP on USB: see')
    a('[the v3 must-test list](pcb-v3-concept.md#must-test-on-the-v2-board-before-ordering-v3).)')
    a('')
    a('**Cut list (one box):**')
    a('')
    a('| Lead | Wire | Cut | From → to |')
    a('|---|---|---|---|')
    a('| Splice leg A | 22 AWG, XH crimp pin on the plug end | about 30 mm | J5 slot 2 → the splice |')
    a('| Splice leg B | 22 AWG, XH crimp pin on the plug end | about 30 mm | J5 slot 4 → the splice |')
    a('| Charger BATT | 22 AWG | about 50 mm | the splice → **BAT** pad |')
    a('| Charger GND | 22 AWG, XH crimp pin on the plug end | 76 mm | J5 pin 1 → **G** pad |')
    a('| Charger PWR | 22 AWG, XH crimp pin on the plug end | 76 mm | J5 pin 6 → **VIN** pad (solar in; USB shows here too) |')
    a('| Battery | the cell\'s own JST-XH lead (needs ≥ 45 mm) | as is | cell → J4 |')
    a('| Solar (optional) | the panel\'s flat 2-core cable | to suit | through end wall B → JST-ZH plug in J8 |')
    a('')
    a('Cut the four plug wires, strip about 2 mm on one end and crimp a JST-XH pin (SXH-001T-P0.6) on it with an XH')
    a('crimper. Tug each pin hard: it must not slide off. **No crimper?** Use the optional pre-crimped leads (152 mm, a')
    a('crimp on both ends) instead: cut each one to the length above, keeping a crimp end for the J5 housing.')
    a('')
    a('### 11a: The battery splice in the J5 plug (slots 2 and 4)')
    a('')
    a('![J5 splice](renders/pcb-build-splice.png)')
    a('')
    a('Nothing changes on the PCB. On the board, J5 pin 2 is the battery and pin 4 is the board supply; putting the battery')
    a('wire in **both** slots joins them, so the battery feeds the board directly.')
    a('')
    a('1. The two splice legs, about **30 mm** each, with their crimp pins in **slot 2** and **slot 4**.')
    a('2. Strip the two bare ends and the wire to the 6092\'s **BAT** pad, twist all three together, solder, and slide')
    a('   heat-shrink over the joint.')
    a('3. If your J5 plug still has the old LOAD wire in slot 4, pull it out first (lift the plastic tab over its crimp with a')
    a('   pin and slide it back out).')
    a('4. **Both crimps click in, then tug-test each one.** The motor current goes through these two crimps; a loose one cuts')
    a('   power to the whole board.')
    a('5. **With the J5 plug out, the board has no power.** The battery reaches it only through this plug.')
    a('')
    a('### 11b: Charger (Adafruit 6092)')
    a('')
    a('![charger wiring](renders/pcb-build-charger.png)')
    a('')
    a('1. **Three wires, soldered to the pads by their printed names:**')
    a('   - J5 **pin 1 (GND)** → **G** (or the **−** screw terminal)')
    a('   - J5 **pin 2 (BATT)** → **BAT** (bottom edge)')
    a('   - J5 **pin 6 (PWR)** → **VIN** (the DC / solar pads)')
    a('2. **Leave empty:** the **4.5V** and **3V** screw terminals, the JST-PH battery socket, and EN.')
    a('3. No temperature probe and no big capacitor: this module doesn\'t use them.')
    a('4. **Which wire goes in which slot: go by the letters printed on the board**, not by pin numbers. Push the **empty**')
    a('   plug into the board\'s charger socket first (it only fits one way), look straight down, and mark each slot with the')
    a('   letter printed beside it:')
    a('')
    a('   ![charger plug on the board](renders/pcb-build-plug.png)')
    a('')
    a('   | Letter on the board | Wire |')
    a('   |---|---|')
    a('   | **G** | the wire to the charger\'s **G** |')
    a('   | **B+** | a BAT splice wire |')
    a('   | (no letter) | empty |')
    a('   | **L+** | the other BAT splice wire |')
    a('   | (no letter) | empty |')
    a('   | **P+** | the wire to the charger\'s **VIN** |')
    a('')
    a('5. **Check before the battery goes in** (meter on beep, battery and USB unplugged, plug in the board): charger **G**')
    a('   to the **GND** test pad beeps, charger **BAT** to **BAT+** beeps, charger **VIN** to **PWR** beeps, and charger')
    a('   **BAT** to **GND** does **not** beep.')
    a('6. **Tug-test every crimp.** On a v2 board the PWR crimp lost contact twice: TP4 read 4.8 V while the module\'s')
    a('   input read 0 V.')
    a('')
    a('**The lights:** orange **C** on = charging, off = full. Red **F** = a fault: unplug and check the wiring. The chip stops')
    a('charging after **6 hours** nonstop; unplugging and replugging the power restarts it (for solar, the sun going down does).')
    a('')
    a('**USB:** plug USB power into the **6092\'s own USB-C** (full 5 V, straight into the charger). The PCB\'s USB-C board,')
    a('its lead and J3 are no longer used; D1 just sits idle. Two things to know:')
    a('')
    a('- **The ESP can still tell USB is plugged in.** With USB in the 6092, its VIN pad (and so the PCB\'s PWR line and GPIO0)')
    a('  reads about **4.35 V**, about 0.6 V under USB, so the module joins USB to VIN, most likely through a diode (measured')
    a('  on a v2 board).')
    a('- **Don\'t plug in USB-C and the solar panel at the same time**: that diode is not tested yet, so the panel might')
    a('  push back into the USB charger.')
    a('')
    a('### 11c: Battery')
    a('')
    a('The 18650 plugs into **J4** with its own JST-XH lead: nothing to make. Before it ever goes in:')
    a('')
    a('1. Hold its plug against J4: the **red wire must sit over the silkscreen +**.')
    a('2. Meter on **DC volts**, red probe on the plug\'s red wire: **+3.0 to +4.2 V**. A minus sign means the plug is wired')
    a('   backwards: don\'t plug it in.')
    a('3. **Charge it first** (see "Charging the battery on the bench" below): the ESP needs the cell above about 3.8 V.')
    a('')
    a('### 11d: Solar (optional)')
    a('')
    a('The panel\'s flat 2-core cable comes in through the slot in end wall B and gets a **JST-ZH 2-pin plug**: **− on pin 1**')
    a('(silk −), **+ on pin 2** (silk +). **Check the panel\'s polarity with the meter in sun before crimping**: on the first')
    a('board the panel was wired backwards (D2 blocked it, nothing was damaged). Behind a window it needs daylight: a 6 V panel')
    a('in a dim room reads about 1 V and charges nothing.')
    a('')
    a('### Charging the battery on the bench')
    a('')
    a('The fastest way to fill a flat cell, without the PCB:')
    a('')
    a('1. Unplug the battery from J4.')
    a('2. Two clip leads: battery **red → BAT**, battery **black → the − screw terminal** of the 6092.')
    a('3. USB-C straight into the 6092. Orange **C** lights.')
    a('4. About 2 hours from 3.6 V at 1 A. Done when **C** goes out. Unplug, wait a minute, measure: **4.1–4.2 V** = full.')
    a('')
    a('**Never connect USB straight to the battery:** 5 V pushes a lithium cell past 4.2 V and it can swell or catch fire.')
    a('')
    a('| Cell reads (resting) | Charge |')
    a('|---|---|')
    a('| 4.2 V | full |')
    a('| 3.9 V | about 75% |')
    a('| 3.7 V | about 50% (the "3.7 V" on the label is the average, not full) |')
    a('| 3.6 V | about 25–30% |')
    a('| 3.0 V | empty |')
    a('')
    # ---- step 12
    a('## Step 12: First power (no ESP yet)')
    a('')
    a('Meter on **DC volts** (V with a straight line, "V⎓" or "DCV", not the wavy V~; range 20 if it has ranges). Black probe')
    a('on **TP5 (GND)** for every reading.')
    a('')
    a('1. **Battery polarity:** hold its plug against J4: red wire over **+**, and the plug reads **+3.0 to +4.2 V**.')
    a('2. Plug the **charger harness into J5**, then the **battery into J4**. Through the splice in the J5 plug, the battery')
    a('   reaches the board directly.')
    a('3. Measure:')
    a('')
    a('| Pad | Expect |')
    a('|---|---|')
    a('| TP1 BAT+ | the cell\'s voltage (3.0–4.2 V) |')
    a('| TP2 5V | 0.1–0.4 V under TP1 (it comes through D3) |')
    a('| TP3 3V3 | 0 V (it comes from the ESP, not plugged in yet) |')
    a('| TP4 PWR | 0 V. Plug USB into the 6092: about **4.35 V**, and the orange light comes on. With the solar panel in daylight instead: about 5.5–6 V |')
    a('')
    a('**TP1 is the cell** (through the J5 splice); TP2 is always 0.1–0.4 V lower, so don\'t read the battery off TP2. While')
    a('it charges the cell reads a little high: for a true reading, unplug USB for a minute first.')
    a('')
    a('If TP1 reads 0, check the J5 plug is in and both splice crimps (slots 2 and 4) are clicked in, and that the cell isn\'t flat.')
    a('')
    # ---- step 13
    a('## Step 13: Plug in the ESP')
    a('')
    a('1. **Unplug the battery** (J4).')
    a('2. Flash the ESP32-C6 on the bench first (through its own USB-C). In the box there\'s no room for a cable.')
    a('3. Plug it into J1 / J2: **chip up, its USB toward end B**, its 5V pin in J1\'s square pad. Push it fully down.')
    a('4. Battery back in. **TP3 should read 3.3 V**, and the ESP boots. With the cell below about 3.8 V, TP3 sags toward')
    a('   3.0 V (D3 and the ESP\'s regulator each take a little) and the ESP resets whenever the radio transmits: charge the cell first.')
    a('   (v3 fixes this with a 3.3 V converter: [v3 must-test list](pcb-v3-concept.md#must-test-on-the-v2-board-before-ordering-v3).)')
    a('')
    a('Then it goes into the box: [box assembly](controller-box.md#assembly).')
    a('')
    a('## If something reads wrong')
    a('')
    a('| Symptom | Likely cause | Check |')
    a('|---|---|---|')
    a('| Readings make no sense | meter on the wrong setting (AC, mV, or Ω) | dial on **DC volts**, range 20 |')
    a('| Minus sign on a reading | probes swapped, or a plug wired backwards | black on TP5; measure the plug by itself |')
    a('| Solar in: TP4 has voltage but the charger\'s VIN reads 0 V | PWR crimp not making contact | push the crimp in until it clicks, tug-test it |')
    a('| TP1 and TP2 fine, TP3 about 3.0 V, ESP keeps resetting | cell too low (below about 3.8 V) | charge it (bench charging above) |')
    a('| Cell barely rises after hours | charger not charging properly | USB power meter between charger and cable: about **1 A** while charging (6092) |')
    a('| ESP not reaching the Tilt Hub | not powered, or browning out | TP3 = 3.3 V? Unplug power 5 s to restart it |')
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
