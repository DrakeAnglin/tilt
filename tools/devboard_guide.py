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
spec = importlib.util.spec_from_file_location('cv4', os.path.join(HERE, '../hardware/mechanical/fusion/ControllerV4/ControllerV4.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
H, HN, COLS = M.H, M.HN, M.COLS
OUT = os.path.join(HERE, '../docs/renders')
DOC = os.path.join(HERE, '../docs/dev-board-build.md')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

S = 30.0                     # px per hole pitch
MX, MY = 70, 90              # margins
W = int(MX * 2 + S * (M.NI - 1) + 230)
HGT = int(MY + S * (M.NM - 1) + 120)

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
    y = MY + S * (M.NM - 1) + S * 1.5
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


def resistor(o, a, b, text):
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
    x0, y0 = pos('b1')
    x1, y1 = pos('h10')
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="5" fill="#1b1b1b" opacity="0.85"/>' % (
        x0 - 22, y1 - 14, S * 9 + 44, (y0 - y1) + 28))
    o.append('<rect x="%.0f" y="%.0f" width="48" height="74" rx="4" fill="#bbb" stroke="#666"/>' % (x0 - 70, (y0 + y1) / 2 - 37))
    o.append('<text x="%.0f" y="%.0f" font-size="11" text-anchor="middle" font-weight="bold">USB-C</text>' % (x0 - 46, (y0 + y1) / 2 + 4))
    for i, m, lab in PARTS['ESP32-C6'].pins:
        h = HN(i, m)
        dot(o, h, '#e0b040')
        label(o, h, lab.replace('TX16', 'TX').replace('RX17', 'RX'), dy=22 if h[0] == 'b' else -12, color='#fff', size=10)
    o.append('<text x="%.0f" y="%.0f" font-size="16" fill="#fff" text-anchor="middle" font-weight="bold">ESP32-C6 (chip up)</text>' % (
        (x0 + x1) / 2, (y0 + y1) / 2 + 5))


def draw_res(o):
    for n, txt in RES:
        a, b = pins(n)
        resistor(o, a, b, txt)


def draw_diodes(o):
    for n, txt in DIODES:
        p = dict((lab, HN(i, m)) for i, m, lab in PARTS[n].pins)
        body, lead = pins(n)
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


def draw_batt(o):
    for i, m, lab in PARTS['Battery pins'].pins:
        h = HN(i, m)
        c = '#d62728' if lab == 'B+' else '#222'
        dot(o, h, c)
        label(o, h, {'B+': 'B+ (red)', 'B-': 'B− (black)'}[lab], dx=22, dy=4 if lab == 'B+' else 16, color=c, anchor='start')


def charger_pads():
    short = {'PWR + (input)': 'PWR+', 'PWR - / GND': 'PWR−', 'BATT +': 'BAT+', 'BATT -': 'BAT−', 'LOAD + (output)': 'LOAD+',
             'LOAD -': 'LD−'}
    return [(h, short[pad]) for pad, h, _ in M.CHARGER if pad in short]


def draw_charger(o):
    """The charger sits off the board, past the row-24 end; its wires come in to the ringed holes."""
    x0, _ = pos('a24')
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


def draw_leads(o):
    for n in ('Port leads', 'USB leads', 'Solar leads'):
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
    if n.startswith('vbat rail') or 'vbat' in n:
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
    return 'body over %s, lead bent %s into %s' % (a, 'sideways' if a[0] != b[0] else 'back', b)


def diode_note(n):
    p = dict((lab, HN(i, m)) for i, m, lab in PARTS[n].pins)
    return '**band (K) at %s**, other end (A) at %s' % (p['K'], p['A'])


def cap_note(n):
    a, b = pins(n)
    (i0, m0), (i1, m1) = H(a), H(b)
    if i0 != i1 and m0 != m1:
        return 'corner to corner: pull the legs in slightly, lean the body away from the ESP'
    return 'middle hole %s stays empty' % HN((i0 + i1) // 2, (m0 + m1) // 2)


def what(rows):
    return [(f, t, n.split(': ', 1)[1]) for f, t, n in rows]


step('esp', 'ESP32-C6 and its headers', 'top', [draw_esp],
     'Top side. Row 1 toward the phone jacks, column a toward the battery. Chip side UP, USB-C hanging past row 1.',
     ['5V / GND / 3V3 land in column h (h1, h2, h3), TX / RX in column b (b1, b2).'],
     """1. Mark the board with a marker: **row 1 = the end toward the phone jacks**, **column a = the edge toward the battery**.
2. Push two 10-pin header strips into the ESP's **inner** holes (long side down), set the ESP on the perfboard **chip side
   up**, USB-C hanging past row 1: the pins go into **b1–b10** and **h1–h10**.
3. Check before soldering: **5V in h1, GND in h2, 3V3 in h3, TX in b1**. Solder one pin at each corner, check it sits
   flat, then the rest. Keep each joint on its own pad.""",
     [('ESP32-C6', 'b1–b10, h1–h10', 'chip up, USB-C past row 1')])
step('res', 'Resistors (%d)' % len(RES), 'top', [draw_res],
     'Top side. All of them stand up: body over the first hole, the other lead bent back into the second. Either way round.',
     ['Colour bands (4-band): 1k = brown black red, 1M = brown black green. Not sure? Measure it.'],
     """Resistors have no direction. Bend the top lead back down, push both leads through, splay them slightly underneath so
the part stays put, solder, and **trim to ~1 mm**. Keep the trimmed legs: they make good bridges in step 9.""",
     rows_parts([n for n, _ in RES], res_note))
step('diodes', 'Diodes (3 × 1N5819, 1 × 6.2 V zener)', 'top', [draw_diodes],
     'Top side. Direction matters: the silver/white band is the cathode (K). Each label sits on the hole the band goes to.',
     ['A ring on the body = band at the bottom of the standing body. A white tab on the lead = band at the top (that lead is K).'],
     """These **only work one way round**; the band end is the cathode (K). D3 stands with its body over j5, band end down.
For D1, D2 and the zener the body stands over the anode hole and the **bent-back lead is the cathode**, so the band is at
the top. Check each one against the table before soldering.""",
     rows_parts([n for n, _ in DIODES], diode_note))
step('caps', 'Ceramic capacitors (4 × 100 nF, 1 × 10 µF)', 'top', [draw_caps],
     'Top side. Either way round. Legs are 3 holes apart: the middle hole stays empty. The 10µ goes corner to corner.',
     ['100 nF is marked 104, 10 µF is marked 106.'],
     """No direction. Push them straight down so the body sits low; don't bend the legs at the body. The 10 µF goes corner
to corner (j1 to i2): pull its legs in slightly and lean the body **away from the ESP**.""",
     rows_parts([n for n, _ in CAPS], cap_note))
step('batt', 'Battery pins (2 header pins)', 'top', [draw_batt],
     'Top side. Two header pins for the cell\'s JST-XH plug. The plug is NOT keyed on bare pins.',
     ['Mark b24 with a red "+" now: the red wire of the battery plug always goes on b24.'],
     """Snap 2 pins off a header strip and solder them in **a24 (−)** and **b24 (+)**, long side up. Mark **b24 "+"** in red.""",
     [('Battery pins', 'a24 (−), b24 (+)', 'red wire of the plug on b24')])
step('charger', 'Charger: prepare it, wire it in from off the board (3 wire pairs)', 'top', [draw_charger],
     'Top side. The charger (30.5 × 31.5 mm) sits OFF the board, past row 24; its wires come in to the ringed holes.',
     ['b24 already has the battery pin: push the BATT + wire in beside it or solder it to that pin underneath.'],
     """The charger board (30.5 × 31.5 mm) is wider than the perfboard, and its bulk capacitor is 16 mm across and 26 mm tall,
so it sits **off the board**, beside the row-24 end, on wires about 6–8 cm long.

![charger board](renders/build-charger.png)

1. On the bench first: remove the small **103** (10 kΩ) resistor beside the **THERM** label and solder the 10 kΩ NTC's
   two leads to its pads (the NTC gets taped to the cell later).
2. The bulk capacitor has its own footprint on the charger, at the top right (the outline with **+** on one side):
   **long leg into the + hole**, stripe side into the other. To make it lie on its side, bend both leads 90° about 2 mm
   from the body first (hold the lead with pliers at the body so the bend doesn't strain it).
3. **Power wires (they carry the battery and motor current): 3 pairs of the white 22 AWG two-conductor wire.**
   PWR + / PWR −, BATT + / BATT −, LOAD + / LOAD −. Solder each pair to its two pads, then the other ends into the
   holes in the table from the top. Keep + and − straight: mark the + conductor with a marker before you start.
4. Solder all 6 underneath. Leave the small edge pads (CE, TE, PROG2, SEL) unconnected. The board has no STAT pad;
   the ESP watches the input voltage instead (the 1 MΩ pair at g19–g22 from step 2).

(Pad names assumed from the Adafruit-style board: check them against the real board before wiring.)""",
     [(pad, h, net) for pad, h, net in M.CHARGER])
step('leads', 'Leads from the RJ12, USB-C and solar boards (22)', 'top', [draw_leads],
     'Top side. Each lead goes in from the top. Pin 1 is the square pad on each RJ12 board.',
     ['Let the RJ12 boards hang off the end and tape them down while you work underneath.'],
     """Solder the 18 leads from the three RJ12 boards (pin 1 = square pad), then the USB-C breakout's VBUS → e24 and
GND → d24, and the solar lead's + → h24 and − → i24. Trim underneath to ~1 mm.""",
     None)
step('wires', 'Insulated wires underneath (%d)' % len(wires_of('wire')), 'bottom', [draw_under, 'wire'],
     'Bottom view: flip the board over its long edge, row 1 still on the left, column a now at the TOP. Grey = done already.',
     ['Dashed = 30 AWG insulated wire, dots = its two ends. Colours: black GND, red battery +, orange 5V, blue signal.'],
     """Wires go in **before** the bridges and rails, while their holes are still open. For each wire: cut it a little long,
strip ~2 mm at each end, push the ends into the two holes **from underneath**, solder, trim. Where a hole already has a
lead, solder the wire end to that lead. Beep each wire out with the meter as you go.""",
     what(wires_of('wire')))
step('bridges', 'Bare bridges underneath (%d)' % len(wires_of('bridge')), 'bottom', [draw_under, 'bridge'],
     'Bottom view. Each bridge joins neighbouring holes in a straight line (h1-j1, h2-j2, h3-j3 skip an empty hole).',
     ['Use trimmed resistor legs or bare tinned wire laid flat across the pads, soldered at both ends.'],
     """A bridge is a short piece of **bare** wire laid across neighbouring pads (a trimmed resistor leg is ideal), soldered at
both ends; don't rely on a solder blob alone. Work one area at a time and check each with the meter: the two ends beep,
and neither beeps to the pad next to it.""",
     what(wires_of('bridge')))
step('rails', 'Rails (2)', 'bottom', [draw_under, 'rail'],
     'Bottom view. Two long bare wires: GND down column a (rows 12-24), battery + down column j (rows 13-24).',
     ['Solder each rail at every hole it passes, including the ones that already have wires or leads.'],
     """Last: lay a straight bare tinned wire along column **a** from row 12 to row 24 (GND) and along column **j** from row 13
to row 24 (battery +), soldering it at every hole. Then do the checks in step 11.""",
     what(wires_of('rail')))


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
    muted(o, prev)
    if bottom:
        draw_under(o, st['draw'][1])
    else:
        for f in st['draw']:
            f(o)
    name = 'build-step-%02d.svg' % (k + 1)
    finish(o, name, st['notes'])
    return name


def render_done():
    o = board('Finished: top side', 'Top view, every part and lead in place.')
    for s2 in STEPS:
        if s2['view'] == 'top':
            for f in s2['draw']:
                f(o)
    finish(o, 'build-done-top.svg')
    o = board('Finished: underside', 'Bottom view, everything in place. Grey dots = joints of the parts and leads from the top.', True)
    draw_pins_under(o)
    for k in ('wire', 'bridge', 'rail'):
        draw_under(o, k)
    lx, ly = MX - 40, HGT - 60
    for k, (t, c) in enumerate((('GND', NET_COL['GND']), ('battery +', NET_COL['VBAT']), ('5V', NET_COL['5V']),
                                ('3V3', NET_COL['3V3']), ('signal', NET_COL['sig']))):
        o.append('<rect x="%d" y="%.0f" width="18" height="6" fill="%s"/><text x="%d" y="%.0f" font-size="12">%s</text>' % (
            lx + k * 150, ly, c, lx + k * 150 + 24, ly + 7, t))
    finish(o, 'build-done-under.svg')
    return ['build-done-top.svg', 'build-done-under.svg']


def charger_picture():
    """The Comimark MCP73871 board as in the owner's photo (front, PWR at top left), with what goes where.
    Positions are scaled from the photo (about +/-0.5 mm): measure before relying on them for a footprint."""
    k, ox, oy = 14.0, 330, 90                       # px per mm, board origin (top-left corner) in the picture
    bw, bh = 30.5, 31.5

    def P(x, y):
        return ox + k * x, oy + k * y
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="640" font-family="Helvetica,Arial">',
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
    holes = [('GND', 4.2, 3.5, 'a20 (GND)', '#222'), ('PWR', 8.8, 3.5, 'g23 (PWR node)', '#d62728'),
             ('GND', 3.8, 27.9, 'a21 (GND)', '#222'), ('BATT', 8.8, 27.9, 'b24 (battery +)', '#d62728'),
             ('LOAD', 20.8, 27.9, 'j20 (battery + rail)', '#d62728'), ('GND', 25.6, 27.9, 'a22 (GND)', '#222')]
    for name, x, y, dest, c in holes:
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
    a = P(6.5, 3.5)
    call(a[0], a[1] - 26, 300, 110, ['PWR pair: 22 AWG, 2 wires', 'PWR → g23,  GND → a20', '(USB-C and solar come in here,', 'through D1 / D2 on the perfboard)'], '#b03030', 'end')
    a = P(6.3, 27.9)
    call(a[0], a[1] + 26, 300, 560, ['BATT pair: 22 AWG, 2 wires', 'BATT → b24,  GND → a21'], '#b03030', 'end')
    a = P(23.2, 27.9)
    call(a[0], a[1] + 26, 790, 560, ['LOAD pair: 22 AWG, 2 wires', 'LOAD → j20,  GND → a22'], '#b03030')
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
        ('ESP32-C6 SuperMini', 1, '1', 'ESP32-C6 SuperMini 5-pack'),
        ('Header pins', len(PARTS['ESP32-C6'].pins) + len(PARTS['Battery pins'].pins), '1 (2 × 10), 5 (2)', 'perfboard kit headers'),
        ('Resistor 1 kΩ', count['1k'], '2', 'resistor kit'),
        ('Resistor 1 MΩ', count['1M'], '2: battery and input-power dividers', 'resistor kit'),
        ('Diode 1N5819', 3, '3', '1N5819 150-pack'),
        ('Zener 6.2 V', 1, '3', 'zener kit'),
        ('Ceramic capacitor 100 nF (104)', count['100n'], '4', 'ceramic capacitor kit'),
        ('Ceramic capacitor 10 µF (106)', count['10µ'], '4', 'ceramic capacitor kit'),
        ('MCP73871 charger board, 30.5 × 31.5 mm, off the board (+ its 16 × 26 mm bulk capacitor)', 1, '6', 'Comimark MCP73871'),
        ('NTC thermistor 10 kΩ', 1, '6', 'NTC 10-pack'),
        ('White 22 AWG two-conductor wire', '3 pairs × 6-8 cm', '6 (charger power)', 'solar extension wire'),
        ('RJ12 breakout board', 3, '7 (%d leads)' % len(PARTS['Port leads'].pins), 'RJ11/RJ12 breakout 4-pack'),
        ('USB-C breakout (Cermant)', 1, '7 (2 leads)', 'USB-C breakout 10-pack'),
        ('Solar lead (optional)', 1, '7 (2 leads)', 'solar panel + extension'),
        ('30 AWG insulated wire', '%d pieces' % len(wires_of('wire')), '8', '30 AWG silicone wire'),
        ('Bare wire or trimmed resistor legs', '%d bridges + %d rails' % (len(wires_of('bridge')), len(wires_of('rail'))), '9, 10',
         'tinned wire / leg offcuts'),
        ('Perfboard 3 × 7 cm (a–j × 1–24)', 1, 'all', 'perfboard kit'),
        ('18650 cell with JST-XH plug', 1, '11', '18650 cell'),
    ]


def write_md():
    o = ['# Building the controller dev board, step by step', '',
         'For the kit\'s **3 × 7 cm perfboard (columns a–j, rows 1–24)**. Everything here (pictures, tables, counts) is generated',
         'from the layout in [ControllerV4.py](../hardware/mechanical/fusion/ControllerV4/ControllerV4.py) by',
         '[`tools/devboard_guide.py`](../tools/devboard_guide.py); [`tools/devboard_check.py`](../tools/devboard_check.py)',
         'checks that the wiring makes every connection with no shorts. Full wiring list:',
         '[ctrl-v4-wiring.md](renders/ctrl-v4-wiring.md).', '',
         '**Order:** all parts and leads first (steps 1–7, holes still open), then the insulated wires (8), then the bare',
         'bridges (9), then the rails (10). That way solder never fills a hole that something still has to go through. Each',
         'step does one kind of part, and in its picture that step is in colour while everything already done is grey.', '',
         '## Parts for one board', '', '| Part | Count | Step | From (BOM) |', '|---|---|---|---|']
    o += ['| %s | %s | %s | %s |' % r for r in bom()]
    o += ['', 'For all 3 controllers, triple every count. Links and prices: [BOM](../hardware/BOM.md).', '',
          '## Which parts have a direction?', '', '![which way round](renders/build-polarity.png)', '',
          '| Part | Direction matters? | How to tell |', '|---|---|---|',
          '| Resistors | **No** | either way round |',
          '| Ceramic capacitors | **No** | either way round; legs 3 holes apart, the middle hole stays empty |',
          '| **1N5819 diodes, 6.2 V zener** | **YES** | the silver/white **band is the cathode (K)** |',
          '| **ESP32-C6** | **YES** | chip side up, USB-C past row 1, 5V/GND/3V3 in column h |',
          '| **Battery plug** on the 2 header pins | **YES, and it can go on backwards** | red wire on **b24 (+)**, black on **a24 (−)** |',
          '| **Charger bulk capacitor** (on the charger board) | **YES** | stripe = −, long leg = + |',
          '| USB-C and solar leads, charger pads | **YES** | follow the tables |', '',
          'A reversed diode just won\'t conduct; a reversed electrolytic or battery can damage parts. Check those twice.', '',
          '## Tools and tips',
          '- Soldering iron (~330 °C), thin solder, flush cutters, tweezers, multimeter (beep / continuity mode), marker.',
          '- Place parts on the **top**, solder **underneath**, trim leads to ~1 mm.',
          '- Use just enough solder for a small cone on the pad. Too much spreads to the next pad or fills holes.',
          '- If a hole fills by accident, heat it and clear it with a desoldering pump or wick before going on.', '']
    hdr = {'esp': ('Part', 'Holes', 'Note'), 'res': ('Resistor', 'Holes', 'How'), 'diodes': ('Diode', 'Holes', 'Direction'),
           'caps': ('Capacitor', 'Holes', 'Note'), 'batt': ('Part', 'Holes', 'Note'), 'charger': ('Charger pad', 'Board hole', 'Net'),
           'wires': ('From', 'To', 'What'), 'bridges': ('From', 'To', 'What'), 'rails': ('From', 'To', 'What')}
    for k, st in enumerate(STEPS):
        o += ['## Step %d: %s' % (k + 1, st['title']), '', '![step %d](renders/build-step-%02d.png)' % (k + 1, k + 1), '', st['body'], '']
        if st['key'] == 'leads':
            leads = {lab: HN(i, m) for i, m, lab in PARTS['Port leads'].pins}
            o += ['| RJ12 pin | Port 1 | Port 2 | Port 3 |', '|---|---|---|---|']
            for pin, sig in ((1, 'VBAT'), (2, 'IN1'), (3, 'GND'), (4, 'ANG'), (5, 'EN'), (6, 'IN2')):
                o.append('| %d %s | %s | %s | %s |' % (pin, {'VBAT': 'battery +', 'ANG': 'angle'}.get(sig, sig),
                                                     leads['P1 ' + sig], leads['P2 ' + sig], leads['P3 ' + sig]))
            o += ['', '| Lead | Hole |', '|---|---|', '| USB-C VBUS (+) | e24 |', '| USB-C GND (−) | d24 |',
                  '| Solar + | h24 |', '| Solar − | i24 |', '']
        else:
            o += ['| %s |' % ' | '.join(hdr[st['key']]), '|---|---|---|'] + ['| %s | %s | %s |' % r for r in st['table']] + ['']
    o += ['## Step 11: checks and first power-up', '',
          '![finished top](renders/build-done-top.png)', '', '![finished underside](renders/build-done-under.png)', '',
          'The battery + rail (column j) gets most of its connections from the top: the three port leads (j15–j17) and the',
          'charger\'s LOAD + wire (j20); underneath, only the wire from D3 (j6 → j13) joins it. The cell never connects to the',
          'rail directly: battery + (b24) goes to the charger\'s BATT + pad and the charger feeds the rail from LOAD +.', '',
          '1. Meter, beep mode, no power: GND (a12) to battery + (j13): **no beep**. GND to 5V (h1): no beep. GND to 3V3 (h3):',
          '   no beep. GND to the battery + pin (b24): no beep.',
          '2. Plug USB into the **ESP\'s own** USB-C only (battery unplugged). Its LED should light; upload the test sketch.',
          '3. Unplug USB, then push the cell\'s plug onto a24/b24 (**red on b24**). Measure j13 to a12: about the cell voltage',
          '   (3.0–4.2 V).',
          '4. Never plug USB into the ESP and the battery at the same time unless D3 is fitted.', '']
    open(DOC, 'w').write('\n'.join(o))


def main():
    names = [render_step(k) for k in range(len(STEPS))] + render_done() + [charger_picture(), polarity()]
    for old in ('build-1-esp', 'build-2-parts', 'build-3-underside'):
        for ext in ('.svg', '.png'):
            p = os.path.join(OUT, old + ext)
            if os.path.exists(p):
                os.remove(p)
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
