"""Pictures for the dev-board build guide (docs/dev-board-build.md), drawn from ControllerV4's layout and wiring list
so they always match it.

  python3 tools/devboard_guide.py      # writes docs/renders/build-*.svg
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('cv4', os.path.join(HERE, '../hardware/mechanical/fusion/ControllerV4/ControllerV4.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
H, COLS = M.H, M.COLS
OUT = os.path.join(HERE, '../docs/renders')

S = 30.0                     # px per hole pitch
MX, MY = 70, 90              # margins
W = int(MX * 2 + S * (M.NI - 1) + 230)
HGT = int(MY + S * (M.NM - 1) + 140)

NET_COL = {'GND': '#222222', 'VBAT': '#d62728', '5V': '#ff7f0e', '3V3': '#9467bd', 'sig': '#1f77b4'}


def pos(hole, bottom=False):
    i, m = H(hole)
    x = MX + S * i
    y = MY + S * (m if bottom else (M.NM - 1 - m))          # top view: column a at the bottom; bottom view: a at the top
    return x, y


def board(title, sub, bottom=False):
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica,Arial">' % (W, HGT),
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         '<text x="%d" y="30" font-size="20" font-weight="bold">%s</text>' % (MX - 40, title),
         '<text x="%d" y="54" font-size="13" fill="#444">%s</text>' % (MX - 40, sub),
         '<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="6" fill="%s" stroke="#3a7a2a" stroke-width="2"/>' % (
             MX - S * 0.7, MY - S * 0.7, S * (M.NI - 1) + S * 1.4, S * (M.NM - 1) + S * 1.4,
             '#f3efe2' if bottom else '#e9f4e1')]
    for i in range(M.NI):
        x = MX + S * i
        o.append('<text x="%.0f" y="%.0f" font-size="11" fill="#666" text-anchor="middle">%d</text>' % (x, MY - S * 0.9, i + 1))
    for m in range(M.NM):
        y = MY + S * (m if bottom else (M.NM - 1 - m))
        o.append('<text x="%.0f" y="%.0f" font-size="13" font-weight="bold" fill="#666" text-anchor="middle">%s</text>' % (
            MX - S * 1.15, y + 4, COLS[m]))
    for i in range(M.NI):
        for m in range(M.NM):
            x, y = pos('%s%d' % (COLS[m], i + 1), bottom)
            o.append('<circle cx="%.0f" cy="%.0f" r="4" fill="#fff" stroke="#999"/>' % (x, y))
    return o


def finish(o, name, notes=()):
    y = MY + S * (M.NM - 1) + S * 1.6
    for n in notes:
        o.append('<text x="%d" y="%.0f" font-size="13" fill="#222">%s</text>' % (MX - 40, y, n))
        y += 20
    o.append('</svg>')
    open(os.path.join(OUT, name), 'w').write('\n'.join(o))


def dot(o, hole, color, bottom=False, r=6):
    x, y = pos(hole, bottom)
    o.append('<circle cx="%.0f" cy="%.0f" r="%d" fill="%s"/>' % (x, y, r, color))


def label(o, hole, text, dx=0, dy=-12, color='#000', size=11, bottom=False, anchor='middle'):
    x, y = pos(hole, bottom)
    o.append('<text x="%.0f" y="%.0f" font-size="%d" fill="%s" text-anchor="%s" font-weight="bold">%s</text>' % (
        x + dx, y + dy, size, color, anchor, text))


def resistor(o, a, b, text):
    (x0, y0), (x1, y1) = pos(a), pos(b)
    o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="#888" stroke-width="2"/>' % (x0, y0, x1, y1))
    o.append('<circle cx="%.0f" cy="%.0f" r="9" fill="#e8c88a" stroke="#8a6a2a" stroke-width="1.5"/>' % (x0, y0))
    o.append('<text x="%.0f" y="%.0f" font-size="9" text-anchor="middle" font-weight="bold">%s</text>' % (x0, y0 + 3, text))


def ceramic(o, a, b, text):
    (x0, y0), (x1, y1) = pos(a), pos(b)
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = (abs(x1 - x0) + 16, 12) if y0 == y1 else (12, abs(y1 - y0) + 16)
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="3" fill="#7fb2e5" stroke="#2a5a8a"/>' % (
        xm - w / 2, ym - h / 2, w, h))
    o.append('<text x="%.0f" y="%.0f" font-size="9" text-anchor="middle" fill="#0b2e55" font-weight="bold">%s</text>' % (
        xm + (0 if y0 == y1 else 16), ym + (-9 if y0 == y1 else 3), text))


def diode(o, body, lead, text, band_on_body):
    """Standing diode: body over 'body', lead in 'lead'. The band (cathode) is drawn on the cathode side."""
    (x0, y0), (x1, y1) = pos(body), pos(lead)
    o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="#888" stroke-width="2"/>' % (x0, y0, x1, y1))
    o.append('<circle cx="%.0f" cy="%.0f" r="10" fill="#333"/>' % (x0, y0))
    bx, by = (x0, y0) if band_on_body else (x1, y1)
    o.append('<circle cx="%.0f" cy="%.0f" r="10" fill="none" stroke="#ddd" stroke-width="3"/>' % (bx, by) if band_on_body else
             '<rect x="%.0f" y="%.0f" width="8" height="16" fill="#ddd" stroke="#333"/>' % (bx - 4, by - 8))
    o.append('<text x="%.0f" y="%.0f" font-size="10" text-anchor="middle" font-weight="bold" fill="#000">%s</text>' % (
        (x0 + x1) / 2, min(y0, y1) - 14, text))


def guide_top():
    """Step pictures, top view."""
    o = board('Step 1: orientation and the ESP32-C6',
              'Top (component) side. Row 1 toward the phone jacks, column a toward the battery. ESP chip side UP, USB-C hanging past row 1.')
    x0, y0 = pos('b1')
    x1, y1 = pos('h10')
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="5" fill="#1b1b1b" opacity="0.85"/>' % (
        x0 - 22, y1 - 14, (x1 - x0) * 0 + S * 9 + 44, (y0 - y1) + 28))
    o.append('<rect x="%.0f" y="%.0f" width="48" height="74" rx="4" fill="#bbb" stroke="#666"/>' % (x0 - 70, (y0 + y1) / 2 - 37))
    o.append('<text x="%.0f" y="%.0f" font-size="11" text-anchor="middle" font-weight="bold">USB-C</text>' % (x0 - 46, (y0 + y1) / 2 + 4))
    lab_b = ['TX', 'RX', '0', '1', '2', '3', '4', '5', '6', '7']
    lab_h = ['5V', 'GND', '3V3', '20', '19', '18', '15', '14', '9', '8']
    for k in range(10):
        dot(o, 'b%d' % (k + 1), '#e0b040')
        dot(o, 'h%d' % (k + 1), '#e0b040')
        label(o, 'b%d' % (k + 1), lab_b[k], dy=22, color='#fff', size=10)
        label(o, 'h%d' % (k + 1), lab_h[k], dy=-12, color='#fff', size=10)
    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    o.append('<text x="%.0f" y="%.0f" font-size="16" fill="#fff" text-anchor="middle" font-weight="bold">ESP32-C6 (chip up)</text>' % (xc, yc + 5))
    cx0, cy0 = pos('c15')
    cx1, cy1 = pos('h22')
    o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="4" fill="#3b3b3b" opacity="0.8"/>' % (
        cx0 - 14, cy1 - 14, cx1 - cx0 + 28, cy0 - cy1 + 28))
    o.append('<text x="%.0f" y="%.0f" font-size="14" fill="#fff" text-anchor="middle" font-weight="bold">charger (foam tape)</text>' % (
        (cx0 + cx1) / 2, (cy0 + cy1) / 2 + 5))
    o.append('<text x="%d" y="%.0f" font-size="14" fill="#c00" font-weight="bold">&#8592; toward the phone jacks</text>' % (MX - 40, HGT - 70))
    o.append('<text x="%d" y="%.0f" font-size="14" fill="#c00" font-weight="bold" text-anchor="end">toward the USB-C end &#8594;</text>' % (W - 30, HGT - 70))
    finish(o, 'build-1-esp.svg', ['Column a (bottom edge here) faces the battery. 5V / GND / 3V3 land in column h, TX / RX in column b.'])

    o = board('Step 2: parts on top (direction matters for the dark ones)',
              'Top side. Tan = resistor, blue = ceramic capacitor (any way round). Black = diode: the band goes where shown. Electrolytic: stripe = minus.')
    for name, a, b, txt in (('R stat', 'j4', 'j5', '10k'), ('R div top', 'j8', 'j9', '1M'), ('R div bot', 'j10', 'j11', '1M'),
                            ('R ADC1', 'b12', 'b13', '1k'), ('R ADC2', 'd12', 'd13', '1k'), ('R ADC3', 'f12', 'f13', '1k')):
        resistor(o, a, b, txt)
    for a, b, txt in (('j1', 'j3', '10µ'), ('i11', 'i13', '100n'), ('a14', 'c14', '100n'), ('d14', 'f14', '100n'), ('g12', 'g14', '100n')):
        ceramic(o, a, b, txt)
    diode(o, 'j6', 'j7', 'D3 band→j6', True)
    diode(o, 'e23', 'd23', '', False)
    diode(o, 'h23', 'g23', '', False)
    diode(o, 'f24', 'f23', '', False)
    for h, t in (('e23', 'D1: band at d23'), ('h23', 'D2: band at g23'), ('f23', 'Zener: band at f23')):
        x, y = pos(h)
        o.append('<text x="%.0f" y="%.0f" font-size="11" font-weight="bold" text-anchor="end">%s</text>' % (x - 46, y + 4, t))
    for h, t, c in (('b24', 'B− (black)', '#222'), ('c24', 'B+ (red)', '#d62728'), ('d24', 'USB −', '#222'), ('e24', 'USB +', '#d62728'),
                    ('h24', 'Solar +', '#d62728'), ('i24', 'Solar −', '#222')):
        dot(o, h, c)
        label(o, h, t, dx=22, dy=4, color=c, size=11, anchor='start')
    finish(o, 'build-2-parts.svg', ['Blue ceramic capacitors: legs 3 holes apart (5 mm), the middle hole stays EMPTY. Don\'t bend the legs to fit 2 holes.',
                                     'Diodes stand up: body over the first hole, lead bent back into the second. The silver/white band is the cathode (K).',
                                     'Battery pins: 2 bare header pins at b24 (−) and c24 (+). The plug is NOT keyed on bare pins: red wire to c24.'])


def guide_bottom():
    o = board('Step 3: wiring underneath (board flipped over)',
              'Bottom view: flip the board over its long edge, row 1 still on the left. Column a is now at the TOP. Bridges = short bare wire between neighbours.',
              bottom=True)
    for f, t, note in M.WIRES:
        n = note.lower()
        if n.startswith('gnd rail'):
            col = NET_COL['GND']
        elif n.startswith('vbat rail'):
            col = NET_COL['VBAT']
        elif 'gnd' in n or 'zener anode' in n or ' - ->' in n:
            col = NET_COL['GND']
        elif 'vbat' in n or 'c bulk +' in n:
            col = NET_COL['VBAT']
        elif '5v' in n:
            col = NET_COL['5V']
        elif '3v3' in n:
            col = NET_COL['3V3']
        else:
            col = NET_COL['sig']
        (x0, y0), (x1, y1) = pos(f, True), pos(t, True)
        wdt = 5 if 'rail' in n and n.endswith(('rows 12-24', 'rows 11-24')) else 3
        if n.startswith('bridge') or 'rail' in n.split(':')[0]:
            o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="%d" stroke-linecap="round"/>' % (
                x0, y0, x1, y1, col, wdt))
        else:                                                    # insulated wire: drawn as a curve
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2 - 14
            o.append('<path d="M%.0f %.0f Q%.0f %.0f %.0f %.0f" fill="none" stroke="%s" stroke-width="2.5" stroke-dasharray="7,3"/>' % (
                x0, y0, mx, my, x1, y1, col))
    lx = MX - 40
    ly = HGT - 64
    for k, (t, c) in enumerate((('GND', NET_COL['GND']), ('VBAT (battery +)', NET_COL['VBAT']), ('5V', NET_COL['5V']),
                                ('3V3', NET_COL['3V3']), ('signal', NET_COL['sig']))):
        o.append('<rect x="%d" y="%.0f" width="18" height="6" fill="%s"/><text x="%d" y="%.0f" font-size="12">%s</text>' % (
            lx + k * 150, ly, c, lx + k * 150 + 24, ly + 7, t))
    finish(o, 'build-3-underside.svg', ['', 'Solid = bare bridge or rail. Dashed = insulated 30 AWG wire. Charger pad wires: see the table in the guide.'])


def polarity():
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="260" font-family="Helvetica,Arial">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         '<text x="20" y="30" font-size="20" font-weight="bold">Which way round?</text>']
    # diode
    o += ['<line x1="40" y1="110" x2="200" y2="110" stroke="#999" stroke-width="3"/>',
          '<rect x="90" y="96" width="60" height="28" rx="6" fill="#222"/>', '<rect x="136" y="96" width="9" height="28" fill="#ddd"/>',
          '<text x="120" y="80" font-size="14" text-anchor="middle" font-weight="bold">1N5819 / zener</text>',
          '<text x="60" y="150" font-size="13">anode (A)</text>', '<text x="150" y="150" font-size="13" font-weight="bold">band = cathode (K)</text>']
    # electrolytic
    o += ['<rect x="340" y="70" width="60" height="90" rx="10" fill="#1d3557"/>', '<rect x="340" y="70" width="14" height="90" fill="#ddd"/>',
          '<text x="347" y="120" font-size="16" font-weight="bold" text-anchor="middle">−</text>',
          '<line x1="354" y1="160" x2="354" y2="200" stroke="#999" stroke-width="3"/>', '<line x1="388" y1="160" x2="388" y2="215" stroke="#999" stroke-width="3"/>',
          '<text x="370" y="60" font-size="14" text-anchor="middle" font-weight="bold">bulk electrolytic</text>',
          '<text x="300" y="235" font-size="13">stripe / short leg = −</text>', '<text x="410" y="215" font-size="13">long leg = +</text>']
    # ceramic & resistor
    o += ['<rect x="560" y="90" width="40" height="30" rx="5" fill="#7fb2e5"/>', '<text x="580" y="80" font-size="14" text-anchor="middle" font-weight="bold">ceramic</text>',
          '<text x="580" y="145" font-size="13" text-anchor="middle">any way round</text>',
          '<text x="580" y="165" font-size="13" text-anchor="middle">legs 3 holes apart</text>',
          '<rect x="700" y="96" width="70" height="26" rx="10" fill="#e8c88a"/>', '<text x="735" y="80" font-size="14" text-anchor="middle" font-weight="bold">resistor</text>',
          '<text x="735" y="145" font-size="13" text-anchor="middle">any way round</text>']
    o.append('</svg>')
    open(os.path.join(OUT, 'build-polarity.svg'), 'w').write('\n'.join(o))


if __name__ == '__main__':
    guide_top()
    guide_bottom()
    polarity()
    print('wrote docs/renders/build-1-esp.svg, build-2-parts.svg, build-3-underside.svg, build-polarity.svg')
