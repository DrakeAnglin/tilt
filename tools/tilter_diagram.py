"""Wiring diagram for the tilter's sensor module (RJ12 breakout -> DRV8833 + AS5600 -> N20), in the build's wire colours.

  python3 tools/tilter_diagram.py        # writes docs/renders/tilter-wiring.svg (and .png with headless Chrome)
"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '../docs/renders/tilter-wiring.svg')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
COL = {'red': '#d62728', 'black': '#222222', 'green': '#2ca02c', 'yellow': '#e8c31a', 'blue': '#1f77b4', 'white': '#ffffff',
       'motor': '#f2f2f2'}
W, H = 1180, 760

o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica,Arial">' % (W, H),
     '<rect width="100%" height="100%" fill="#fff"/>',
     '<text x="24" y="36" font-size="22" font-weight="bold">Tilter sensor module: wiring</text>',
     '<text x="24" y="60" font-size="13" fill="#444">Match pins by the names printed on your boards (the order along each header can differ '
     'between suppliers). Thick = 22 AWG, thin = 30 AWG.</text>']


def board(x, y, w, h, fill, title, sub=''):
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="%s" stroke="#333" stroke-width="1.5"/>' % (x, y, w, h, fill))
    o.append('<text x="%d" y="%d" font-size="15" font-weight="bold" fill="#fff">%s</text>' % (x + 12, y + 24, title))
    if sub:
        o.append('<text x="%d" y="%d" font-size="11" fill="#eee">%s</text>' % (x + 12, y + 40, sub))


def pin(x, y, name, side='r'):
    o.append('<circle cx="%d" cy="%d" r="6" fill="#e0b040" stroke="#7a5c00"/>' % (x, y))
    o.append('<text x="%d" y="%d" font-size="12" font-weight="bold" fill="#fff" text-anchor="%s">%s</text>' % (
        x - 12 if side == 'r' else x + 12, y + 4, 'end' if side == 'r' else 'start', name))
    return x, y


def wire(a, b, colour, thick=False, label='', bend=0):
    (x0, y0), (x1, y1) = a, b
    mx = (x0 + x1) / 2 + bend
    w = 5 if thick else 3
    if colour == 'white' or colour == 'motor':
        o.append('<path d="M%d %d C%d %d %d %d %d %d" fill="none" stroke="#555" stroke-width="%d"/>' % (x0, y0, mx, y0, mx, y1, x1, y1, w + 2))
    o.append('<path d="M%d %d C%d %d %d %d %d %d" fill="none" stroke="%s" stroke-width="%d"/>' % (x0, y0, mx, y0, mx, y1, x1, y1, COL[colour], w))
    if label:
        o.append('<text x="%d" y="%d" font-size="11" fill="#333" text-anchor="middle">%s</text>' % (mx, (y0 + y1) / 2 - 6, label))


# RJ12 breakout (left)
board(40, 110, 230, 320, '#2b6cb0', 'RJ12 breakout', 'jack faces out of the module end wall')
o.append('<rect x="52" y="150" width="70" height="250" rx="4" fill="#ddd" stroke="#666"/>')
o.append('<text x="87" y="280" font-size="12" text-anchor="middle" font-weight="bold" transform="rotate(-90 87 280)">RJ12 jack (cord)</text>')
rj = {}
for k, (n, name) in enumerate(((1, 'battery +'), (2, 'IN1'), (3, 'GND'), (4, 'angle'), (5, 'EN'), (6, 'IN2'))):
    rj[n] = pin(258, 160 + k * 46, '%d %s' % (n, name))
o.append('<rect x="252" y="154" width="12" height="12" fill="none" stroke="#000" stroke-width="1.5"/>')
o.append('<text x="150" y="420" font-size="11" fill="#fff">pin 1 = square pad</text>')

# DRV8833 (middle top)
board(560, 90, 260, 300, '#7b2d8e', 'DRV8833 motor driver', 'cut the J1 en/sleep jumper first')
drv = {'VCC': pin(572, 140, 'VCC', 'l'), 'GND': pin(572, 186, 'GND', 'l'), 'IN1': pin(572, 232, 'IN1', 'l'),
       'IN2': pin(572, 278, 'IN2', 'l'), 'ULT': pin(572, 324, 'ULT', 'l'),
       'OUT1': pin(808, 186, 'OUT1'), 'OUT2': pin(808, 232, 'OUT2')}
o.append('<text x="690" y="370" font-size="11" fill="#eee" text-anchor="middle">IN3, IN4, OUT3, OUT4, EEP: leave empty</text>')
# 10 uF at the driver
o.append('<rect x="586" y="152" width="18" height="22" rx="3" fill="#7fb2e5" stroke="#2a5a8a"/>')
o.append('<line x1="595" y1="140" x2="595" y2="152" stroke="#888" stroke-width="2"/><line x1="595" y1="174" x2="595" y2="186" stroke="#888" stroke-width="2"/>')
o.append('<line x1="572" y1="140" x2="595" y2="140" stroke="#888" stroke-width="2"/><line x1="572" y1="186" x2="595" y2="186" stroke="#888" stroke-width="2"/>')
o.append('<text x="612" y="168" font-size="11" fill="#fff" font-weight="bold">10 µF: legs on VCC and GND</text>')

# AS5600 (middle bottom)
board(560, 450, 260, 250, '#1d6b3a', 'AS5600 angle sensor', 'chip faces the magnet')
asn = {'VCC': pin(572, 500, 'VCC', 'l'), 'OUT': pin(572, 546, 'OUT', 'l'), 'GND': pin(572, 592, 'GND', 'l'),
       'DIR': pin(808, 546, 'DIR'), 'GPO': pin(808, 500, 'GPO'), 'G2': pin(808, 592, 'GND')}
o.append('<text x="690" y="680" font-size="11" fill="#eee" text-anchor="middle">SCL, SDA: leave empty</text>')
o.append('<polyline points="808,500 790,500 790,522 590,522 590,500 572,500" fill="none" stroke="%s" stroke-width="3"/>' % COL['blue'])
o.append('<text x="690" y="517" font-size="11" fill="#fff" text-anchor="middle">link GPO to VCC</text>')
o.append('<path d="M808 546 C840 546 840 592 808 592" fill="none" stroke="%s" stroke-width="3"/>' % COL['black'])
o.append('<text x="860" y="565" font-size="11" fill="#333">link DIR to GND (never leave DIR open:</text>')
o.append('<text x="860" y="579" font-size="11" fill="#333">it sets the counting direction)</text>')

# N20 motor (right)
o.append('<rect x="960" y="150" width="150" height="110" rx="14" fill="#bbb" stroke="#555"/>')
o.append('<text x="1035" y="210" font-size="15" font-weight="bold" text-anchor="middle">N20 motor</text>')
m1, m2 = (960, 186), (960, 232)
for p in (m1, m2):
    o.append('<rect x="%d" y="%d" width="10" height="14" fill="#e0b040" stroke="#7a5c00"/>' % (p[0] - 6, p[1] - 7))
wire(drv['OUT1'], m1, 'motor', True)
wire(drv['OUT2'], m2, 'motor', True)
o.append('<text x="980" y="290" font-size="11" fill="#333">white 22 AWG pair (soldered to the</text>')
o.append('<text x="980" y="304" font-size="11" fill="#333">tabs at final assembly). Swap them if</text>')
o.append('<text x="980" y="318" font-size="11" fill="#333">"forward" turns the wrong way.</text>')

# RJ12 -> boards
wire(rj[1], drv['VCC'], 'red', True, bend=-40)
wire(rj[3], drv['GND'], 'black', True, bend=-10)
wire(rj[2], drv['IN1'], 'green', bend=20)
wire(rj[6], drv['IN2'], 'yellow', bend=40)
wire(rj[5], drv['ULT'], 'blue', bend=60)
wire(rj[5], asn['VCC'], 'blue', bend=10)
wire(rj[4], asn['OUT'], 'white', bend=-20)
wire(rj[3], asn['GND'], 'black', bend=-60)
legend = [('red', True, 'pin 1 battery + -> DRV VCC (22 AWG)'), ('black', True, 'pin 3 GND -> DRV GND (22 AWG)'),
          ('green', False, 'pin 2 IN1 -> DRV IN1'), ('yellow', False, 'pin 6 IN2 -> DRV IN2'),
          ('blue', False, 'pin 5 EN -> DRV ULT and -> AS5600 VCC'), ('white', False, 'pin 4 angle -> AS5600 OUT'),
          ('black', False, 'pin 3 GND -> AS5600 GND (30 AWG)'), ('motor', True, 'DRV OUT1 / OUT2 -> N20 tabs')]
for k, (c, thick, t) in enumerate(legend):
    y = 470 + k * 26
    if c in ('white', 'motor'):
        o.append('<line x1="40" y1="%d" x2="80" y2="%d" stroke="#555" stroke-width="%d"/>' % (y, y, 7 if thick else 5))
    o.append('<line x1="40" y1="%d" x2="80" y2="%d" stroke="%s" stroke-width="%d"/>' % (y, y, COL[c], 5 if thick else 3))
    o.append('<text x="90" y="%d" font-size="12" fill="#222">%s</text>' % (y + 4, t))

o.append('<text x="24" y="735" font-size="13" fill="#222">Two separate GND wires from RJ12 pin 3 (one to the driver, one to the sensor) and two blue wires from pin 5 (EN '
         'powers the sensor and wakes the driver).</text>')
o.append('</svg>')
open(OUT, 'w').write('\n'.join(o))
png = OUT[:-4] + '.png'
subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                '--window-size=%d,%d' % (W, H), '--screenshot=' + os.path.abspath(png), 'file://' + os.path.abspath(OUT)],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print('wrote', OUT, png)
