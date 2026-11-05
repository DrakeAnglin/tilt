"""Controller PCB v3, concept placement: one board carrying everything (cell holder, charger, USB-C, solar jack, three
RJ12 ports, ESP32-C6 on sockets), so the case is just a shell.

  python3 hardware/pcb/v3/concept.py          # prints the fit numbers and writes docs/renders/pcb-v3-layout.svg
  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_pcb_v3_concept.py --timeout 900

Coordinates (mm), same frame as ControllerV5: X along the rail from end A's outer face, Y across the rail (0 = the
tilt rod, -Y room side), Z up from the rail floor. The board lies flat; parts are boxes (x0, x1, y0, y1, z0, z1) or
cylinders, sized from their datasheets / listings (noted beside each).
"""
import math
import os

# ---------------------------------------------------------------- case and board
WALL, END_T, FLOOR = 2.0, 1.6, 1.2
BOARD = dict(x0=END_T + 0.4, len=115.0, y0=-24.0, y1=24.0, zb=2.9, t=1.6)       # 115 x 48, same height as V5's PCB
ZT = BOARD['zb'] + BOARD['t']                                                    # board top 4.5
X0, X1 = BOARD['x0'], BOARD['x0'] + BOARD['len']
L = X1 + 0.4 + END_T                                                             # box length
Y_IN = (BOARD['y0'] - 0.4, BOARD['y1'] + 0.4)
Y_OUT = (Y_IN[0] - WALL, Y_IN[1] + WALL)
ROD_Z, ROD = 24.0, 4.0
GROOVE_R, GROOVE_ZC, GROOVE_T = 5.0, 24.0 - 2.0 * math.sqrt(2) - 0.5 + 5.0, 1.0  # as V5: 0.5 under / 1.9 each side


def under_channel(y):
    """Lid's underside over |y| (the groove's channel is 1 mm thick round an r 5 groove)."""
    r = GROOVE_R + GROOVE_T
    return GROOVE_ZC - math.sqrt(r * r - y * y) if abs(y) < r else float('inf')


# ---------------------------------------------------------------- parts
P = {}       # name: ('box', x0, x1, y0, y1, z0, z1) | ('cylx', x0, x1, yc, zc, r) | ('cylz', xc, yc, z0, z1, r)
# 18650 holder: Keystone 1042P, through-hole pins, 77.05 L x 20.65 W x 14.86 H above the board (DigiKey / Future)
HX0 = X0 + 18.0
P['18650 holder (Keystone 1042P)'] = ('box', HX0, HX0 + 77.05, BOARD['y1'] - 20.65, BOARD['y1'], ZT, ZT + 14.86)
CELL_Y = BOARD['y1'] - 20.65 / 2
CELL_ZC = ZT + 1.0 + 9.25                                     # cell resting ~1 mm up in the holder
P['18650 cell (unprotected 65 / protected 69)'] = ('cylx', HX0 + 4.0, HX0 + 4.0 + 69.0, CELL_Y, CELL_ZC, 9.25)
# ESP32-C6 SuperMini on 8.5 mm sockets + 2.5 mm header spacers, rows 15.24 apart, USB-C toward end B
EX0, EYC = X0 + 47.0, -12.9
for ry in (EYC - 7.62, EYC + 7.62):
    P['ESP socket %+.0f' % ry] = ('box', EX0, EX0 + 25.4, ry - 1.27, ry + 1.27, ZT, ZT + 8.5)
EZ0 = ZT + 8.5 + 2.5
P['ESP32-C6 SuperMini (socketed)'] = ('box', EX0 - 0.3, EX0 + 25.7, EYC - 9.0, EYC + 9.0, EZ0, EZ0 + 1.0)
P['ESP pin tips'] = ('box', EX0, EX0 + 25.4, EYC - 9.0 + 0.3, EYC + 9.0 - 0.3, EZ0 + 1.0, EZ0 + 2.9)
P['ESP USB-C'] = ('box', EX0 + 25.7 - 6.0, EX0 + 25.7 + 1.5, EYC - 4.5, EYC + 4.5, EZ0 + 1.0, EZ0 + 4.3)
# charger: BQ25185 (WSON-10, 2.2 x 2) + its R/C, ORing Schottkys, cell protection (DW01A + FS8205A): SMD, JLC-assembled
P['Charger + protection (SMD)'] = ('box', X0 + 24.0, X0 + 39.5, -22.0, -6.0, ZT, ZT + 1.2)
P['NTC (on the holder)'] = ('box', HX0 + 36.0, HX0 + 40.0, BOARD['y1'] - 22.0, BOARD['y1'] - 20.9, ZT, ZT + 1.0)
P['470 uF (SMD 8 x 10)'] = ('cylz', X0 + 87.0, -12.0, ZT, ZT + 10.5, 4.0)
# ports. RJ12 Amphenol 87180-066LF: 13.2 W x 11.5 H, 17.3 deep, plug opening 1.73-8.50 above the board
RJ_W, RJ_H, RJ_D = 13.2, 11.5, 17.32
RJ = {'Port 1 (end A)': (X0, -15.0, +1), 'Port 2 (end B)': (X1, -14.6, -1), 'Port 3 (end B)': (X1, +1.0, -1)}
for nm, (ex, yc, s) in RJ.items():
    xa, xb = sorted((ex + s * 0.55, ex + s * RJ_D))
    P['RJ12 ' + nm] = ('box', xa, xb, yc - RJ_W / 2, yc + RJ_W / 2, ZT, ZT + RJ_H)
    P['PTC ' + nm] = ('box', ex + s * 20.0 - 2.3, ex + s * 20.0 + 2.3, yc - 1.6, yc + 1.6, ZT, ZT + 1.0)   # 1812 SMD
# USB-C receptacle, SMD 16-pin (JLC basic part), mid-mount at the board edge: 8.94 W x 3.26 H x 7.35 deep
UYC = -2.0
P['USB-C (SMD)'] = ('box', X0 - 0.3, X0 + 7.05, UYC - 4.47, UYC + 4.47, ZT - 0.6, ZT - 0.6 + 3.26)
# solar input: barrel jack, right angle THT, CUI PJ-002AH: 14.4 L x 9 W x 11 H, 2.0 mm pin (takes 5.5 x 2.1 plugs)
SYC = 8.3
P['Solar jack (PJ-002AH)'] = ('box', X0, X0 + 14.4, SYC - 4.5, SYC + 4.5, ZT, ZT + 11.0)
# mounting holes (M3), in corners the ports and the holder leave free
HOLES = [(X0 + 4.0, 20.5), (X1 - 4.0, 20.5), (X0 + 42.5, -21.0), (X0 + 80.0, -21.0)]

# the case height is set by the cell's top
CELL_TOP = CELL_ZC + 9.25
ZL = CELL_TOP + 0.4
TOP = ZL + 2.0


def report():
    out = ['Board %.0f x %.0f mm; case %.1f x %.1f x %.1f mm (V5: 164.6 x 52.5 x 25.8)' % (
        BOARD['len'], BOARD['y1'] - BOARD['y0'], L, Y_OUT[1] - Y_OUT[0], TOP)]
    # tallest parts and the groove
    for nm, p in P.items():
        if p[0] == 'box':
            _, x0, x1, y0, y1, z0, z1 = p
            yy = 0.0 if y0 < 0 < y1 else min(abs(y0), abs(y1))
            room = min(under_channel(yy), ZL) - z1
        elif p[0] == 'cylx':
            _, x0, x1, yc, zc, r = p
            room = min(min(under_channel(y), ZL) - (zc + math.sqrt(max(r * r - (y - yc) ** 2, 0)))
                       for y in [yc - r + k * r / 20 for k in range(41)])
        else:
            _, xc, yc, z0, z1, r = p
            yy = 0.0 if yc - r < 0 < yc + r else min(abs(yc - r), abs(yc + r))
            room = min(under_channel(yy), ZL) - z1
        out.append('  %-44s room above %.1f' % (nm, room))
    return out


def svg(path):
    """Top-view layout drawing (to scale, 6 px/mm)."""
    k, pad = 6.0, 30
    W, H = (L + 2 * pad / k) * k, (Y_OUT[1] - Y_OUT[0]) * k + 2 * pad + 50

    def tx(x):
        return pad + x * k

    def ty(y):                                       # +Y up the page
        return pad + (Y_OUT[1] - y) * k

    col = {'RJ12': '#2f2f2f', 'ESP': '#2b4fa8', '18650 c': '#3a8f4a', '18650 h': '#9aa', 'USB': '#888', 'Solar': '#c57b00',
           'Charger': '#7a3fa0', 'PTC': '#d07a2a', '470': '#444', 'NTC': '#b33'}
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica,Arial">' % (W, H),
         '<rect width="100%" height="100%" fill="#fff"/>',
         '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="#f4f4f4" stroke="#999"/>' % (
             tx(0), ty(Y_OUT[1]), L * k, (Y_OUT[1] - Y_OUT[0]) * k, 4 * k),
         '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#2f6b4f" opacity="0.85"/>' % (
             tx(X0), ty(BOARD['y1']), BOARD['len'] * k, (BOARD['y1'] - BOARD['y0']) * k),
         '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#c00" stroke-dasharray="6,4" stroke-width="1.5"/>' % (
             tx(-2), ty(0), tx(L + 2), ty(0)),
         '<text x="%.1f" y="%.1f" font-size="12" fill="#c00">tilt rod (lid groove above)</text>' % (tx(L / 2 - 30), ty(0) - 5)]
    order = sorted(P.items(), key=lambda kv: (kv[1][-1] if kv[1][0] != 'cylx' else 99))
    for nm, p in order:
        c = next((v for kk, v in col.items() if nm.startswith(kk) or kk in nm), '#666')
        if p[0] == 'box':
            _, x0, x1, y0, y1, z0, z1 = p
            s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="0.85" stroke="#000" stroke-width="0.5"/>' % (
                tx(x0), ty(y1), (x1 - x0) * k, (y1 - y0) * k, c))
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        elif p[0] == 'cylx':
            _, x0, x1, yc, zc, r = p
            s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" opacity="0.6" stroke="#000" stroke-width="0.5"/>' % (
                tx(x0), ty(yc + r), (x1 - x0) * k, 2 * r * k, 2 * k, c))
            cx, cy = (x0 + x1) / 2, yc
        else:
            _, xc, yc, z0, z1, r = p
            s.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" opacity="0.85"/>' % (tx(xc), ty(yc), r * k, c))
            cx, cy = xc, yc
        if not nm.startswith(('ESP socket', 'ESP pin', 'ESP USB', '18650 holder')):
            label = 'PTC' if nm.startswith('PTC') else nm.split(' (')[0]
            s.append('<text x="%.1f" y="%.1f" font-size="11" fill="#fff" text-anchor="middle" stroke="#000" stroke-width="2.5" paint-order="stroke">%s</text>' % (
                tx(cx), ty(cy) + 4, label))
    for hx, hy in HOLES:
        s.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#fff" stroke="#000"/>' % (tx(hx), ty(hy), 1.7 * k))
    s.append('<text x="%.1f" y="%.1f" font-size="13">End A: port 1, USB-C, solar jack</text>' % (tx(0), H - 30))
    s.append('<text x="%.1f" y="%.1f" font-size="13" text-anchor="end">End B: ports 2 and 3</text>' % (tx(L), H - 30))
    s.append('<text x="%.1f" y="%.1f" font-size="13" text-anchor="middle">Board %.0f x %.0f mm, case %.0f x %.1f x %.1f mm (to scale)</text>' % (
        W / 2, H - 10, BOARD['len'], BOARD['y1'] - BOARD['y0'], L, Y_OUT[1] - Y_OUT[0], TOP))
    s.append('</svg>')
    open(path, 'w').write('\n'.join(s))


if __name__ == '__main__':
    print('\n'.join(report()))
    repo = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..'))
    svg(os.path.join(repo, 'docs/renders/pcb-v3-layout.svg'))
