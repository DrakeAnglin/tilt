"""Build the controller carrier PCB in KiCad from netlist.py: outline, placement, nets, GND zones, routing, checks,
manufacturing files. Run with KiCad's Python:

  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 hardware/pcb/board.py

Coordinates in mm, origin at the board's top-left corner, y down (KiCad's convention). End A (the RJ12 jacks) is at
y = 0; the body runs down alongside the 18650 to end B, where the USB-C breakout plugs in.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import netlist as N  # noqa: E402
import router  # noqa: E402

FPLIB = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/'
OUT = os.path.join(HERE, 'controller')
PCB = os.path.join(OUT, 'controller.kicad_pcb')

W_BAR, D_BAR = 47.0, 47.0          # jack strip across end A (jacks, then each port's fuse and resistors behind it)
W_BODY, L = 27.0, 125.0            # body width (beside the cell) and total board length
MM = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


# ------------------------------------------------------------------ placement: (x, y, rotation) of each footprint origin
JACK_X = (11.0, 26.5, 42.0)
FILTER_Y = (50.6, 56.8, 63.0)        # the 1 k of each angle filter (its 100 n sits 3.1 mm below)
PLACE = {
    # RJ12 jacks, opening out of end A (footprint front is +y, so turned 180 deg); fronts flush with the edge
    'J9': (JACK_X[0], 17.32, 180), 'J10': (JACK_X[1], 17.32, 180), 'J11': (JACK_X[2], 17.32, 180),
    # ESP32-C6 sockets, turned so the ESP's USB faces end B (over low parts: a cable fits with the ESP plugged in):
    # 5V row on the left, TX row on the right, pin 1 of each at the bottom
    'J1': (4.5, 72.0, 180), 'J2': (19.74, 72.0, 180),
    # angle filters and the 10 uF, under the plugged-in ESP (it stands 8.5 mm up on its sockets)
    'R5': (8.0, FILTER_Y[0], 0), 'C3': (9.0, FILTER_Y[0] + 3.1, 0),
    'R6': (8.0, FILTER_Y[1], 0), 'C4': (9.0, FILTER_Y[1] + 3.1, 0),
    'R7': (8.0, FILTER_Y[2], 0), 'C5': (9.0, FILTER_Y[2] + 3.1, 0),
    'C1': (8.0, 69.6, 0),
    # bulk capacitor, battery + test pad, holes
    'C9': (31.0, 42.0, 0), 'TP1': (39.0, 38.6, 0),
    'H1': (3.5, 41.0, 0), 'H2': (W_BAR - 3.5, 43.3, 0), 'H3': (23.8, 121.5, 0),
    # power section, two flat parts per row, rows 5 mm apart (value printed above each part)
    'D3': (2.0, 79.0, 0), 'R1': (15.5, 79.0, 0),
    'R2': (2.0, 84.0, 0), 'C2': (16.0, 84.0, 0),
    'R3': (2.0, 89.0, 0), 'R4': (15.5, 89.0, 0),
    'C6': (2.5, 94.0, 0), 'D1': (15.5, 94.0, 0),
    'D2': (2.0, 99.0, 0),
    'TP2': (13.5, 99.0, 0), 'TP3': (17.0, 99.0, 0), 'TP4': (20.5, 99.0, 0), 'TP5': (24.0, 99.0, 0),
    'D4': (2.0, 105.0, 0),
    # the three connectors, all different: battery (XH 2), charger (XH 6), solar (ZH 2)
    'J4': (17.5, 105.0, 0), 'J5': (3.0, 113.5, 0), 'J8': (22.0, 113.5, 0),
    # USB-C breakout socket across end B: the breakout's USB-C overhangs the end
    'J3': (4.5, 122.5, 90),
}
for _k, _ox in enumerate(JACK_X):
    PLACE['F%d' % (_k + 1)] = (_ox - 7.4, 22.6, 0)                     # PTC behind each jack
    # behind each jack, left to right: IN2 series, EN series, EN pull-down, IN1 series (all standing in a row, pad 1 up)
    r_in1, r_in2, r_en, r_pd = 8 + 4 * _k, 9 + 4 * _k, 10 + 4 * _k, 11 + 4 * _k
    for _ref, _dx in ((r_in2, -8.6), (r_en, -5.4), (r_pd, -2.2), (r_in1, 1.0)):
        PLACE['R%d' % _ref] = (_ox + _dx, 28.0, 270)


def outline(board):
    pts = [(0, 0), (W_BAR, 0), (W_BAR, D_BAR), (W_BODY, D_BAR), (W_BODY, L), (0, L)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(x0, y0))
        s.SetEnd(P(x1, y1))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        board.Add(s)
    return pts


def build():
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = MM(0.25)
    ds.m_ViasMinSize = MM(0.7)
    ds.m_MinThroughDrill = MM(0.35)
    ds.m_CopperEdgeClearance = MM(0.4)
    outline(board)
    nets = {}
    # unused connector pins get KiCad's own no-connect net names, as the schematic gives them (schematic parity)
    nc = {}
    for ref, value, key, pads, note in N.PARTS:
        if key.startswith(('SOCK', 'XH', 'ZH', 'RJ')):
            for pad, net in pads.items():
                if not net:
                    nc[(ref, pad)] = 'unconnected-(%s-Pin_%d-Pad%d)' % (ref, pad, pad)
    for name in sorted(set(N.nets()) | set(nc.values())):
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    for ref, value, key, pads, note in N.PARTS:
        lib, name = N.FP[key].split(':')
        fp = pcbnew.FootprintLoad(FPLIB + lib + '.pretty', name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))                  # keep the library nickname (schematic parity)
        fp.SetReference(ref)
        fp.SetValue(value)
        x, y, rot = PLACE[ref]
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num.isdigit() and pads.get(int(num)):
                pad.SetNet(nets[pads[int(num)]])
            elif num.isdigit() and (ref, int(num)) in nc:
                pad.SetNet(nets[nc[(ref, int(num))]])
            if ref in ('C3', 'C4', 'C5', 'C6') and num == '2':      # small filter-cap GND pads under the ESP: solid to the pour
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        board.Add(fp)
    return board


SHORT = {'1M': '1M', '1k': '1k', '100nF': '100n', '10uF': '10u', '1N5819': '1N5819', '1N5341B 6.2V 5W': '6V2 5W Z',
         '220': '220', '10': '10', '100k': '100k', '470uF 10V': '470u', '0.75A PTC': 'PTC'}
LABELS = [  # (text, x, y, size, angle): connector names and orientation marks on the top silkscreen
    ('PORT 1', 3.0, 20.4, 0.9, 0), ('PORT 2', 18.5, 20.4, 0.9, 0), ('PORT 3', 34.0, 20.4, 0.9, 0),
    ('ESP32-C6: chip up, USB this way', 13.1, 75.6, 0.8, 0),
    ('5V', 1.4, 72.0, 0.8, 90), ('TX', 23.0, 72.0, 0.8, 90),
    ('BAT+', 42.2, 38.6, 0.8, 0),
    ('5V', 13.5, 97.1, 0.8, 0), ('3V3', 17.0, 97.1, 0.8, 0), ('PWR', 20.5, 97.1, 0.8, 0), ('GND', 24.0, 97.1, 0.8, 0),
    ('BATTERY (red +)', 18.75, 101.2, 0.8, 0), ('CHARGER', 9.25, 109.8, 0.8, 0), ('SOLAR', 22.75, 110.4, 0.8, 0),
    ('USB-C BOARD (socket out)', 10.85, 119.9, 0.8, 0),
    # pin labels on the three power connectors (a reversed plug is the one mistake that destroys parts)
    ('-', 17.5, 109.8, 1.0, 0), ('+', 20.0, 109.8, 1.0, 0),                           # J4 battery: pin 1 GND, pin 2 BATT+ (red)
    ('G', 3.0, 118.4, 0.8, 0), ('B+', 5.5, 118.4, 0.8, 0), ('L+', 10.5, 118.4, 0.8, 0), ('P+', 15.5, 118.4, 0.8, 0),  # J5
    ('-', 22.0, 117.3, 1.0, 0), ('+', 23.5, 117.3, 1.0, 0),                            # J8 solar: pin 1 GND, pin 2 SOL+
]


def silk(board):
    """Values on the parts instead of reference codes, connector labels, the ESP and USB-C board outlines."""
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        if ref[0] in 'RCDF':
            val = pcbnew.PCB_TEXT(board)
            board.Add(val)
            val.SetText(SHORT.get(fp.GetValue(), fp.GetValue()))
            val.SetLayer(pcbnew.F_SilkS)
            val.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
            val.SetTextThickness(MM(0.13))
            span = {'F': 5.1, 'R': 7.62, 'D': 10.16 if 'W' in fp.GetValue() else 7.62, 'C': 5.0 if 'u' not in fp.GetValue() or 'F' not in fp.GetValue() else 3.5}[ref[0]]
            if ref == 'C9':
                span = 3.5
            x, y, rot = PLACE[ref]
            if rot == 270:                                      # standing in a row behind a jack: value along the part
                val.SetPosition(P(x, y + 3.81))
                val.SetTextAngleDegrees(90)
            elif ref[0] == 'F':                                 # PTC: inside its outline, between its legs
                val.SetPosition(P(x + 2.55, y + 0.95))
            elif ref == 'C9':                                   # bulk cap: just above the can
                val.SetPosition(P(x + 1.75, y - 4.75))
            elif ref == 'C1':                                   # under the ESP: just below the part
                val.SetPosition(P(x + 2.5, y + 2.0))
            elif ref == 'D4':
                val.SetPosition(P(x + 5.08, y - 3.0))
            else:
                under_esp = 48 < y < 72                         # the filters: value inside the body (the ESP covers them)
                val.SetPosition(P(x + span / 2, y - (0 if under_esp else 2.3)))
    for text, x, y, size, ang in LABELS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(size * 0.15))
        t.SetPosition(P(x, y))
        t.SetTextAngleDegrees(ang)
        board.Add(t)
    for text, x, y, size in (('Automated blinds controller v2', 13.5, 76.0, 0.9), ('ESP32-C6 + MCP73871 carrier', 13.5, 77.4, 0.8)):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(pcbnew.B_SilkS)
        t.SetMirrored(True)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(size * 0.15))
        t.SetPosition(P(x, y))
        board.Add(t)


POWER = {'VBAT': 0.8, 'GND': 0.8, 'PWR': 0.6, 'BATT+': 0.8, '+5V': 0.6, 'VBUS': 0.6, 'SOL+': 0.6,
         'P1_VBAT': 0.8, 'P2_VBAT': 0.8, 'P3_VBAT': 0.8}
# motor return: jacks' GND pins -> bulk cap -> charger / battery GND, as one wide track before the rest of GND
MOTOR_GND = [('J5', '1'), ('J4', '1'), ('C9', '2'), ('J9', '3'), ('J10', '3'), ('J11', '3')]


def inset(pts, d):
    """Shrink the rectilinear outline by d (mm) on every side (points listed clockwise in y-down coordinates)."""
    n = len(pts)
    out = []
    for k in range(n):
        (xp, yp), (x, y), (xn, yn) = pts[k - 1], pts[k], pts[(k + 1) % n]
        # inward normal of the incoming and outgoing edges (clockwise, y down: inward = right-hand side rotated)
        def normal(ax, ay, bx, by):
            dx, dy = bx - ax, by - ay
            ln = (dx * dx + dy * dy) ** 0.5
            return -dy / ln, dx / ln
        n1, n2 = normal(xp, yp, x, y), normal(x, y, xn, yn)
        out.append((x + d * (n1[0] + n2[0]) if n1[0] != n2[0] or n1[0] else x + d * n1[0],
                    y + d * (n1[1] + n2[1]) if n1[1] != n2[1] or n1[1] else y + d * n1[1]))
    return out


def gnd_zones(board, pts):
    net = board.GetNetsByName()['GND']
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(net)
        z.SetLocalClearance(MM(0.3))
        z.SetMinThickness(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in inset(pts, 0.5):
            ol.Append(MM(x), MM(y))
        board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    b = build()
    pts = [(0, 0), (W_BAR, 0), (W_BAR, D_BAR), (W_BODY, D_BAR), (W_BODY, L), (0, L)]
    # wide power nets first, then the signals; GND last (the zones also join it)
    # the short hops from each jack to its resistors first (the jack pins are tightly packed), then power, then the rest
    jack_side = ['P%d_%s' % (k, sig) for k in (1, 2, 3) for sig in ('IN1', 'IN2', 'EN', 'ANG')]
    order = jack_side + ['VBAT', 'BATT+', 'PWR', '+5V', 'VBUS', 'SOL+', 'P1_VBAT', 'P2_VBAT', 'P3_VBAT'] + \
        sorted(n for n in N.nets() if n not in POWER and n not in jack_side) + ['GND']
    fails, (nt, nv), grid = router.route(b, pts, POWER, order, first={'GND': (MOTOR_GND, 1.0)})
    print('routed: %d track segments, %d vias' % (nt, nv))
    print('could not route:', fails or 'none')
    print('GND stitching vias:', router.stitch(b, grid, 'GND', 4.0))
    gnd_zones(b, pts)
    silk(b)
    b.Save(PCB)
    print('saved', PCB)
