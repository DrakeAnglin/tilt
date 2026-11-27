"""The tilter sensor module's wiring picture (docs/renders/tilter-wiring.png), drawn from the table below.

Boards are drawn the way you hold them while wiring: the RJ12 breakout with its jack on the left, pins 6 to 1 from
top to bottom (pin 1, the square pad, at the bottom). The wires match docs/tilter-wiring.md, step 2.

  python3 tools/tilter_wiring.py          # writes the SVG to a temp folder and prints its path
  python3 tools/tilter_wiring.py --png    # also renders docs/renders/tilter-wiring.png with Chrome
"""
import os
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.join(HERE, '../docs/renders/tilter-wiring.png')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
W, H = 2000, 1268                      # drawing units; rendered at 2840 × 1800 px

GOLD, GOLD_EDGE, EMPTY, EMPTY_EDGE = '#e0b040', '#8a6d1f', '#dddddd', '#999999'
RED, BLACK, GREEN, YELLOW, BLUE, WHITE = '#d62a2a', '#222222', '#2ea043', '#e8c020', '#1f6fb5', '#ffffff'
THICK, THIN = 7, 4                     # 22 AWG, 30 AWG
ARROW = '#e06c00'                      # the wire-direction markers

# Which edge each board's leads point to, as held: (x, edge y, points up?, words)
DIRECTIONS = [
    (211, 155, True, 'RJ12: leads leave toward the TOP edge'),
    (1000, 141, False, 'DRV8833: leads come in from the TOP edge'),
    (1000, 1127, True, 'AS5600: leads come in from the BOTTOM edge'),
]

# RJ12 breakout pins, top to bottom as held: (pin, label, y)
RJ_X = 338
RJ_PINS = [(6, 'IN2', 233), (5, 'EN', 295), (4, 'angle', 357), (3, 'GND', 419), (2, 'IN1', 481), (1, 'battery +', 543)]
RJ_Y = {p: y for p, _, y in RJ_PINS}

DRV_L, DRV_R = 820, 1180               # pin columns on the DRV8833
DRV_LEFT = [('IN4', 197, False), ('IN3', 256, False), ('GND', 315, True), ('VCC', 374, True), ('IN2', 433, True),
            ('IN1', 492, True)]
DRV_RIGHT = [('EEP', 197, True), ('OUT1', 256, True), ('OUT2', 315, True), ('OUT3', 374, False), ('OUT4', 433, False),
             ('ULT', 492, False)]
DRV_Y = {n: y for n, y, _ in DRV_LEFT + DRV_RIGHT}

AS_L, AS_R = 887, 1112                 # pin columns on the AS5600
AS_Y = {'VCC': 873, 'OUT': 923, 'GND': 974, 'DIR': 848, 'SCL': 898, 'SDA': 949, 'GPO': 1000}
MOTOR_TABS = (256, 335)

# (color, width, outlined, points): each wire from its RJ12 pad (or driver pad) to its end, square corners
WIRES = [
    (RED, THICK, False, [(RJ_X, RJ_Y[1]), (470, RJ_Y[1]), (470, DRV_Y['VCC']), (DRV_L, DRV_Y['VCC'])]),
    (BLACK, THICK, False, [(RJ_X, RJ_Y[3]), (500, RJ_Y[3]), (500, DRV_Y['GND']), (DRV_L, DRV_Y['GND'])]),
    (GREEN, THIN, False, [(RJ_X, RJ_Y[2]), (560, RJ_Y[2]), (560, DRV_Y['IN1']), (DRV_L, DRV_Y['IN1'])]),
    (YELLOW, THIN, False, [(RJ_X, RJ_Y[6]), (620, RJ_Y[6]), (620, DRV_Y['IN2']), (DRV_L, DRV_Y['IN2'])]),
    (BLUE, THIN, False, [(RJ_X, RJ_Y[5]), (590, RJ_Y[5]), (590, 620), (1268, 620), (1268, DRV_Y['EEP']),
                         (DRV_R, DRV_Y['EEP'])]),
    (BLUE, THIN, False, [(RJ_X, RJ_Y[5]), (650, RJ_Y[5]), (650, AS_Y['VCC']), (AS_L, AS_Y['VCC'])]),
    (WHITE, THIN, True, [(RJ_X, RJ_Y[4]), (680, RJ_Y[4]), (680, AS_Y['OUT']), (AS_L, AS_Y['OUT'])]),
    (BLACK, THIN, False, [(RJ_X, RJ_Y[3]), (440, RJ_Y[3]), (440, AS_Y['GND']), (AS_L, AS_Y['GND'])]),
    (RED, THICK, False, [(DRV_R, DRV_Y['OUT1']), (1422, MOTOR_TABS[0])]),
    (BLACK, THICK, False, [(DRV_R, DRV_Y['OUT2']), (1340, DRV_Y['OUT2']), (1340, MOTOR_TABS[1]), (1422, MOTOR_TABS[1])]),
]

LEGEND = [
    (RED, THICK, False, 'RJ12 pin 1 battery + -> DRV VCC (22 AWG)'),
    (BLACK, THICK, False, 'RJ12 pin 3 GND -> DRV GND (22 AWG)'),
    (GREEN, THIN, False, 'RJ12 pin 2 IN1 -> DRV IN1 (30 AWG)'),
    (YELLOW, THIN, False, 'RJ12 pin 6 IN2 -> DRV IN2 (30 AWG)'),
    (BLUE, THIN, False, 'RJ12 pin 5 EN -> DRV EEP (sleep) and AS5600 VCC (30 AWG)'),
    (WHITE, THIN, True, 'RJ12 pin 4 angle -> AS5600 OUT (30 AWG)'),
    (BLACK, THIN, False, 'RJ12 pin 3 GND -> AS5600 GND (30 AWG)'),
    (RED, THICK, False, 'DRV OUT1 / OUT2 -> N20 tabs: one red, one black (22 AWG)'),
]


def text(x, y, s, size=17, col='#222', weight='normal', anchor='start', rot=None):
    tr = ' transform="rotate(%d %d %d)"' % (rot, x, y) if rot is not None else ''
    return ('<text x="%d" y="%d" font-size="%d" fill="%s" font-weight="%s" text-anchor="%s"%s>%s</text>'
            % (x, y, size, col, weight, anchor, tr, escape(s)))


def rect(x0, y0, x1, y1, fill, stroke='none', rx=0, sw=2):
    return ('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s" stroke="%s" stroke-width="%d"/>'
            % (x0, y0, x1 - x0, y1 - y0, rx, fill, stroke, sw))


def pad(x, y, used=True, square=False):
    fill, edge = (GOLD, GOLD_EDGE) if used else (EMPTY, EMPTY_EDGE)
    if square:
        return rect(x - 10, y - 10, x + 10, y + 10, fill, '#111' if used else edge, sw=3)
    return '<circle cx="%d" cy="%d" r="10" fill="%s" stroke="%s" stroke-width="2"/>' % (x, y, fill, edge)


def line(points, col, width, outlined=False, dash=None):
    pts = ' '.join('%d,%d' % p for p in points)
    d = ' stroke-dasharray="%s"' % dash if dash else ''
    out = []
    if outlined:
        out.append('<polyline points="%s" fill="none" stroke="#777" stroke-width="%d"%s/>' % (pts, width + 3, d))
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%d"%s/>' % (pts, col, width, d))
    return ''.join(out)


def breakout():
    o = [rect(57, 155, 365, 620, '#2b6cb0', '#1a4a80', 8), text(73, 190, 'RJ12 breakout', 22, '#fff', 'bold'),
         rect(73, 212, 172, 563, '#dddddd', '#999', 4), text(128, 390, 'jack (cord plugs in here)', 17, '#222', 'bold',
                                                              'middle', -90)]
    for p, name, y in RJ_PINS:
        o.append(text(318, y + 7, '%d %s' % (p, name), 19, '#fff', 'bold', 'end'))
    o.append(text(261, 604, 'pin 1 = square pad (bottom)', 16, '#fff', anchor='middle'))
    return o


def pads_breakout():
    return [pad(RJ_X, y, square=(p == 1)) for p, _, y in RJ_PINS]


def driver():
    o = [rect(789, 141, 1211, 563, '#2d2a3a', '#111', 10), rect(950, 302, 1049, 401, '#111', '#444', 3),
         text(1000, 542, 'DRV8833', 22, '#fff', 'bold', 'middle'),
         rect(975, 167, 991, 185, GOLD), rect(1003, 167, 1019, 185, GOLD),
         text(965, 182, 'en', 16, '#fff', anchor='end'), text(1029, 182, 'sleep', 16, '#fff'),
         text(1000, 214, 'J1: leave open', 16, '#fff', anchor='middle')]
    for name, y, used in DRV_LEFT:
        o.append(text(DRV_L + 20, y + 7, name, 19, '#fff' if used else '#888', 'bold'))
    for name, y, used in DRV_RIGHT:
        o.append(text(DRV_R - 20, y + 7, name, 19, '#fff' if used else '#888', 'bold', 'end'))
    return o


def pads_driver():
    return ([pad(DRV_L, y, used) for _, y, used in DRV_LEFT] + [pad(DRV_R, y, used) for _, y, used in DRV_RIGHT])


def motor():
    return [rect(1422, 211, 1662, 380, '#c8c8c8', '#888', 14), text(1542, 303, 'N20 motor', 22, '#111', 'bold', 'middle'),
            rect(1414, MOTOR_TABS[0] - 10, 1430, MOTOR_TABS[0] + 10, GOLD, GOLD_EDGE),
            rect(1414, MOTOR_TABS[1] - 10, 1430, MOTOR_TABS[1] + 10, GOLD, GOLD_EDGE),
            text(1422, 422, 'red and black 22 AWG pair to the motor tabs,', 17),
            text(1422, 446, 'either way round', 17)]


def sensor():
    o = [rect(789, 705, 1211, 1127, '#f4f4ee', '#aaa', 14)]
    o += ['<circle cx="%d" cy="%d" r="25" fill="#fff" stroke="#aaa" stroke-width="2"/>' % c
          for c in ((834, 750), (1166, 750), (834, 1082), (1166, 1082))]
    for name, x in (('C1', 929), ('C2', 977), ('R1', 1025)):
        o += [rect(x - 8, 806, x + 8, 830, '#d8c3a0', '#b09870', sw=1), text(x, 800, name, 15, '#555', anchor='middle')]
    for name, x in (('R3', 943), ('R2', 991), ('R4', 1039)):
        o += [rect(x - 8, 1025, x + 8, 1049, '#d8c3a0', '#b09870', sw=1), text(x, 1073, name, 15, '#555', anchor='middle')]
    o += [rect(958, 885, 1040, 946, '#111'), text(999, 921, 'AS5600', 14, '#fff', anchor='middle'),
          text(1000, 1115, 'chip faces the magnet', 17, '#333', anchor='middle')]
    for name in ('VCC', 'OUT', 'GND'):
        o.append(text(AS_L + 20, AS_Y[name] + 7, name, 19, '#111', 'bold'))
    for name in ('DIR', 'SCL', 'SDA', 'GPO'):
        o.append(text(AS_R - 20, AS_Y[name] + 7, name, 19, '#111' if name in ('DIR', 'GPO') else '#999', 'bold', 'end'))
    # the two links on the back of the board, dashed
    o.append(line([(AS_R, AS_Y['DIR']), (1203, AS_Y['DIR']), (1203, 781), (853, 781), (853, AS_Y['GND']),
                   (AS_L, AS_Y['GND'])], BLACK, 3, dash='9,6'))
    o.append(line([(AS_R, AS_Y['GPO']), (1191, AS_Y['GPO']), (1191, 1050), (865, 1050), (865, AS_Y['VCC']),
                   (AS_L, AS_Y['VCC'])], BLUE, 3, dash='9,6'))
    return o


def pads_sensor():
    return [pad(AS_L, AS_Y['VCC'], square=True), pad(AS_L, AS_Y['OUT']), pad(AS_L, AS_Y['GND']),
            pad(AS_R, AS_Y['DIR'], square=True), pad(AS_R, AS_Y['SCL'], False), pad(AS_R, AS_Y['SDA'], False),
            pad(AS_R, AS_Y['GPO'])]


def arrow(x, edge, up, words):
    """A fat arrow just outside a board's edge, pointing the way the leads run, with its words beside it."""
    if edge < 600:                     # a top edge: the arrow sits above it
        y0, y1 = edge - 44, edge - 6
    else:                              # a bottom edge: below it
        y0, y1 = edge + 6, edge + 44
    tip, tail = (y0, y1) if up else (y1, y0)
    head = 12 if up else -12
    return ['<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="6"/>' % (x, tail, x, tip + head, ARROW),
            '<polygon points="%d,%d %d,%d %d,%d" fill="%s"/>' % (x, tip, x - 11, tip + head + (2 if up else -2),
                                                                 x + 11, tip + head + (2 if up else -2), ARROW),
            text(x + 20, (y0 + y1) // 2 + 7, words, 18, ARROW, 'bold')]


def legend():
    o = []
    for i, (col, width, outlined, label) in enumerate(LEGEND):
        y = 507 + i * 34
        if i == len(LEGEND) - 1:          # the motor pair: one red, one black
            o += [line([(1422, y - 4), (1470, y - 4)], RED, 4), line([(1422, y + 4), (1470, y + 4)], BLACK, 4)]
        else:
            o.append(line([(1422, y), (1470, y)], col, width, outlined))
        o.append(text(1482, y + 6, label, 17))
    o += [text(1254, 853, 'Dashed = short link wires on the BACK of the board', 18),
          text(1254, 878, '(the pins are on opposite sides):', 18),
          text(1254, 912, 'GPO to VCC', 18, BLUE, 'bold'), text(1254, 940, 'DIR to GND', 18, '#111', 'bold'),
          text(1254, 980, 'C1 / C2: the 3.3 V check (step 1)', 17)]
    return o


def svg():
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1420" height="900" viewBox="0 0 %d %d" '
         'font-family="Helvetica, Arial, sans-serif">' % (W, H), rect(0, 0, W, H, '#ffffff'),
         text(35, 52, 'Tilter sensor module: wiring', 32, '#111', 'bold'),
         text(35, 88, 'Boards drawn the way you hold them, component side up. RJ12 breakout: jack on the left, pins 6 to 1 '
                      'from the top. Thick = 22 AWG, thin = 30 AWG.', 17, '#444')]
    o += breakout() + driver() + motor() + sensor()
    o += [line(pts, col, width, outlined) for col, width, outlined, pts in WIRES]
    o += pads_breakout() + pads_driver() + pads_sensor() + legend()
    for x, edge, up, words in DIRECTIONS:
        o += arrow(x, edge, up, words)
    o.append(text(35, 1215, 'Gray pads stay empty: IN3, IN4, ULT (= FAULT), OUT3, OUT4 on the driver; SCL, SDA on the '
                            'sensor. Two wires each on RJ12 pins 3 and 5.', 17, '#333'))
    o.append('</svg>')
    return '\n'.join(o)


def main(argv):
    path = os.path.join(tempfile.mkdtemp(), 'tilter-wiring.svg')
    with open(path, 'w') as f:
        f.write(svg())
    if '--png' in argv:
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                        '--window-size=1420,900', '--screenshot=' + os.path.abspath(PNG), 'file://' + path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print('wrote', os.path.relpath(PNG))
    print('svg:', path)
    return path


if __name__ == '__main__':
    main(sys.argv)
