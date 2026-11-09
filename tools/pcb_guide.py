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


def charger_picture():
    """The Adafruit 6092 (bq25185) charger, used as a charger ONLY, and its 3-wire J5 harness. Drawn as a wiring diagram:
    the pad names are the ones printed on the board (Adafruit's guide); positions on the real board differ, so go by the
    printed labels."""
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="980" font-family="Helvetica,Arial">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         text(20, 32, 'Charger: Adafruit 6092 (bq25185), wired as a charger only', 20, '#111', 'bold', 'start', halo=False),
         text(20, 56, 'Top view, drawn from Adafruit\'s photo (not to scale). Go by the name printed beside each pad.', 13, '#444', anchor='start', halo=False)]
    # the module, top view, drawn from Adafruit's photo: USB-C at the top end, the screw terminal at the bottom end, the
    # JST-PH socket just below the USB-C, and the row of 8 pads down the left edge (VIN at the USB end, EN at the terminal end)
    mx0, my0, mw, mh = 620, 120, 300, 470
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
    o.append(text(mx0 + mw / 2, my0 + mh + 64, '(the battery feeds the board directly; see the J5 jumper)', 12, '#555', halo=False))
    # the J5 housing on the left, wires to the pads
    hx, hy = 70, 200
    cav = [('1', 'G', 'GND', '#222'), ('2', 'B+', 'BATT', '#d62728'), ('3', '·', 'empty', '#999'),
           ('4', 'L+', 'empty', '#999'), ('5', '·', 'empty', '#999'), ('6', 'P+', 'PWR', '#d62728')]
    o.append(text(hx, hy - 50, 'J5 plug (6-pin JST-XH)', 15, '#111', 'bold', 'start', halo=False))
    o.append(text(hx, hy - 30, 'wire side toward you, lock ramp up: pin 1 on top here', 12, '#d62728', anchor='start', halo=False))
    o.append('<rect x="%d" y="%d" width="150" height="%d" rx="6" fill="#f4f1e8" stroke="#555" stroke-width="2"/>' % (hx, hy, 6 * 50 + 10))
    wire_y = {}
    for q, (pin, silk, what, c) in enumerate(cav):
        y_ = hy + 5 + 50 * q
        o.append('<rect x="%d" y="%d" width="140" height="44" rx="4" fill="#fff" stroke="#bbb"/>' % (hx + 5, y_))
        o.append(text(hx + 15, y_ + 18, 'pin %s (%s)' % (pin, silk), 12, '#444', anchor='start', halo=False))
        o.append(text(hx + 15, y_ + 36, what, 14, c, 'bold', 'start', halo=False))
        wire_y[pin] = y_ + 22
    for name, col, y, lab in pads:
        y0 = wire_y[{'G': '1', 'BAT': '2', 'VIN': '6'}[name]]
        o.append('<path d="M%d %d C %d %d, %d %d, %d %d" fill="none" stroke="%s" stroke-width="4"/>' % (
            hx + 150, y0, hx + 330, y0, mx0 - 180, my0 + y, mx0 - 16, my0 + y, col))
    o.append(text(hx, hy + 6 * 50 + 34, 'pin 4 stays empty: it\'s jumpered to pin 2 on the PCB (11a)', 12, '#666', anchor='start', halo=False))
    ty0 = 740
    for k_, t in enumerate([
            '3 wires, all on the pad row: GND (pin 1) to G, BATT (pin 2) to BAT, PWR (pin 6) to VIN. Nothing else is wired.',
            'No temperature probe and no big capacitor with this module (the old one needed both).',
            'Orange C on = charging; off = full (or its fixed 6-hour charge limit: unplug and replug power to restart).',
            'Red F = fault: unplug and check the wiring.',
            'USB plugs into this module\'s USB-C. The PCB\'s USB-C board and J3 are not used.',
            'VIN carries solar only (J8 → D2 → J5 pin 6). The ESP can\'t see USB is plugged in (GPIO0 sees solar only).',
            'Do not plug in USB-C and the solar panel at the same time (not yet checked how the module joins them).']):
        o.append(text(40, ty0 + 24 * k_, t, 13, '#d62728' if k_ >= 4 else '#222', 'bold' if k_ == 0 else 'normal', 'start', halo=False))
    o.append('</svg>')
    open(os.path.join(OUT, 'pcb-build-charger.svg'), 'w').write('\n'.join(o))
    return 'pcb-build-charger.svg'


def jumper_picture():
    """Close-up of J5's six pins from UNDER the board: the wire that joins pin 2 (battery) to pin 4 (board supply)."""
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="440" font-family="Helvetica,Arial">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         text(20, 32, 'J5 jumper: pin 2 to pin 4, on the underside', 20, '#111', 'bold', 'start', halo=False),
         text(20, 56, 'The battery then feeds the whole board directly; the charger only charges it.', 13, '#444', anchor='start', halo=False)]
    o.append('<rect x="60" y="100" width="780" height="200" rx="10" fill="#2f6b3a" stroke="#1d4426" stroke-width="2"/>')
    o.append(text(450, 125, 'UNDERSIDE of the PCB at J5 (near end B, the USB-C end)', 13, '#e9efe9', 'bold', halo=False))
    xs = [150 + 110 * k for k in range(6)]
    for k, x in enumerate(xs):
        if k == 0:
            o.append('<rect x="%d" y="182" width="44" height="44" rx="4" fill="#d9b44a" stroke="#8a6d1f" stroke-width="2"/>' % (x - 22))
        else:
            o.append('<circle cx="%d" cy="204" r="22" fill="#d9b44a" stroke="#8a6d1f" stroke-width="2"/>' % x)
        o.append('<circle cx="%d" cy="204" r="8" fill="#777"/>' % x)
        o.append(text(x, 262, 'pin %d' % (k + 1), 14, '#fff', 'bold', halo=False))
    o.append(text(xs[0], 285, 'square pad', 12, '#e9efe9', halo=False))
    for k, lab in ((1, 'battery'), (3, 'board supply')):
        o.append(text(xs[k], 285, lab, 12, '#ffd', 'bold', halo=False))
    o.append('<path d="M%d 190 C %d 140, %d 140, %d 190" fill="none" stroke="#d62728" stroke-width="6"/>' % (xs[1], xs[1] + 30, xs[3] - 30, xs[3]))
    o.append(text((xs[1] + xs[3]) / 2, 148, 'insulated wire', 13, '#fff', 'bold', halo=False))
    o.append(text((xs[1] + xs[3]) / 2, 230, 'pin 3 NOT touched', 12, '#ffd', halo=False))
    for k_, t in enumerate([
            'Count from the SQUARE pad (pin 1): the 2nd and the 4th pin. The square pad is pin 1 from either side of the board.',
            'Use a short piece of insulated wire (22 AWG), stripped 2 mm at each end, soldered to the two pin joints.',
            'It must clear pin 3. Keep it flat: the board sits 2.4 mm off the box floor.',
            'Check: meter on beep, pin 2 to TP1 should beep. Then pull the old LOAD wire out of slot 4 of the J5 plug.']):
        o.append(text(40, 340 + 24 * k_, t, 13, '#222', 'bold' if k_ == 0 else 'normal', 'start', halo=False))
    o.append('</svg>')
    open(os.path.join(OUT, 'pcb-build-jumper.svg'), 'w').write('\n'.join(o))
    return 'pcb-build-jumper.svg'


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
    pics.append(jumper_picture())
    pics.append(charger_picture())

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
        a('| %s | %d | %s | %s |' % (v + (' (optional, not used with the 6092)' if any(r == 'J3' for r, _ in lst) else ''), len(lst),
                                   ', '.join(r for r, _ in lst), ', '.join(sorted({str(k) for _, k in lst}))))
    a('| ESP32-C6 SuperMini (male pins on, flashed on the bench) | 1 | plugs into J1 / J2 | 13 |')
    a('| Adafruit 6092 charger (bq25185), charging only, + 3-wire harness (6-pin XH housing) | 1 | J5 | 11 |')
    a('| Short insulated wire for the J5 pin 2 to pin 4 jumper | 1 | J5 underside | 11 |')
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
    a('| J5 | JST-XH 6-pin (B6B-XH-A) | the charger harness | **G  B+  ·  L+  ·  P+** (pins 3 and 5 empty; pin 4 gets jumpered to pin 2 in step 11) |')
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
    a('| J5 jumper | 22 AWG insulated | about 8 mm | J5 pin 2 → J5 pin 4, under the PCB |')
    a('| Charger BATT | 22 AWG, pre-crimped JST lead | 76 mm | J5 pin 2 → **BAT** pad |')
    a('| Charger GND | 22 AWG, pre-crimped JST lead | 76 mm | J5 pin 1 → **G** pad |')
    a('| Charger PWR | 22 AWG, pre-crimped JST lead | 76 mm | J5 pin 6 → **VIN** pad (carries solar) |')
    a('| Battery | the cell\'s own JST-XH lead (needs ≥ 45 mm) | as is | cell → J4 |')
    a('| Solar (optional) | the panel\'s flat 2-core cable | to suit | through end wall B → JST-ZH plug in J8 |')
    a('')
    a('The pre-crimped JST leads are 152 mm with a crimp on both ends: cut them so the crimp end goes in the J5 housing.')
    a('')
    a('### 11a: The J5 jumper (pin 2 to pin 4)')
    a('')
    a('![J5 jumper](renders/pcb-build-jumper.png)')
    a('')
    a('1. Turn the board over. Find J5\'s six pins; **pin 1 is the square pad** (from either side).')
    a('2. Solder a short insulated wire from **pin 2** (battery) to **pin 4** (board supply), clear of pin 3. Keep it flat.')
    a('3. **Check:** meter on beep, J5 pin 2 to **TP1** beeps.')
    a('4. If your J5 plug still has a wire in **slot 4** (the old LOAD wire), pull it out: lift the plastic tab over its crimp')
    a('   with a pin and slide it back out.')
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
    a('4. **Crimp the three ends into the 6-pin housing:** pin 1 GND, pin 2 BATT, pin 6 PWR. Pins 3, 4, 5 empty.')
    a('5. **Which end is pin 1:** from the wire side with the housing\'s **lock ramp up**, pin 1 is on the **left** (JST\'s XH')
    a('   drawing). To be sure, push the **empty** housing into the soldered J5 first (it only fits one way), look down, and')
    a('   mark the cavity over the silkscreen **G**. That\'s pin 1.')
    a('6. **Tug-test every crimp.** On the first board the PWR crimp lost contact twice: TP4 read 4.8 V while the module\'s')
    a('   input read 0 V.')
    a('')
    a('**The lights:** orange **C** on = charging, off = full. Red **F** = a fault: unplug and check the wiring. The chip stops')
    a('charging after **6 hours** nonstop; unplugging and replugging the power restarts it (for solar, the sun going down does).')
    a('')
    a('**USB:** plug USB power into the **6092\'s own USB-C** (full 5 V, straight into the charger). The PCB\'s USB-C board,')
    a('its lead and J3 are no longer used; D1 just sits idle. Two things to know:')
    a('')
    a('- **The ESP can\'t tell USB is plugged in.** GPIO0 (PSENSE) watches the PWR line, which now only carries solar.')
    a('  Charging works the same; only the firmware\'s "USB present" reading is lost. One wire from the 6092\'s **VU** pad could')
    a('  bring it back, once we\'ve checked how VU connects inside the module.')
    a('- **Don\'t plug in USB-C and the solar panel at the same time** until we\'ve checked how the 6092 joins its USB-C and VIN.')
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
    a('2. Plug the **charger harness into J5**, then the **battery into J4**. With the J5 jumper, the battery reaches the board')
    a('   directly.')
    a('3. Measure:')
    a('')
    a('| Pad | Expect |')
    a('|---|---|')
    a('| TP1 BAT+ | the cell\'s voltage (3.0–4.2 V) |')
    a('| TP2 5V | 0.1–0.4 V under TP1 (it comes through D3) |')
    a('| TP3 3V3 | 0 V (it comes from the ESP, not plugged in yet) |')
    a('| TP4 PWR | 0 V. Plug USB into the 6092: TP4 **stays 0 V** (it only sees solar) and the orange light comes on. With the solar panel in daylight: about 5.5–6 V |')
    a('')
    a('**TP1 is the cell** (through the J5 jumper); TP2 is always 0.1–0.4 V lower, so don\'t read the battery off TP2. While')
    a('it charges the cell reads a little high: for a true reading, unplug USB for a minute first.')
    a('')
    a('If TP1 reads 0, check the J5 jumper (pin 2 to pin 4) and that the cell isn\'t flat.')
    a('')
    # ---- step 13
    a('## Step 13: Plug in the ESP')
    a('')
    a('1. **Unplug the battery** (J4).')
    a('2. Flash the ESP32-C6 on the bench first (through its own USB-C). In the box there\'s no room for a cable.')
    a('3. Plug it into J1 / J2: **chip up, its USB toward end B**, its 5V pin in J1\'s square pad. Push it fully down.')
    a('4. Battery back in. **TP3 should read 3.3 V**, and the ESP boots. With the cell below about 3.8 V, TP3 sags toward')
    a('   3.0 V (D3 and the ESP\'s regulator each take a little) and the ESP resets whenever Wi-Fi transmits: charge the cell first.')
    a('   (v3 fixes this with a 3.3 V converter: [v3 must-test list](pcb-v3-concept.md#must-test-on-the-v2-board-before-ordering-v3).)')
    a('')
    a('Then it goes into the box: [V5 assembly](controller-v5.md#assembly).')
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
    a('| ESP not on Wi-Fi | not powered, or browning out | TP3 = 3.3 V? Unplug power 5 s to restart it |')
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
