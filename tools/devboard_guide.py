"""Build guide for the controller dev board: writes docs/dev-board-build.md and one checkpoint picture per step
(docs/renders/build-step-NN.svg/.png), all drawn from ControllerV4's layout and wiring list so they always match it.

Order: every part and lead first (holes still open), then the insulated wires, then the bare bridges, then the two
rails, so solder never fills a hole that something still has to go through. In each picture the current step is in
colour and earlier steps are greyed out.

  python3 tools/devboard_guide.py          # writes the svgs + the markdown
  python3 tools/devboard_guide.py --png    # also renders the pngs with headless Chrome
"""
import importlib.util
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STRAIGHT = '--straight' in sys.argv           # the older straight layout (ControllerV4.py): pictures only, prefixed build-s-
spec = importlib.util.spec_from_file_location('cv4', os.path.join(HERE, '../hardware/mechanical/fusion/ControllerV4/',
                                                                   'ControllerV4.py' if STRAIGHT else 'DevBoardR.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
H, HN, COLS = M.H, M.HN, M.COLS
OUT = os.path.join(HERE, '../docs/renders')
DOC = os.path.join(HERE, '../docs/dev-board-build.md')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
PRE = 'build-s-' if STRAIGHT else 'build-'

S = 30.0                     # px per hole pitch
MX, MY = 70, 90              # margins
W = int(MX * 2 + S * (M.NI - 1) + 360)
HGT = int(MY + S * (M.NM - 1) + 160)

NET_COL = {'GND': '#222222', 'VBAT': '#d62728', '5V': '#ff7f0e', '3V3': '#9467bd', 'sig': '#1f77b4'}
PARTS = {p.name: p for p in M.layout()}


def pins(name):
    return [HN(i, m) for i, m, _ in PARTS[name].pins]


def pos(hole, bottom=False):
    i, m = H(hole)
    return MX + S * i, MY + S * (m if bottom else (M.NM - 1 - m))   # top view: column a at the bottom; bottom view: a on top


# ------------------------------------------------------------------ drawing primitives
def board(title, sub, bottom=False):
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica,Arial">' % (W, HGT),
         '<defs><filter id="mute"><feColorMatrix type="saturate" values="0"/></filter></defs>',
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         '<text x="%d" y="30" font-size="20" font-weight="bold">%s</text>' % (MX - 40, title),
         '<text x="%d" y="54" font-size="13" fill="#444">%s</text>' % (MX - 40, sub),
         '<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="6" fill="%s" stroke="#3a7a2a" stroke-width="2"/>' % (
             MX - S * 0.7, MY - S * 0.7, S * (M.NI - 1) + S * 1.4, S * (M.NM - 1) + S * 1.4,
             '#f3efe2' if bottom else '#e9f4e1')]
    for i in range(M.NI):
        o.append('<text x="%.0f" y="%.0f" font-size="11" fill="#666" text-anchor="middle">%d</text>' % (MX + S * i, MY - S * 0.9, i + 1))
    for m in range(M.NM):
        y = MY + S * (m if bottom else (M.NM - 1 - m))
        o.append('<text x="%.0f" y="%.0f" font-size="13" font-weight="bold" fill="#666" text-anchor="middle">%s</text>' % (
            MX - S * 1.15, y + 4, COLS[m]))
    for i in range(M.NI):
        for m in range(M.NM):
            x, y = pos(HN(i, m), bottom)
            o.append('<circle cx="%.0f" cy="%.0f" r="4" fill="#fff" stroke="#999"/>' % (x, y))
    return o


def finish(o, name, notes=()):
    y = MY + S * (M.NM - 1) + S * 2.9
    for n in notes:
        o.append('<text x="%d" y="%.0f" font-size="13" fill="#222">%s</text>' % (MX - 40, y, n))
        y += 20
    o.append('</svg>')
    open(os.path.join(OUT, name), 'w').write('\n'.join(o))


def muted(o, items):
    o.append('<g filter="url(#mute)" opacity="0.3">')
    o.extend(items)
    o.append('</g>')


def dot(o, hole, color, bottom=False, r=6):
    x, y = pos(hole, bottom)
    o.append('<circle cx="%.0f" cy="%.0f" r="%d" fill="%s"/>' % (x, y, r, color))


def ring(o, hole, color, bottom=False):
    x, y = pos(hole, bottom)
    o.append('<circle cx="%.0f" cy="%.0f" r="9" fill="none" stroke="%s" stroke-width="2.5"/>' % (x, y, color))


def label(o, hole, text, dx=0, dy=-12, color='#000', size=11, bottom=False, anchor='middle'):
    x, y = pos(hole, bottom)
    o.append('<text x="%.0f" y="%.0f" font-size="%d" fill="%s" text-anchor="%s" font-weight="bold">%s</text>' % (
        x + dx, y + dy, size, color, anchor, text))


def edge_dy(hole, bottom):
    """Label offset that keeps a label inside the board: below holes on the top edge of the picture, above the rest."""
    top_edge = hole[0] == ('a' if bottom else 'j')
    return 19 if top_edge else -11


def span(a, b):
    (i0, m0), (i1, m1) = H(a), H(b)
    return abs(i0 - i1) + abs(m0 - m1)


BANDS = {'1k': ('#8b4513', '#111', '#d62728'), '1M': ('#8b4513', '#111', '#2ca02c'), '10k': ('#8b4513', '#111', '#ff7f0e')}


def flat_body(o, a, b, length_mm, fill, stroke):
    """Body of a part lying flat between holes a and b (legs drawn to the holes). Returns the body's geometry."""
    (x0, y0), (x1, y1) = pos(a), pos(b)
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    ux, uy = (x1 - x0) / math.hypot(x1 - x0, y1 - y0), (y1 - y0) / math.hypot(x1 - x0, y1 - y0)
    half = length_mm / 2.54 * S / 2
    o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="#888" stroke-width="2"/>' % (x0, y0, x1, y1))
    w, h = (2 * half, 18) if abs(ux) > abs(uy) else (18, 2 * half)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="7" fill="%s" stroke="%s" stroke-width="1.5"/>' % (
        xm - w / 2, ym - h / 2, w, h, fill, stroke))
    return xm, ym, ux, uy, half


def resistor(o, a, b, text):
    if span(a, b) >= 3:                                   # lying flat: body between the legs, colour bands
        xm, ym, ux, uy, half = flat_body(o, a, b, 6.3, '#e8c88a', '#8a6a2a')
        for k, c in enumerate(BANDS.get(text, ())):
            bx, by = xm + ux * (-half + 7 + 7 * k), ym + uy * (-half + 7 + 7 * k)
            w, h = (4, 18) if abs(ux) > abs(uy) else (18, 4)
            o.append('<rect x="%.0f" y="%.0f" width="%d" height="%d" fill="%s"/>' % (bx - w / 2, by - h / 2, w, h, c))
        o.append('<text x="%.0f" y="%.0f" font-size="9" text-anchor="middle" font-weight="bold">%s</text>' % (
            xm + ux * 8 + (0 if abs(ux) > abs(uy) else 20), ym + uy * 8 + (-12 if abs(ux) > abs(uy) else 3), text))
        return
    (x0, y0), (x1, y1) = pos(a), pos(b)
    o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="#888" stroke-width="2"/>' % (x0, y0, x1, y1))
    o.append('<circle cx="%.0f" cy="%.0f" r="9" fill="#e8c88a" stroke="#8a6a2a" stroke-width="1.5"/>' % (x0, y0))
    o.append('<text x="%.0f" y="%.0f" font-size="9" text-anchor="middle" font-weight="bold">%s</text>' % (x0, y0 + 3, text))


def ceramic(o, a, b, text):
    (x0, y0), (x1, y1) = pos(a), pos(b)
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    if x0 != x1 and y0 != y1:                                   # corner to corner: tilted body
        ln = math.hypot(x1 - x0, y1 - y0) + 16
        o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="12" rx="3" fill="#7fb2e5" stroke="#2a5a8a" transform="rotate(%.1f %.0f %.0f)"/>' % (
            xm - ln / 2, ym - 6, ln, math.degrees(math.atan2(y1 - y0, x1 - x0)), xm, ym))
        o.append('<text x="%.0f" y="%.0f" font-size="9" fill="#0b2e55" font-weight="bold">%s</text>' % (xm + 12, ym + 4, text))
        return
    w, h = (abs(x1 - x0) + 16, 12) if y0 == y1 else (12, abs(y1 - y0) + 16)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="3" fill="#7fb2e5" stroke="#2a5a8a"/>' % (
        xm - w / 2, ym - h / 2, w, h))
    o.append('<text x="%.0f" y="%.0f" font-size="9" text-anchor="middle" fill="#0b2e55" font-weight="bold">%s</text>' % (
        xm + (0 if y0 == y1 else 16), ym + (-9 if y0 == y1 else 3), text))


# ------------------------------------------------------------------ what each step adds
RES = [('R div top 1M', '1M'), ('R div bot 1M', '1M'), ('R pwr top 1M', '1M'), ('R pwr bot 1M', '1M'),
       ('R ADC1 1k', '1k'), ('R ADC2 1k', '1k'), ('R ADC3 1k', '1k')]
CAPS = [('C 10u', '10µ'), ('C div 100n', '100n'), ('C ADC1 100n', '100n'), ('C ADC2 100n', '100n'), ('C ADC3 100n', '100n')]
DIODES = [('D3 1N5819', 'D3'), ('D1 1N5819 USB', 'D1'), ('D2 1N5819 solar', 'D2'), ('Z 6.2V', 'Z')]


def draw_esp(o):
    """ESP body from its pin positions, USB-C past the pin-1 end (5V / TX), pin names just inside the body."""
    pts = {lab: pos(HN(i, m)) for i, m, lab in PARTS['ESP32-C6'].pins}
    xs, ys = [p[0] for p in pts.values()], [p[1] for p in pts.values()]
    x0, x1, y0, y1 = min(xs) - 22, max(xs) + 22, min(ys) - 22, max(ys) + 22
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="5" fill="#1b1b1b" opacity="0.85"/>' % (x0, y0, x1 - x0, y1 - y0))
    (ax, ay), (bx, by) = pts['5V'], pts['TX16']
    (cx, cy), (dx, dy) = pts['8'], pts['7']
    ux, uy = (ax + bx - cx - dx) / 2, (ay + by - cy - dy) / 2          # from the far end toward the USB end
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    mx, my = (ax + bx) / 2 + ux * 40, (ay + by) / 2 + uy * 40
    w, h = (48, 74) if abs(ux) > abs(uy) else (74, 48)
    o.append('<rect x="%.0f" y="%.0f" width="%d" height="%d" rx="4" fill="#bbb" stroke="#666"/>' % (mx - w / 2, my - h / 2, w, h))
    o.append('<text x="%.0f" y="%.0f" font-size="11" text-anchor="middle" font-weight="bold">USB-C</text>' % (mx, my + 4))
    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    rows_run_x = abs(pts['5V'][1] - pts['8'][1]) < 1          # each pin row runs left-right: put labels above / below it
    for lab, (x, y) in pts.items():
        o.append('<circle cx="%.0f" cy="%.0f" r="6" fill="#e0b040"/>' % (x, y))
        if rows_run_x:
            lx, ly = x, y + (19 if yc > y else -11)
        else:
            lx, ly = x + (18 if xc > x else -18), y + 3
        o.append('<text x="%.0f" y="%.0f" font-size="9" fill="#fff" text-anchor="middle" font-weight="bold">%s</text>' % (
            lx, ly, lab.replace('TX16', 'TX').replace('RX17', 'RX')))
    o.append('<text x="%.0f" y="%.0f" font-size="15" fill="#fff" text-anchor="middle" font-weight="bold">ESP32-C6 (chip up)</text>' % (xc, yc + 5))


def socket_rows():
    """Female header socket strips: the ESP's two pin rows, the USB-C breakout's row (if it plugs in)."""
    rows = []
    for name in ('ESP32-C6', 'USB-C breakout'):
        if name in PARTS:
            pts = [HN(i, m) for i, m, _ in PARTS[name].pins]
            by_row = len({H(q)[0] for q in pts}) < len(pts)
            groups = {}
            for h in pts:
                groups.setdefault(H(h)[0] if by_row else H(h)[1], []).append(h)
            rows += [(name, sorted(g, key=lambda q: H(q))) for g in groups.values()]
    return rows


def draw_sockets(o):
    for name, hs in socket_rows():
        (x0, y0), (x1, y1) = pos(hs[0]), pos(hs[-1])
        xa, xb, ya, yb = min(x0, x1) - 12, max(x0, x1) + 12, min(y0, y1) - 12, max(y0, y1) + 12
        o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="3" fill="#222"/>' % (xa, ya, xb - xa, yb - ya))
        for h in hs:
            x, y = pos(h)
            o.append('<rect x="%.0f" y="%.0f" width="8" height="8" fill="#888"/>' % (x - 4, y - 4))
        cx, cy = (xa + xb) / 2, (ya + yb) / 2
        rot = '' if xb - xa > yb - ya else ' transform="rotate(-90 %.0f %.0f)"' % (cx, cy)
        o.append('<text x="%.0f" y="%.0f" font-size="10" fill="#fff" text-anchor="middle" font-weight="bold"%s>%s socket (%d)</text>' % (
            cx, cy + 4, rot, 'ESP' if name == 'ESP32-C6' else 'USB-C', len(hs)))
    draw_jst(o)
    draw_batt(o)


def draw_usb(o):
    """The USB-C breakout plugged in, its socket hanging past the row-24 end."""
    if 'USB-C breakout' not in PARTS:
        return
    pts = {lab: pos(HN(i, m)) for i, m, lab in PARTS['USB-C breakout'].pins}
    ys = [p[1] for p in pts.values()]
    x = pts['VBUS'][0]
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="4" fill="#c0392b" opacity="0.9"/>' % (
        x - 1.5 / 2.54 * S, (min(ys) + max(ys)) / 2 - 10.8 / 2.54 * S, 12.7 / 2.54 * S, 21.6 / 2.54 * S))
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="5" fill="#bbb" stroke="#666"/>' % (
        x + (12.7 - 1.5 - 7.35 + 1.0) / 2.54 * S, (min(ys) + max(ys)) / 2 - 4.47 / 2.54 * S, 7.35 / 2.54 * S, 8.94 / 2.54 * S))
    for lab, (px, py) in pts.items():
        o.append('<circle cx="%.0f" cy="%.0f" r="5" fill="#e0b040"/>' % (px, py))
        o.append('<text x="%.0f" y="%.0f" font-size="8" fill="#fff" font-weight="bold">%s</text>' % (px + 8, py + 3, lab))


def draw_res(o):
    for n, txt in RES:
        a, b = pins(n)
        resistor(o, a, b, txt)


def draw_diodes(o):
    for n, txt in DIODES:
        p = dict((lab, HN(i, m)) for i, m, lab in PARTS[n].pins)
        body, lead = pins(n)
        if span(body, lead) >= 3:                         # lying flat: the band is drawn at the cathode end, as on the part
            xm, ym, ux, uy, half = flat_body(o, p['A'], p['K'], 5.2, '#333', '#111')
            bx, by = xm + ux * (half - 6), ym + uy * (half - 6)
            w, h = (7, 18) if abs(ux) > abs(uy) else (18, 7)
            o.append('<rect x="%.0f" y="%.0f" width="%d" height="%d" fill="#ddd"/>' % (bx - w / 2, by - h / 2, w, h))
            o.append('<text x="%.0f" y="%.0f" font-size="9" fill="#fff" text-anchor="middle" font-weight="bold">%s</text>' % (
                xm - ux * 5, ym - uy * 5 + 3, txt))
            label(o, p['K'], 'K', dx=(13 if abs(uy) > abs(ux) else 0), dy=(4 if abs(uy) > abs(ux) else -12), size=9)
            continue
        (x0, y0), (x1, y1) = pos(body), pos(lead)
        o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="#888" stroke-width="2"/>' % (x0, y0, x1, y1))
        o.append('<circle cx="%.0f" cy="%.0f" r="10" fill="#333"/>' % (x0, y0))
        x, y = pos(p['K'])
        if p['K'] == body:
            o.append('<circle cx="%.0f" cy="%.0f" r="10" fill="none" stroke="#ddd" stroke-width="3"/>' % (x, y))
        else:
            o.append('<rect x="%.0f" y="%.0f" width="8" height="16" fill="#ddd" stroke="#333"/>' % (x - 4, y - 8))
        label(o, p['K'], '%s band' % txt, dy=-14, size=10)


def draw_caps(o):
    for n, txt in CAPS:
        a, b = pins(n)
        ceramic(o, a, b, txt)


BATT = 'JST battery' if 'JST battery' in PARTS else 'Battery pins'
JSTS = [n for n in PARTS if n.startswith('JST')]


def draw_jst(o):
    """JST-XH headers: white housings, pins as dots, the pin names beside them."""
    for n in JSTS:
        hs = [HN(i, m) for i, m, _ in PARTS[n].pins]
        xs, ys = [pos(h)[0] for h in hs], [pos(h)[1] for h in hs]
        if 'GND' in n:                                    # right angle: housing reaches out over the column-a edge
            o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="3" fill="#f4f1e8" stroke="#777" stroke-width="1.5"/>' % (
                min(xs) - 22, min(ys) - 12, max(xs) - min(xs) + 44, 52))
        else:
            o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="3" fill="#f4f1e8" stroke="#777" stroke-width="1.5"/>' % (
                min(xs) - 22 if max(xs) > min(xs) else min(xs) - 17, min(ys) - 22 if max(ys) > min(ys) else min(ys) - 17,
                max(xs) - min(xs) + (44 if max(xs) > min(xs) else 34), max(ys) - min(ys) + (44 if max(ys) > min(ys) else 34)))
        for (i, m, lab), x, y in zip(PARTS[n].pins, xs, ys):
            c = NET_COL['VBAT'] if '+' in lab else NET_COL['GND']
            o.append('<circle cx="%.0f" cy="%.0f" r="5" fill="%s"/>' % (x, y, c))
        name = {'JST battery': 'battery', 'JST charger +': 'charger +', 'JST charger LOAD': 'LOAD +', 'JST charger GND': 'charger GND'}[n]
        if 'GND' in n:
            o.append('<text x="%.0f" y="%.0f" font-size="10" text-anchor="middle" font-weight="bold">%s</text>' % (
                (min(xs) + max(xs)) / 2, max(ys) + 30, name))
        elif n != 'JST battery':
            o.append('<text x="%.0f" y="%.0f" font-size="10" text-anchor="middle" font-weight="bold">%s</text>' % (
                (min(xs) + max(xs)) / 2 + (0 if max(xs) > min(xs) else 32), min(ys) + (32 if max(xs) > min(xs) else (max(ys) - min(ys)) / 2 + 4),
                name))


def draw_batt(o):
    for i, m, lab in PARTS[BATT].pins:
        h = HN(i, m)
        c = '#d62728' if lab == 'B+' else '#222'
        dot(o, h, c)
        label(o, h, {'B+': 'B+ (red)', 'B-': 'B− (black)'}[lab], dx=-12, dy=-10 if lab == 'B+' else 18, color=c, anchor='end')


def charger_pads():
    short = {'PWR + (input)': 'PWR+', 'PWR - / GND': 'PWR−', 'BATT +': 'BAT+', 'BATT -': 'BAT−', 'LOAD + (output)': 'LOAD+',
             'LOAD -': 'LD−'}
    return [(h, short[pad]) for pad, h, _ in M.CHARGER if pad in short]


def draw_charger(o):
    """The charger sits off the board, past the row-24 end; its wires come in to the ringed holes."""
    x0, _ = pos('a24')
    x0 += 130 if 'USB-C breakout' in PARTS else 0           # beyond the USB-C board's overhang
    _, ya = pos('a1')
    _, yj = pos('j1')
    o.append('<rect x="%.0f" y="%.0f" width="120" height="%.0f" rx="6" fill="#3b3b3b" opacity="0.85"/>' % (x0 + 44, yj - 6, ya - yj + 12))
    o.append('<text x="%.0f" y="%.0f" font-size="13" fill="#fff" text-anchor="middle" font-weight="bold">charger</text>' % (x0 + 104, (ya + yj) / 2 - 8))
    o.append('<text x="%.0f" y="%.0f" font-size="11" fill="#fff" text-anchor="middle">(off the board)</text>' % (x0 + 104, (ya + yj) / 2 + 10))
    for h, lab in charger_pads():
        x, y = pos(h)
        ring(o, h, '#0a7a3a')
        o.append('<path d="M%.0f %.0f Q%.0f %.0f %.0f %.0f" fill="none" stroke="#0a7a3a" stroke-width="1.5" stroke-dasharray="4,3"/>' % (
            x, y, (x + x0 + 44) / 2, y - 18, x0 + 44, y))
        label(o, h, lab, dy=22 if h[0] == 'a' else -13, color='#0a7a3a', size=9)


def draw_solar(o):
    draw_leads(o, ('Solar leads',))


def draw_leads(o, which=('Port leads', 'USB leads')):
    for n in [q for q in which if q in PARTS]:
        for i, m, lab in PARTS[n].pins:
            h = HN(i, m)
            sig = lab.split()[-1]
            if sig == 'VBAT' or lab in ('V+', 'S+'):
                c = NET_COL['VBAT']
            elif sig == 'GND' or lab in ('V-', 'S-'):
                c = NET_COL['GND']
            else:
                c = NET_COL['sig']
            dot(o, h, c, r=5)
            txt = {'V+': 'USB+', 'V-': 'USB−', 'S+': 'Sol+', 'S-': 'Sol−'}.get(lab, lab.replace(' VBAT', '+').replace(' GND', '−'))
            label(o, h, txt, dy=edge_dy(h, False), color=c, size=8)


def net_colour(note):
    n = note.lower()
    if n.startswith('gnd rail') or 'gnd' in n or 'zener anode' in n or ' - ->' in n:
        return NET_COL['GND']
    if n.startswith('vbat rail') or 'vbat' in n or 'battery +' in n:
        return NET_COL['VBAT']
    if '5v' in n:
        return NET_COL['5V']
    if '3v3' in n:
        return NET_COL['3V3']
    return NET_COL['sig']


def kind(w):
    if w[2].startswith(('GND rail', 'VBAT rail')):
        return 'rail'
    return 'bridge' if w[2].startswith('bridge') else 'wire'


def wires_of(k):
    return [w for w in M.WIRES if kind(w) == k]


def draw_under(o, which):
    for f, t, note in wires_of(which):
        col = net_colour(note)
        (x0, y0), (x1, y1) = pos(f, True), pos(t, True)
        if which == 'wire':
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2 - 14
            o.append('<path d="M%.0f %.0f Q%.0f %.0f %.0f %.0f" fill="none" stroke="%s" stroke-width="2.5" stroke-dasharray="7,3"/>' % (
                x0, y0, mx, my, x1, y1, col))
            for x, y in ((x0, y0), (x1, y1)):
                o.append('<circle cx="%.0f" cy="%.0f" r="3.5" fill="%s"/>' % (x, y, col))
        else:
            o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="%d" stroke-linecap="round"/>' % (
                x0, y0, x1, y1, col, 6 if which == 'rail' else 4))


def draw_pins_under(o):
    """Every lead and pin from the top side, seen from underneath as solder joints."""
    for p in PARTS.values():
        for i, m, _ in p.pins:
            dot(o, HN(i, m), '#8a8a8a', True, r=5)
    for h, _ in charger_pads():
        dot(o, h, '#8a8a8a', True, r=5)


# ------------------------------------------------------------------ steps
STEPS = []


def step(key, title, view, draw, sub, notes, body, table):
    STEPS.append(dict(key=key, title=title, view=view, draw=draw, sub=sub, notes=notes, body=body, table=table))


def rows_parts(names, note):
    return [(n, ', '.join(pins(n)), note(n)) for n in names]


def res_note(n):
    a, b = pins(n)
    if span(a, b) >= 3:
        return 'flat, legs in %s and %s' % (a, b)
    return 'body over %s, lead bent %s into %s' % (a, 'sideways' if a[0] != b[0] else 'back', b)


def diode_note(n):
    p = dict((lab, HN(i, m)) for i, m, lab in PARTS[n].pins)
    solar = ' (for the solar input; fit it anyway)' if ('solar' in n or n.startswith('Z ')) else ''
    return '%s**band (K) at %s**, other end (A) at %s%s' % ('flat, ' if span(p['K'], p['A']) >= 3 else '', p['K'], p['A'], solar)


def cap_note(n):
    a, b = pins(n)
    (i0, m0), (i1, m1) = H(a), H(b)
    if i0 != i1 and m0 != m1:
        return 'corner to corner: pull the legs in slightly, lean the body away from the ESP'
    return 'middle hole %s stays empty' % HN((i0 + i1) // 2, (m0 + m1) // 2)


def what(rows):
    return [(f, t, n.split(': ', 1)[1]) for f, t, n in rows]


ESP = {lab: HN(i, m) for i, m, lab in PARTS['ESP32-C6'].pins}
RAILS = [(f, t, n.split(':')[0]) for f, t, n in wires_of('rail')]


def esp_rows():
    side = lambda labs: '%s–%s' % (ESP[labs[0]], ESP[labs[-1]])
    return side(['5V', '8']), side(['TX16', '7'])


def rails_text():
    return ', '.join('%s %s–%s' % ('GND' if 'GND' in k else 'battery +', f, t) for f, t, k in RAILS)


LEAD = {lab: HN(i, m) for n in ('USB leads', 'USB-C breakout', 'Solar leads', 'Battery pins', 'JST battery') if n in PARTS
        for i, m, lab in PARTS[n].pins}
CH = {pad: h for pad, h, _ in M.CHARGER}
FLAT = span(*pins('R ADC1 1k')) >= 3

step('res', 'Resistors (%d)' % len(RES), 'top', [draw_res],
     ('Top side. All of them lie flat across 4 holes (legs 3 spaces apart). Either way round.' if FLAT else
      'Top side. All of them stand up: body over the first hole, the other lead bent back into the second. Either way round.'),
     ['Colour bands (4-band): 1k = brown black red, 1M = brown black green. Not sure? Measure it.'],
     ("""First mark the board: **row 1 = the end toward the phone jacks**, **column a = the edge with the row numbers printed on
it** (toward the battery).

Resistors have no direction. Bend both legs down 90° right at the body so they drop into holes 4 apart (3 spaces), push
them through so the body lies flat on the board, splay the legs slightly underneath, solder, and **trim to ~1 mm**. Keep
the trimmed legs: they make good bridges later. The holes under each body stay empty.""" if FLAT else
      """Resistors have no direction. Bend the top lead back down, push both leads through, splay them slightly underneath so
the part stays put, solder, and **trim to ~1 mm**. Keep the trimmed legs: they make good bridges later."""),
     rows_parts([n for n, _ in RES], res_note))
step('diodes', 'Diodes (3 × 1N5819, 1 × 6.2 V zener)', 'top', [draw_diodes],
     'Top side. Direction matters: the silver/white band is the cathode (K), drawn at the end where it goes.',
     (['Each diode lies flat across 4 holes. Put the band end at the hole marked K.'] if FLAT else
      ['A ring on the body = band at the bottom of the standing body. A white tab on the lead = band at the top (that lead is K).']),
     ("""These **only work one way round**; the band end is the cathode (K). Bend the legs like the resistors (4 holes)
and lay each one flat with its **band at the K hole** in the table and the picture. Check each one before soldering.""" if FLAT else
      """These **only work one way round**; the band end is the cathode (K). Each one stands up with its body over the first
hole in the table. Check each one against the table before soldering."""),
     rows_parts([n for n, _ in DIODES], diode_note))
step('caps', 'Ceramic capacitors (4 × 100 nF, 1 × 10 µF)', 'top', [draw_caps],
     'Top side. Either way round. They stand up with their legs 3 holes apart: the middle hole stays empty.',
     ['100 nF is marked 104, 10 µF is marked 106.'],
     """No direction. Push them straight down so the body sits low; don't bend the legs at the body.""",
     rows_parts([n for n, _ in CAPS], cap_note))
step('sockets', 'Sockets and connectors: ESP (2 × 10), USB-C (1 × 6), JST: battery, charger (3)', 'top', [draw_sockets],
     'Top side. The ESP and USB-C board plug into sockets, the battery and charger into JST-XH headers: everything unplugs.',
     ['The ESP and the USB-C board are NOT plugged in yet: that happens after the checks at the end.'],
     """All the header parts at once:

1. **ESP socket:** two 10-way female socket strips in **%s** and **%s**. To get them straight, push the strips onto the
   ESP's own pins, set ESP + sockets on the board (chip side up, USB-C over the column-a edge), solder one end pin of each
   strip, check they sit flat, solder the rest, then lift the ESP back out.
2. **USB-C socket:** one 6-way socket strip in **%s**, the same way with the breakout: its USB-C socket points **out past
   the row-24 end**, pins VBUS, GND, CC1, D−, D+, CC2 from column b. Solder, then lift it out.
3. **JST-XH headers** (2.5 mm pitch, fits the holes; they're keyed, so plugs only go in one way). It's tight around
   a19–a23 but they fit:
   - **Battery:** 2-pin top-entry header in **%s (−) / %s (+)**. Before soldering, hold the cell's plug against it: its
     **red wire must land on %s**. Turn the header round if it doesn't.
   - **Charger +:** 2-pin top-entry header in **d19 (BATT +) / e19 (PWR +)**.
   - **Charger LOAD +:** 2-pin top-entry header in **j20–j21** (both pins are on the battery + rail).
   - **Charger GND:** 3-pin **right-angle** header in **a21 / a22 / a23** (PWR −, BATT −, LOAD −), opening outward over the
     column-a edge.""" % (esp_rows()[0], esp_rows()[1], '%s–%s' % (LEAD.get('VBUS', '-'), LEAD.get('CC2', '-')),
                          LEAD['B-'], LEAD['B+'], LEAD['B+']),
     [('ESP socket', '%s, %s' % esp_rows(), 'ESP plugs in chip side up, USB-C over the column-a edge'),
      ('USB-C socket', '%s–%s' % (LEAD.get('VBUS', '-'), LEAD.get('CC2', '-')), 'VBUS, GND, CC1, D−, D+, CC2; its socket points past row 24'),
      ('JST battery (2-pin)', '%s (−), %s (+)' % (LEAD['B-'], LEAD['B+']), 'red wire of the cell\'s plug on %s' % LEAD['B+']),
      ('JST charger + (2-pin)', 'd19 (BATT +), e19 (PWR +)', 'top entry'),
      ('JST charger LOAD + (2-pin)', 'j20, j21', 'top entry, both pins battery +'),
      ('JST charger GND (3-pin)', 'a21 (PWR −), a22 (BATT −), a23 (LOAD −)', 'right angle, opening over the column-a edge')])
step('charger', 'Charger: prepare it, put JST plugs on its wires (3 plugs)', 'top', [draw_charger],
     'Top side. The charger (30.5 × 31.5 mm) sits OFF the board, past row 24; its wires plug into the JST headers from step 4.',
     ['Nothing is soldered to the board in this step: the charger plugs in, so it can be swapped.'],
     """The charger board (30.5 × 31.5 mm) is wider than the perfboard, and its bulk capacitor is 16 mm across and 26 mm tall,
so it sits **off the board**, beside the row-24 end, on wires about 6–8 cm long.

![charger board](renders/build-charger.png)

1. On the bench first: remove the small **103** (10 kΩ) resistor beside the **THERM** label and solder the 10 kΩ NTC's
   two leads to its pads (the NTC gets taped to the cell later). If its leads don't reach the cell, extend them with
   **30 AWG silicone stranded wire** and heat-shrink each joint.
2. The bulk capacitor has its own footprint on the charger, at the top right (the outline with **+** on one side):
   **long leg into the + hole**, stripe side into the other. To make it lie on its side, bend both leads 90° about 2 mm
   from the body first (hold the lead with pliers at the body so the bend doesn't strain it).
3. **Power wires (they carry the battery and motor current): 6 pieces of 22 AWG stranded insulated wire** (the white
   two-conductor solar wire, split in two), 6–8 cm each. Solder one end of each to the charger's PWR +, PWR −, BATT +, BATT −, LOAD + and LOAD − holes. Mark the +
   wires before you start.
4. **Crimp JST-XH pins** on the other ends and push them into the housings, matching the headers from step 4:
   - **3-pin housing (GND):** PWR − / BATT − / LOAD −, in that order, to match a21 / a22 / a23.
   - **2-pin housing (charger +):** BATT + on the d19 side, PWR + on the e19 side.
   - **2-pin housing (LOAD +):** LOAD + in either position (both pins of that header are battery +).
   Check each one with the meter against the board before plugging in: a swapped + and − here can damage parts.
5. Leave the small edge pads (CE, TE, PROG2, SEL) unconnected. The board has no STAT pad; the ESP watches the input
   voltage instead (the input-power 1 MΩ pair from step 1).

(Pad names assumed from the Adafruit-style board: check them against the real board before wiring.)""",
     [(pad, h, net) for pad, h, net in M.CHARGER])
step('leads', 'Leads from the RJ12 boards (%d)' % len(PARTS['Port leads'].pins), 'top', [draw_leads],
     'Top side. Each lead goes in from the top. Pin 1 is the square pad on each RJ12 board.',
     ['Let the RJ12 boards hang off the end and tape them down while you work underneath.'],
     """Each RJ12 board connects with 6 leads, 5–8 cm long. Use **22 AWG stranded insulated wire** (the white two-conductor
wire, split) for **battery + and GND**, which carry the motor current, and **30 AWG silicone stranded wire** for the four
signals (IN1, IN2, EN, angle). Solder each lead to its RJ12 pad (pin 1 = square pad), then into the hole in the table
from the top. Trim underneath to ~1 mm.""",
     None)
step('solar', 'Solar lead (optional)', 'top', [draw_solar],
     'Top side. Only if you use a solar panel: its lead goes in from the top.',
     ['Skip this step for USB-C charging only. You can add it later: the holes stay free.'],
     """**Optional.** Only if this controller gets a solar panel. The lead is the **white 22 AWG two-conductor wire** (the
solar extension, cut to length). Solder its **+ → %s** and **− → %s** (mark the + conductor first)
(%s is on the GND rail). Trim underneath.

Without solar, skip it: the board charges over USB-C alone. D2 and the zener from step 2 are only there for the
solar input, but fit them anyway so a panel can be added later without re-soldering.""" % (LEAD['S+'], LEAD['S-'], LEAD['S-']),
     [('Solar +', LEAD['S+'], 'to D2\'s anode (bridge in step 9)'), ('Solar −', LEAD['S-'], 'GND rail')])
step('wires', 'Insulated wires underneath (%d)' % len(wires_of('wire')), 'bottom', [draw_under, 'wire'],
     'Bottom view: flip the board over its long edge, row 1 still on the left, column a now at the TOP. Grey = done already.',
     ['Dashed = 30 AWG silicone stranded insulated wire, dots = its two ends. Colours: black GND, orange 5V, blue signal.'],
     """All of these are **30 AWG silicone stranded insulated wire**. They go in **before** the bridges and rails, while their
holes are still open. For each wire: cut it a little long,
strip ~2 mm at each end, push the ends into the two holes **from underneath**, solder, trim. Beep each wire out with the
meter as you go.""",
     what(wires_of('wire')))
step('bridges', 'Bare bridges underneath (%d)' % len(wires_of('bridge')), 'bottom', [draw_under, 'bridge'],
     'Bottom view. Each bridge joins two neighbouring holes in a straight line.',
     ['Use trimmed resistor / diode legs or 22 AWG solid tinned bare wire, laid flat across the pads, soldered at both ends.'],
     """A bridge is a short piece of **bare solid wire**: a trimmed resistor or diode leg, or **22 AWG solid tinned copper
(bus) wire**, laid across neighbouring pads and soldered at
both ends; don't rely on a solder blob alone. Work one area at a time and check each with the meter: the two ends beep,
and neither beeps to the pad next to it.""",
     what(wires_of('bridge')))
step('rails', 'Rails (%d)' % len(RAILS), 'bottom', [draw_under, 'rail'],
     'Bottom view. Long bare wires: ' + rails_text() + '.',
     ['Solder each rail at every hole it passes, including the ones that already have wires or leads.'],
     """Last: lay a straight piece of **22 AWG solid tinned copper (bus) wire** for each rail (%s), soldering it at every hole
it passes. Where two GND rails
meet at a corner, solder them together there. Then do the checks in step 11.""" % rails_text(),
     what(wires_of('rail')))


def need():
    """What each step uses, with counts (drawn from the layout)."""
    cnt = lambda pairs: {v: sum(1 for _, x in pairs if x == v) for _, v in pairs}
    r, c = cnt(RES), cnt(CAPS)
    rail_mm = []
    for f, t, k in RAILS:
        (i0, m0), (i1, m1) = H(f), H(t)
        rail_mm.append('%s %s–%s ~%d mm' % ('GND' if 'GND' in k else 'battery +', f, t, (abs(i0 - i1) + abs(m0 - m1)) * 2.54 + 10))
    socks = socket_rows()
    n_esp = sum(1 for n, _ in socks if n == 'ESP32-C6')
    usb_pins = [len(hs) for n, hs in socks if n == 'USB-C breakout']
    out = {
        'res': ['%s × %s resistor' % (n, v.replace('1k', '1 kΩ').replace('1M', '1 MΩ')) for v, n in r.items()],
        'diodes': ['3 × 1N5819 diode', '1 × 6.2 V zener'],
        'caps': ['%d × %s ceramic capacitor' % (n, {'100n': '100 nF (104)', '10µ': '10 µF (106)'}[v]) for v, n in c.items()],
        'sockets': ['%d × 10-way female header socket (pin stand)' % n_esp] +
                   ['1 × %d-way female header socket (cut from a strip)' % u for u in usb_pins] +
                   ['3 × JST-XH 2-pin top-entry header', '1 × JST-XH 3-pin right-angle header'],
        'charger': ['1 × MCP73871 charger board (+ its bulk capacitor)', '1 × 10 kΩ NTC thermistor',
                    '6 × 22 AWG stranded insulated wire, 6–8 cm', '1 × JST-XH 3-pin housing', '2 × JST-XH 2-pin housing', '6 × JST-XH crimp pins'],
        'leads': ['3 × RJ12 breakout board', '6 × 22 AWG stranded insulated wire, 5–8 cm (battery + and GND)',
                  '12 × 30 AWG silicone stranded wire, 5–8 cm (signals)'],
        'solar': ['1 × white 22 AWG two-conductor lead to the panel: optional'],
        'wires': ['%d × 30 AWG silicone stranded insulated wire (cut to length)' % len(wires_of('wire'))],
        'bridges': ['%d × short bare wire: the ~%d leg offcuts saved from steps 1-3, the rest cut from 22 AWG solid tinned bus wire' % (
            len(wires_of('bridge')), 2 * (len(RES) + len(DIODES) + len(CAPS)))],
        'rails': ['%d × 22 AWG solid tinned bus wire: %s' % (len(RAILS), '; '.join(rail_mm))],
    }
    return out


NEED = need()


def render_step(k):
    st = STEPS[k]
    bottom = st['view'] == 'bottom'
    o = board('Step %d: %s' % (k + 1, st['title']), st['sub'], bottom)
    prev = []
    if bottom:
        draw_pins_under(prev)
        for s2 in STEPS[:k]:
            if s2['view'] == 'bottom':
                draw_under(prev, s2['draw'][1])
    else:
        for s2 in STEPS[:k]:
            for f in s2['draw']:
                f(prev)
    if k == 0 and not bottom:                          # first picture: where things will go, and which end is which
        for name, hs in socket_rows():
            (x0, y0), (x1, y1) = pos(hs[0]), pos(hs[-1])
            prev.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="3" fill="none" stroke="#555" stroke-dasharray="5,4"/>' % (
                min(x0, x1) - 12, min(y0, y1) - 12, abs(x1 - x0) + 24, abs(y1 - y0) + 24))
        o.append('<text x="%d" y="%.0f" font-size="13" fill="#c00" font-weight="bold">&#8592; row 1: toward the phone jacks</text>' % (
            MX - 40, MY + S * (M.NM - 1) + S * 1.5))
        o.append('<text x="%.0f" y="%.0f" font-size="13" fill="#c00" font-weight="bold" text-anchor="end">row 24: toward the USB-C end &#8594;</text>' % (
            MX + S * (M.NI - 1), MY + S * (M.NM - 1) + S * 1.5))
        o.append('<text x="%.0f" y="%.0f" font-size="11" fill="#555">dashed = where the sockets go later (step 4)</text>' % (
            MX + S * 7, MY + S * (M.NM - 1) + S * 1.5))
    muted(o, prev)
    if bottom:
        draw_under(o, st['draw'][1])
    else:
        for f in st['draw']:
            f(o)
    name = '%sstep-%02d.svg' % (PRE, k + 1)
    finish(o, name, ['You need: ' + ', '.join(NEED.get(st['key'], []))] + list(st['notes']))
    return name


def render_done():
    o = board('Finished: top side', 'Top view, every part and lead in place, the ESP and the USB-C board plugged in.')
    for s2 in STEPS:
        if s2['view'] == 'top':
            for f in s2['draw']:
                f(o)
    draw_esp(o)
    draw_usb(o)
    finish(o, PRE + 'done-top.svg')
    o = board('Finished: underside', 'Bottom view, everything in place. Grey dots = joints of the parts and leads from the top.', True)
    draw_pins_under(o)
    for k in ('wire', 'bridge', 'rail'):
        draw_under(o, k)
    lx, ly = MX - 40, HGT - 60
    for k, (t, c) in enumerate((('GND', NET_COL['GND']), ('battery +', NET_COL['VBAT']), ('5V', NET_COL['5V']),
                                ('3V3', NET_COL['3V3']), ('signal', NET_COL['sig']))):
        o.append('<rect x="%d" y="%.0f" width="18" height="6" fill="%s"/><text x="%d" y="%.0f" font-size="12">%s</text>' % (
            lx + k * 150, ly, c, lx + k * 150 + 24, ly + 7, t))
    finish(o, PRE + 'done-under.svg')
    return [PRE + 'done-top.svg', PRE + 'done-under.svg']


def charger_picture():
    """The Comimark MCP73871 board as in the owner's photo (front, PWR at top left), with what goes where.
    Positions are scaled from the photo (about +/-0.5 mm): measure before relying on them for a footprint."""
    k, ox, oy = 14.0, 330, 90                       # px per mm, board origin (top-left corner) in the picture
    bw, bh = 30.5, 31.5

    def P(x, y):
        return ox + k * x, oy + k * y
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="860" font-family="Helvetica,Arial">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         '<text x="20" y="32" font-size="20" font-weight="bold">Charger board (MCP73871, 30.5 × 31.5 mm): what goes where</text>',
         '<text x="20" y="56" font-size="13" fill="#444">Front side, as in the photo. Drawn from the photo, so positions are approximate.</text>']
    x0, y0 = P(0, 0)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="10" fill="#1a1a1a"/>' % (x0, y0, bw * k, bh * k))
    chip = P(13.0, 13.0)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="#333" stroke="#666"/>' % (chip[0], chip[1], 4.5 * k, 4.5 * k))
    o.append('<text x="%.0f" y="%.0f" font-size="11" fill="#aaa" text-anchor="middle">MCP73871</text>' % (chip[0] + 2.25 * k, chip[1] + 2.5 * k))
    for i in range(3):                               # status LEDs (STAT1, STAT2, PG): the only place status shows
        lx, ly = P(5.5, 9.0 + 1.6 * i)
        o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="#c33"/>' % (lx, ly, 3.5 * k, 0.9 * k))
    lx, ly = P(9.4, 9.2)
    o.append('<text x="%.0f" y="%.0f" font-size="11" fill="#bbb">status LEDs</text>' % (lx, ly + 18))
    for i in range(5):                               # small edge pads
        ex, ey = P(1.6, 7.6 + 2.54 * i)
        o.append('<circle cx="%.0f" cy="%.0f" r="9" fill="#c9a400"/><circle cx="%.0f" cy="%.0f" r="4" fill="#1a1a1a"/>' % (ex, ey, ex, ey))
    # bulk capacitor footprint (top right) and THERM resistor
    cx, cy = P(22.4, 3.1)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="none" stroke="#fff" stroke-width="2"/>' % (cx, cy, 3.8 * k, 5.0 * k))
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="#fff"/>' % (cx + 2.6 * k, cy, 1.2 * k, 5.0 * k))
    o.append('<text x="%.0f" y="%.0f" font-size="18" fill="#fff" font-weight="bold">+</text>' % (cx + 0.5 * k, cy + 3.0 * k))
    hx, hy = P(27.1, 5.8)
    o.append('<circle cx="%.0f" cy="%.0f" r="9" fill="#c9a400"/><circle cx="%.0f" cy="%.0f" r="4" fill="#1a1a1a"/>' % (hx, hy, hx, hy))
    tx, ty = P(23.2, 19.3)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="#555" stroke="#0a7a3a" stroke-width="3"/>' % (tx - 0.8 * k, ty - 0.5 * k, 1.6 * k, 1.0 * k))
    o.append('<text x="%.0f" y="%.0f" font-size="12" fill="#ddd" transform="rotate(90 %.0f %.0f)">THERM</text>' % (tx + 1.6 * k, ty - 3.5 * k, tx + 1.6 * k, ty - 3.5 * k))
    holes = [('GND', 4.2, 3.5), ('PWR', 8.8, 3.5), ('GND', 3.8, 27.9), ('BATT', 8.8, 27.9), ('LOAD', 20.8, 27.9), ('GND', 25.6, 27.9)]
    for name, x, y in holes:
        px, py = P(x, y)
        o.append('<circle cx="%.0f" cy="%.0f" r="24" fill="#c9a400"/><circle cx="%.0f" cy="%.0f" r="12" fill="#fff"/>' % (px, py, px, py))
        o.append('<text x="%.0f" y="%.0f" font-size="11" fill="#fff" font-weight="bold" text-anchor="middle">%s</text>' % (
            px, py + (-30 if y < 15 else 42), name))
    # callouts
    def call(px, py, tx_, ty_, lines, c='#0a7a3a', anchor='start'):
        o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="2"/>' % (px, py, tx_, ty_, c))
        o.append('<circle cx="%.0f" cy="%.0f" r="4" fill="%s"/>' % (px, py, c))
        for i, t in enumerate(lines):
            o.append('<text x="%.0f" y="%.0f" font-size="%d" fill="%s" text-anchor="%s" font-weight="%s">%s</text>' % (
                tx_ + (6 if anchor == 'start' else -6), ty_ + 4 + 17 * i, 14 if i == 0 else 12, c if i == 0 else '#333',
                anchor, 'bold' if i == 0 else 'normal', t))
    # which plug and position each pad's wire goes to (the plugs are drawn below the board)
    jst = 'JST charger GND' in PARTS
    plugs = [('A', '3-pin plug', 'into the angled header %s–%s' % (CH['PWR - / GND'], CH['LOAD -']),
              [('PWR −', CH['PWR - / GND'], '#222'), ('BATT −', CH['BATT -'], '#222'), ('LOAD −', CH['LOAD -'], '#222')]),
             ('B', '2-pin plug', 'into the header %s–%s' % (CH['BATT +'], CH['PWR + (input)']),
              [('BATT +', CH['BATT +'], '#d62728'), ('PWR +', CH['PWR + (input)'], '#d62728')]),
             ('C', '2-pin plug', 'into the header j20–j21', [('LOAD +', CH['LOAD + (output)'], '#d62728'), ('(empty)', 'j21', '#999')])]
    where = {w: (pl, hole) for pl, _, _, cav in plugs for w, hole, _ in cav}
    tags = [('PWR −', 4.2, 3.5, -1), ('PWR +', 8.8, 3.5, -1), ('BATT −', 3.8, 27.9, 1), ('BATT +', 8.8, 27.9, 1),
            ('LOAD +', 20.8, 27.9, 1), ('LOAD −', 25.6, 27.9, 1)]
    for w, x, y, up in tags:
        px, py = P(x, y)
        pl, hole = where[w]
        c = '#d62728' if '+' in w else '#222'
        ty_ = py + up * 62
        o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="3"/>' % (px, py + up * 24, px, ty_ - up * 12, c))
        o.append('<rect x="%.0f" y="%.0f" width="62" height="22" rx="4" fill="#fff" stroke="%s" stroke-width="2"/>' % (px - 31, ty_ - 11, c))
        o.append('<text x="%.0f" y="%.0f" font-size="12" font-weight="bold" fill="%s" text-anchor="middle">%s %s</text>' % (
            px, ty_ + 4, c, pl, hole))
    by = oy + bh * k + 120
    o.append('<text x="40" y="%.0f" font-size="15" font-weight="bold">%s</text>' % (
        by - 30, 'The three JST-XH plugs: crimp each wire into the position shown (each position is named after the board hole it plugs onto)'))
    for n, (pl, kind_, into, cav) in enumerate(plugs):
        hx0 = 60 + n * 340
        w_ = 96 * len(cav)
        o.append('<text x="%.0f" y="%.0f" font-size="14" font-weight="bold">Plug %s: %s</text>' % (hx0, by, pl, kind_))
        o.append('<text x="%.0f" y="%.0f" font-size="12" fill="#444">%s</text>' % (hx0, by + 18, into))
        o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="74" rx="6" fill="#f4f1e8" stroke="#777" stroke-width="2"/>' % (hx0, by + 30, w_))
        for q, (w, hole, c) in enumerate(cav):
            cx_ = hx0 + 48 + 96 * q
            o.append('<rect x="%.0f" y="%.0f" width="80" height="58" rx="4" fill="#fff" stroke="#bbb"/>' % (cx_ - 40, by + 38))
            o.append('<text x="%.0f" y="%.0f" font-size="14" font-weight="bold" fill="%s" text-anchor="middle">%s</text>' % (cx_, by + 62, c, w))
            o.append('<text x="%.0f" y="%.0f" font-size="12" fill="#444" text-anchor="middle">→ %s</text>' % (cx_, by + 84, hole))
    o.append('<text x="40" y="%.0f" font-size="12" fill="#444">%s</text>' % (
        by + 130, 'Before plugging in, hold each plug against its header and check every wire lands on the hole named in its position. '
                  'Plug C: LOAD + can go in either position (j20 and j21 are both battery +).'))
    call(cx + 1.9 * k, cy, 790, 100, ['Bulk capacitor goes here', 'long leg (+) in the hole on the + side,', 'stripe side to the other hole;',
                                      'bend the legs 90° first to lay it down'])
    call(tx + 0.8 * k, ty, 790, 280, ['Remove this 103 (10 kΩ) resistor', 'solder the 10 kΩ NTC\'s 2 leads to its pads', '(check: before removing, it reads 10 kΩ)'])
    ex, ey = P(1.6, 12.7)
    call(ex - 10, ey, 300, 330, ['Small edge pads: leave empty', '(CE, TE, PROG2, SEL on the back)', 'There is no STAT pad.'], '#666', 'end')
    o.append('</svg>')
    open(os.path.join(OUT, 'build-charger.svg'), 'w').write('\n'.join(o))
    return 'build-charger.svg'


def polarity():
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="260" font-family="Helvetica,Arial">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         '<text x="20" y="30" font-size="20" font-weight="bold">Which way round?</text>']
    o += ['<line x1="40" y1="110" x2="200" y2="110" stroke="#999" stroke-width="3"/>',
          '<rect x="90" y="96" width="60" height="28" rx="6" fill="#222"/>', '<rect x="136" y="96" width="9" height="28" fill="#ddd"/>',
          '<text x="120" y="80" font-size="14" text-anchor="middle" font-weight="bold">1N5819 / zener</text>',
          '<text x="60" y="150" font-size="13">anode (A)</text>', '<text x="150" y="150" font-size="13" font-weight="bold">band = cathode (K)</text>']
    o += ['<rect x="340" y="70" width="60" height="90" rx="10" fill="#1d3557"/>', '<rect x="340" y="70" width="14" height="90" fill="#ddd"/>',
          '<text x="347" y="120" font-size="16" font-weight="bold" text-anchor="middle">−</text>',
          '<line x1="354" y1="160" x2="354" y2="200" stroke="#999" stroke-width="3"/>', '<line x1="388" y1="160" x2="388" y2="215" stroke="#999" stroke-width="3"/>',
          '<text x="370" y="60" font-size="14" text-anchor="middle" font-weight="bold">charger bulk cap</text>',
          '<text x="300" y="235" font-size="13">stripe / short leg = −</text>', '<text x="410" y="215" font-size="13">long leg = +</text>']
    o += ['<rect x="560" y="90" width="40" height="30" rx="5" fill="#7fb2e5"/>', '<text x="580" y="80" font-size="14" text-anchor="middle" font-weight="bold">ceramic</text>',
          '<text x="580" y="145" font-size="13" text-anchor="middle">any way round</text>',
          '<text x="580" y="165" font-size="13" text-anchor="middle">legs 3 holes apart</text>',
          '<rect x="700" y="96" width="70" height="26" rx="10" fill="#e8c88a"/>', '<text x="735" y="80" font-size="14" text-anchor="middle" font-weight="bold">resistor</text>',
          '<text x="735" y="145" font-size="13" text-anchor="middle">any way round</text>']
    o.append('</svg>')
    open(os.path.join(OUT, 'build-polarity.svg'), 'w').write('\n'.join(o))
    return 'build-polarity.svg'


# ------------------------------------------------------------------ parts list + markdown
def bom():
    count = {}
    for _, v in RES + CAPS:
        count[v] = count.get(v, 0) + 1
    return [
        ('ESP32-C6 SuperMini, with its male pins soldered on', 1, 'plugs in at the end', 'ESP32-C6 SuperMini 5-pack'),
        ('Female header sockets ("pin stands")', '2 × 10 + 1 × 6', '4: ESP and USB-C sockets', 'perfboard kit headers'),
        ('JST-XH header, 2-pin top entry', 3, '4: battery, charger +, charger LOAD +', 'JST-XH kit (to buy)'),
        ('JST-XH header, 3-pin right angle', 1, '4: charger GND', 'JST-XH kit (to buy)'),
        ('JST-XH housings (2-pin × 2, 3-pin × 1) + 6 crimp pins', 1, '5: charger plugs', 'JST-XH kit (to buy)'),
        ('Resistor 1 kΩ', count['1k'], '2', 'resistor kit'),
        ('Resistor 1 MΩ', count['1M'], '2: battery and input-power dividers', 'resistor kit'),
        ('Diode 1N5819', 3, '3', '1N5819 150-pack'),
        ('Zener 6.2 V', 1, '3', 'zener kit'),
        ('Ceramic capacitor 100 nF (104)', count['100n'], '4', 'ceramic capacitor kit'),
        ('Ceramic capacitor 10 µF (106)', count['10µ'], '4', 'ceramic capacitor kit'),
        ('MCP73871 charger board, 30.5 × 31.5 mm, off the board (+ its 16 × 26 mm bulk capacitor)', 1, '6', 'Comimark MCP73871'),
        ('NTC thermistor 10 kΩ', 1, '6', 'NTC 10-pack'),
        ('22 AWG stranded insulated wire (the white two-conductor, split)', '6 × 6-8 cm + 6 × 5-8 cm',
         '5 (charger power), 6 (RJ12 battery + / GND)', 'white 2-conductor 22 AWG'),
        ('RJ12 breakout board', 3, '7 (%d leads)' % len(PARTS['Port leads'].pins), 'RJ11/RJ12 breakout 4-pack'),
        ('USB-C breakout (Cermant), with its 6 male pins', 1, 'plugs in at the end', 'USB-C breakout 10-pack'),
        ('Solar lead (optional)', 1, '7 (2 leads, optional)', 'solar panel + extension'),
        ('30 AWG silicone stranded insulated wire', '%d + 12 pieces' % len(wires_of('wire')), '8 (board wires), 6 (RJ12 signals)',
         '30 AWG silicone wire'),
        ('Bare wire or trimmed resistor legs', '%d bridges + %d rails' % (len(wires_of('bridge')), len(wires_of('rail'))), '9, 10',
         '22 AWG solid tinned bus wire (to buy, ~0.4 m per board) + leg offcuts'),
        ('Perfboard 3 × 7 cm (a–j × 1–24)', 1, 'all', 'perfboard kit'),
        ('18650 cell with JST-XH plug', 1, '11', '18650 cell'),
    ]


def write_md():
    o = ['# Building the controller dev board, step by step', '',
         'For the kit\'s **3 × 7 cm perfboard (columns a–j, rows 1–24)**. Everything here (pictures, tables, counts) is generated',
         'from the layout in [DevBoardR.py](../hardware/mechanical/fusion/ControllerV4/DevBoardR.py) (ESP turned across the',
         'board, resistors and diodes lying flat) by [`tools/devboard_guide.py`](../tools/devboard_guide.py);',
         '[`tools/devboard_check.py`](../tools/devboard_check.py) checks every connection, no shorts, no parts touching, and that',
         'every hole holds exactly one thing (a part leg, a lead or a wire end).', '',
         '**Totals:** %d parts and leads on top, %d insulated wires, %d bare bridges, %d rails.' % (
             sum(len(p.pins) for p in PARTS.values()), len(wires_of('wire')), len(wires_of('bridge')), len(RAILS)), '',
         '**Order:** all parts and leads first (steps 1–7, holes still open; step 7, solar, is optional), then the insulated',
         'wires (8), then the bare bridges (9), then the rails (10); the ESP and the USB-C board plug in last (11). That way solder never fills a hole that something still has to go through. Each',
         'step does one kind of part, and in its picture that step is in colour while everything already done is grey.', '',
         '## Parts for one board', '', '| Part | Count | Step | From (BOM) |', '|---|---|---|---|']
    o += ['| %s | %s | %s | %s |' % r for r in bom()]
    o += ['', 'For all 3 controllers, triple every count. Links and prices: [BOM](../hardware/BOM.md).', '',
          '## Which parts have a direction?', '', '![which way round](renders/build-polarity.png)', '',
          '| Part | Direction matters? | How to tell |', '|---|---|---|',
          '| Resistors | **No** | either way round |',
          '| Ceramic capacitors | **No** | either way round; legs 3 holes apart, the middle hole stays empty |',
          '| **1N5819 diodes, 6.2 V zener** | **YES** | the silver/white **band is the cathode (K)** |',
          '| **ESP32-C6** | **YES** | chip side up, 5V in %s, TX in %s |' % (ESP['5V'], ESP['TX16']),
          '| **Battery JST header** | **YES** | keyed, but check before soldering it: the cell\'s red wire must land on **%s (+)** |' % LEAD['B+'],
          '| **Charger bulk capacitor** (on the charger board) | **YES** | stripe = −, long leg = + |',
          '| USB-C and solar leads, charger pads | **YES** | follow the tables |', '',
          'A reversed diode just won\'t conduct; a reversed electrolytic or battery can damage parts. Check those twice.', '',
          '## Tools and tips',
          '- Soldering iron (~330 °C), thin solder, flush cutters, tweezers, multimeter (beep / continuity mode), marker.',
          '- Place parts on the **top**, solder **underneath**, trim leads to ~1 mm.',
          '- Use just enough solder for a small cone on the pad. Too much spreads to the next pad or fills holes.',
          '- If a hole fills by accident, heat it and clear it with a desoldering pump or wick before going on.', '']
    hdr = {'esp': ('Part', 'Holes', 'Note'), 'sockets': ('Part', 'Holes', 'Note'), 'res': ('Resistor', 'Holes', 'How'), 'diodes': ('Diode', 'Holes', 'Direction'),
           'caps': ('Capacitor', 'Holes', 'Note'), 'batt': ('Part', 'Holes', 'Note'), 'charger': ('Charger pad', 'Board hole', 'Net'),
           'wires': ('From', 'To', 'What'), 'solar': ('Lead', 'Hole', 'Goes to'), 'bridges': ('From', 'To', 'What'), 'rails': ('From', 'To', 'What')}
    for k, st in enumerate(STEPS):
        o += ['## Step %d: %s' % (k + 1, st['title']), '', '**You need:** ' + ', '.join(NEED.get(st['key'], [])) + '.', '',
              '![step %d](renders/build-step-%02d.png)' % (k + 1, k + 1), '', st['body'], '']
        if st['key'] == 'leads':
            leads = {lab: HN(i, m) for i, m, lab in PARTS['Port leads'].pins}
            o += ['| RJ12 pin | Wire | Port 1 | Port 2 | Port 3 |', '|---|---|---|---|---|']
            for pin, sig in ((1, 'VBAT'), (2, 'IN1'), (3, 'GND'), (4, 'ANG'), (5, 'EN'), (6, 'IN2')):
                o.append('| %d %s | %s | %s | %s | %s |' % (pin, {'VBAT': 'battery +', 'ANG': 'angle'}.get(sig, sig),
                                                          '22 AWG stranded' if sig in ('VBAT', 'GND') else '30 AWG silicone',
                                                          leads['P1 ' + sig], leads['P2 ' + sig], leads['P3 ' + sig]))
            o += ([''] + ['| Lead | Hole |', '|---|---|', '| USB-C VBUS (+) | %s |' % LEAD['V+'], '| USB-C GND (−) | %s |' % LEAD['V-']]
                  if 'V+' in LEAD else []) + ['']
        else:
            o += ['| %s |' % ' | '.join(hdr[st['key']]), '|---|---|---|'] + ['| %s | %s | %s |' % r for r in st['table']] + ['']
    o += ['## Step %d: checks, then plug in the ESP and the USB-C board' % (len(STEPS) + 1), '',
          '**You need:** multimeter, 1 × ESP32-C6 SuperMini (its male pins soldered on)%s, 1 × 18650 cell with JST-XH plug.' % (
              ', 1 × USB-C breakout (its 6 male pins soldered on)' if 'USB-C breakout' in PARTS else ''), '',
          '![finished top](renders/build-done-top.png)', '', '![finished underside](renders/build-done-under.png)', '',
          'The battery + rail (%s) gets most of its connections from the top: the three port leads and the charger\'s LOAD +' % rails_text().split(', ')[-1],
          'wire (%s). The cell never connects to the rail directly: battery + (%s) goes to the charger\'s BATT + pad and the' % (CH['LOAD + (output)'], LEAD['B+']),
          'charger feeds the rail from LOAD +.', '',
          'With the ESP and the USB-C board still **out** of their sockets:', '',
          '1. Meter, beep mode, no power: GND (%s) to battery + (%s): **no beep**. GND to 5V (%s): no beep. GND to 3V3 (%s):' % (
              RAILS[0][0], [f for f, t, k in RAILS if 'VBAT' in k][0], ESP['5V'], ESP['3V3']),
          '   no beep. GND to the battery + pin (%s): no beep. GND to the PWR node (%s): no beep.' % (LEAD['B+'], CH['PWR + (input)']),
          '2. Plug the ESP into its socket (chip side up, USB-C over the column-a edge) and the USB-C board into its socket',
          '   (its USB-C pointing out past row 24). Then plug USB into the **ESP\'s own** USB-C only (battery unplugged): its LED',
          '   should light; upload the test sketch.',
          '3. Unplug USB, then push the cell\'s plug onto %s/%s (**red on %s**). Measure %s to %s: about the cell voltage' % (
              LEAD['B-'], LEAD['B+'], LEAD['B+'], [f for f, t, k in RAILS if 'VBAT' in k][0], RAILS[0][0]),
          '   (3.0–4.2 V).',
          '4. Never plug USB into the ESP and the battery at the same time unless D3 is fitted.', '']
    open(DOC, 'w').write('\n'.join(o))


def main():
    if STRAIGHT:
        names = [render_step(k) for k in range(len(STEPS))] + render_done()
    else:
        names = [render_step(k) for k in range(len(STEPS))] + render_done() + [charger_picture(), polarity()]
    for old in ('build-1-esp', 'build-2-parts', 'build-3-underside'):
        for ext in ('.svg', '.png'):
            p = os.path.join(OUT, old + ext)
            if os.path.exists(p):
                os.remove(p)
    if not STRAIGHT:
        write_md()
    if '--png' in sys.argv:
        for n in names:
            svg = os.path.abspath(os.path.join(OUT, n))
            head = open(svg).read(400)
            w = head.split('width="')[1].split('"')[0]
            h = head.split('height="')[1].split('"')[0]
            subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                            '--window-size=%s,%s' % (w, h), '--screenshot=' + svg[:-4] + '.png', 'file://' + svg],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print('wrote', ', '.join(names), 'and docs/dev-board-build.md')


if __name__ == '__main__':
    main()
