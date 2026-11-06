"""Wiring diagram for the tilter's sensor module (RJ12 breakout -> DRV8833 + AS5600 -> N20), in the build's wire colors.
The two boards are drawn as the owner's actually look (pin order as printed on them, 2026-11-01 photos).

  python3 tools/tilter_diagram.py        # writes docs/renders/tilter-wiring.svg and .png (headless Chrome)
"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '../docs/renders/tilter-wiring.svg')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
COL = {'red': '#d62728', 'black': '#222222', 'green': '#2ca02c', 'yellow': '#e8c31a', 'blue': '#1f77b4', 'white': '#ffffff',
       'motor': '#f2f2f2'}
W, H = 1420, 900
o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica,Arial">' % (W, H),
     '<rect width="100%" height="100%" fill="#fff"/>',
     '<text x="24" y="36" font-size="22" font-weight="bold">Tilter sensor module: wiring</text>',
     '<text x="24" y="60" font-size="13" fill="#444">Boards drawn as they look from the component side, pins in their printed order. '
     'Thick = 22 AWG, thin = 30 AWG.</text>']


def pad(x, y, name, side, square=False, dim=False, light=False):
    """A header pad with its printed name next to it, inside the board ('l': name to the right of the pad)."""
    fill = '#d9d9d9' if dim else '#e0b040'
    if square:
        o.append('<rect x="%d" y="%d" width="14" height="14" fill="%s" stroke="#555"/>' % (x - 7, y - 7, fill))
    else:
        o.append('<circle cx="%d" cy="%d" r="7" fill="%s" stroke="#555"/>' % (x, y, fill))
    color = ('#888' if dim else '#fff') if light else ('#999' if dim else '#111')
    anchor = 'start' if side == 'l' else 'end'
    o.append('<text x="%d" y="%d" font-size="14" font-weight="bold" fill="%s" text-anchor="%s">%s</text>' % (
        x + 14 if side == 'l' else x - 14, y + 5, color, anchor, name))
    return x, y


def path(points, color, thick=False, dash=False):
    w = 5 if thick else 3
    d = 'M' + ' L'.join('%d %d' % p for p in points)
    if color in ('white', 'motor'):
        o.append('<path d="%s" fill="none" stroke="#555" stroke-width="%d" stroke-linejoin="round"/>' % (d, w + 2))
    o.append('<path d="%s" fill="none" stroke="%s" stroke-width="%d" stroke-linejoin="round"%s/>' % (
        d, COL[color], w, ' stroke-dasharray="7,4"' if dash else ''))


# ---------------------------------------------------------------- RJ12 breakout (left)
o.append('<rect x="40" y="110" width="220" height="330" rx="8" fill="#2b6cb0" stroke="#333" stroke-width="1.5"/>')
o.append('<text x="52" y="134" font-size="15" font-weight="bold" fill="#fff">RJ12 breakout</text>')
o.append('<rect x="52" y="150" width="70" height="250" rx="4" fill="#ddd" stroke="#666"/>')
o.append('<text x="87" y="280" font-size="12" text-anchor="middle" font-weight="bold" transform="rotate(-90 87 280)">jack (cord plugs in here)</text>')
rj = {}
for k, (n, name) in enumerate(((1, 'battery +'), (2, 'IN1'), (3, 'GND'), (4, 'angle'), (5, 'EN'), (6, 'IN2'))):
    x, y = 240, 165 + k * 44
    if n == 1:
        o.append('<rect x="%d" y="%d" width="14" height="14" fill="#e0b040" stroke="#000" stroke-width="1.5"/>' % (x - 7, y - 7))
    else:
        o.append('<circle cx="%d" cy="%d" r="7" fill="#e0b040" stroke="#555"/>' % (x, y))
    o.append('<text x="%d" y="%d" font-size="13" font-weight="bold" fill="#fff" text-anchor="end">%d %s</text>' % (x - 14, y + 5, n, name))
    rj[n] = (x, y)
o.append('<text x="140" y="428" font-size="11" fill="#fff">pin 1 = square pad</text>')

# ---------------------------------------------------------------- DRV8833 (as printed: IN4 IN3 GND VCC IN2 IN1 | EEP OUT1..4 ULT)
X0, Y0 = 560, 100
o.append('<rect x="%d" y="%d" width="300" height="300" rx="10" fill="#2e2a3a" stroke="#222" stroke-width="2"/>' % (X0, Y0))
o.append('<text x="%d" y="%d" font-size="15" font-weight="bold" fill="#fff" text-anchor="middle">DRV8833</text>' % (X0 + 150, Y0 + 285))
o.append('<rect x="%d" y="%d" width="70" height="70" rx="4" fill="#111" stroke="#555"/>' % (X0 + 115, Y0 + 115))
o.append('<rect x="%d" y="%d" width="12" height="14" fill="#c8a040"/><rect x="%d" y="%d" width="12" height="14" fill="#c8a040"/>' % (
    X0 + 132, Y0 + 18, X0 + 152, Y0 + 18))
o.append('<text x="%d" y="%d" font-size="11" fill="#fff" text-anchor="end">en</text>' % (X0 + 126, Y0 + 30))
o.append('<text x="%d" y="%d" font-size="11" fill="#fff">sleep</text>' % (X0 + 170, Y0 + 30))
o.append('<text x="%d" y="%d" font-size="11" fill="#fff" text-anchor="middle">J1: leave open</text>' % (X0 + 150, Y0 + 52))
drv = {}
for k, name in enumerate(('IN4', 'IN3', 'GND', 'VCC', 'IN2', 'IN1')):
    drv[name] = pad(X0 + 22, Y0 + 40 + k * 42, name, 'l', dim=name in ('IN4', 'IN3'), light=True)
for k, name in enumerate(('EEP', 'OUT1', 'OUT2', 'OUT3', 'OUT4', 'ULT')):
    drv[name] = pad(X0 + 278, Y0 + 40 + k * 42, name, 'r', dim=name in ('ULT', 'OUT3', 'OUT4'), light=True)
# 10 uF straight across GND and VCC, just outside the board edge
gx, gy = drv['GND']
vx, vy = drv['VCC']
o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#888" stroke-width="2"/>' % (gx, gy, gx - 34, gy))
o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#888" stroke-width="2"/>' % (vx, vy, vx - 34, vy))
o.append('<rect x="%d" y="%d" width="16" height="%d" rx="3" fill="#7fb2e5" stroke="#2a5a8a"/>' % (gx - 42, gy - 4, vy - gy + 8))
o.append('<text x="%d" y="%d" font-size="11" font-weight="bold" text-anchor="end">10 µF</text>' % (gx - 46, (gy + vy) / 2 + 4))

# ---------------------------------------------------------------- AS5600 (as printed: VCC OUT GND | DIR SCL SDA GPO)
A0, B0 = 560, 500
o.append('<rect x="%d" y="%d" width="300" height="300" rx="16" fill="#f7f7f2" stroke="#999" stroke-width="2"/>' % (A0, B0))
for cx, cy in ((A0 + 32, B0 + 32), (A0 + 268, B0 + 32), (A0 + 32, B0 + 268), (A0 + 268, B0 + 268)):
    o.append('<circle cx="%d" cy="%d" r="18" fill="#fff" stroke="#bbb"/>' % (cx, cy))
o.append('<rect x="%d" y="%d" width="60" height="44" rx="3" fill="#222"/>' % (A0 + 120, B0 + 128))
o.append('<text x="%d" y="%d" font-size="10" fill="#ddd" text-anchor="middle">AS5600</text>' % (A0 + 150, B0 + 154))
for k, name in enumerate(('C1', 'C2', 'R1')):
    o.append('<text x="%d" y="%d" font-size="11" fill="#555" text-anchor="middle">%s</text>' % (A0 + 100 + k * 34, B0 + 68, name))
    o.append('<rect x="%d" y="%d" width="12" height="18" fill="#c8b48a" stroke="#999"/>' % (A0 + 94 + k * 34, B0 + 72))
for k, name in enumerate(('R3', 'R2', 'R4')):
    o.append('<rect x="%d" y="%d" width="12" height="18" fill="#c8b48a" stroke="#999"/>' % (A0 + 104 + k * 34, B0 + 228))
    o.append('<text x="%d" y="%d" font-size="11" fill="#555" text-anchor="middle">%s</text>' % (A0 + 110 + k * 34, B0 + 262, name))
asn = {}
for k, name in enumerate(('VCC', 'OUT', 'GND')):
    asn[name] = pad(A0 + 70, B0 + 120 + k * 36, name, 'l', square=(k == 0))
for k, name in enumerate(('DIR', 'SCL', 'SDA', 'GPO')):
    asn[name] = pad(A0 + 230, B0 + 102 + k * 36, name, 'r', square=(k == 0), dim=name in ('SCL', 'SDA'))
o.append('<text x="%d" y="%d" font-size="12" fill="#333" text-anchor="middle">chip faces the magnet</text>' % (A0 + 150, B0 + 292))
# the two links, as short wires on the BACK of the board (dashed)
path([asn['GPO'], (A0 + 286, asn['GPO'][1]), (A0 + 286, B0 + 246), (A0 + 54, B0 + 246), (A0 + 54, asn['VCC'][1]), asn['VCC']], 'blue', dash=True)
path([asn['DIR'], (A0 + 294, asn['DIR'][1]), (A0 + 294, B0 + 54), (A0 + 46, B0 + 54), (A0 + 46, asn['GND'][1]), asn['GND']], 'black', dash=True)
o.append('<text x="%d" y="%d" font-size="13" fill="#333">Dashed = short link wires on the BACK of the board</text>' % (A0 + 330, B0 + 110))
o.append('<text x="%d" y="%d" font-size="13" fill="#333">(the pins are on opposite sides):</text>' % (A0 + 330, B0 + 128))
o.append('<text x="%d" y="%d" font-size="13" fill="#1f77b4" font-weight="bold">GPO to VCC</text>' % (A0 + 330, B0 + 152))
o.append('<text x="%d" y="%d" font-size="13" fill="#222" font-weight="bold">DIR to GND</text>' % (A0 + 330, B0 + 172))
o.append('<text x="%d" y="%d" font-size="12" fill="#333">C1 / C2: the 3.3 V check (step 1)</text>' % (A0 + 330, B0 + 200))

# ---------------------------------------------------------------- N20 motor
o.append('<rect x="1010" y="150" width="170" height="120" rx="14" fill="#bbb" stroke="#555"/>')
o.append('<text x="1095" y="215" font-size="15" font-weight="bold" text-anchor="middle">N20 motor</text>')
t1, t2 = (1010, 182), (1010, 238)
for p in (t1, t2):
    o.append('<rect x="%d" y="%d" width="10" height="14" fill="#e0b040" stroke="#7a5c00"/>' % (p[0] - 6, p[1] - 7))
path([drv['OUT1'], (930, drv['OUT1'][1]), (930, t1[1]), t1], 'motor', True)
path([drv['OUT2'], (950, drv['OUT2'][1]), (950, t2[1]), t2], 'motor', True)
o.append('<text x="1010" y="300" font-size="12" fill="#333">white 22 AWG pair to the motor tabs</text>')
o.append('<text x="1010" y="316" font-size="12" fill="#333">(swap them if it turns the wrong way)</text>')

# ---------------------------------------------------------------- the cord's six lines
path([rj[1], (330, rj[1][1]), (330, drv['VCC'][1]), drv['VCC']], 'red', True)
path([rj[3], (350, rj[3][1]), (350, drv['GND'][1]), drv['GND']], 'black', True)
path([rj[2], (370, rj[2][1]), (370, drv['IN1'][1]), drv['IN1']], 'green')
path([rj[6], (390, rj[6][1]), (390, drv['IN2'][1]), drv['IN2']], 'yellow')
path([rj[5], (420, rj[5][1]), (420, 440), (900, 440), (900, drv['EEP'][1]), drv['EEP']], 'blue')   # around the driver to EEP (= SLEEP)
path([rj[5], (440, rj[5][1]), (440, asn['VCC'][1]), asn['VCC']], 'blue')
path([rj[4], (460, rj[4][1]), (460, asn['OUT'][1]), asn['OUT']], 'white')
path([rj[3], (310, rj[3][1]), (310, asn['GND'][1]), asn['GND']], 'black')

# ---------------------------------------------------------------- legend
legend = [('red', True, 'RJ12 pin 1 battery + -> DRV VCC'), ('black', True, 'RJ12 pin 3 GND -> DRV GND'),
          ('green', False, 'RJ12 pin 2 IN1 -> DRV IN1'), ('yellow', False, 'RJ12 pin 6 IN2 -> DRV IN2'),
          ('blue', False, 'RJ12 pin 5 EN -> DRV EEP (sleep) and AS5600 VCC'), ('white', False, 'RJ12 pin 4 angle -> AS5600 OUT'),
          ('black', False, 'RJ12 pin 3 GND -> AS5600 GND'), ('motor', True, 'DRV OUT1 / OUT2 -> N20 tabs')]
for k, (c, thick, t) in enumerate(legend):
    y, lx = 360 + k * 24, 1010
    if c in ('white', 'motor'):
        o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#555" stroke-width="%d"/>' % (lx, y, lx + 34, y, 7 if thick else 5))
    o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="%d"/>' % (lx, y, lx + 34, y, COL[c], 5 if thick else 3))
    o.append('<text x="%d" y="%d" font-size="12" fill="#222">%s (%s)</text>' % (lx + 42, y + 4, t, '22 AWG' if thick else '30 AWG'))
o.append('<text x="24" y="860" font-size="13" fill="#222">Gray pads stay empty: IN3, IN4, ULT (= FAULT), OUT3, OUT4 on the driver; SCL, SDA on the sensor. '
         'Two wires each on RJ12 pins 3 and 5.</text>')
o.append('</svg>')
open(OUT, 'w').write('\n'.join(o))
png = OUT[:-4] + '.png'
subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                '--window-size=%d,%d' % (W, H), '--screenshot=' + os.path.abspath(png), 'file://' + os.path.abspath(OUT)],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print('wrote', OUT, png)
