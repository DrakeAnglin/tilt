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

W_BAR, D_BAR = 47.0, 27.0          # jack strip across end A
W_BODY, L = 27.0, 113.0            # body width (beside the cell) and total board length
MM = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


# ------------------------------------------------------------------ placement: (x, y, rotation) of each footprint origin
JACK_X = (11.0, 26.5, 42.0)
DY = 3.0                            # body parts sit this much lower than first drafted (room for the holes)
PLACE = {
    # RJ12 jacks, opening out of end A (footprint front is +y, so turned 180 deg); fronts flush with the edge
    'J9': (JACK_X[0], 17.32, 180), 'J10': (JACK_X[1], 17.32, 180), 'J11': (JACK_X[2], 17.32, 180),
    # ESP32-C6 sockets: chip up, USB toward the jacks, so the TX row is on the left and the 5V row on the right
    'J2': (4.5, 32.0 + DY, 0), 'J1': (19.74, 32.0 + DY, 0),
    # angle filters and the 10 uF, low enough to sit under the plugged-in ESP (it stands 8.5 mm up on its sockets)
    'R5': (7.6, 34.5 + DY, 0), 'C3': (8.1, 37.5 + DY, 0),
    'R6': (7.6, 41.0 + DY, 0), 'C4': (8.1, 44.0 + DY, 0),
    'R7': (7.6, 47.5 + DY, 0), 'C5': (8.1, 50.5 + DY, 0),
    'C1': (9.5, 28.6 + DY, 0),
    # power section, two flat parts per row, rows 5 mm apart (value printed above each part)
    'D3': (2.0, 64.0, 0), 'R1': (15.5, 64.0, 0),
    'R2': (2.0, 69.0, 0), 'C2': (16.0, 69.0, 0),
    'R3': (2.0, 74.0, 0), 'R4': (15.5, 74.0, 0),
    'D1': (2.0, 79.0, 0), 'D2': (15.5, 79.0, 0),
    'D4': (2.0, 84.0, 0),
    # JST-XH headers, label above each: battery, charger (+, LOAD+, GND), solar
    'J4': (3.0, 92.5, 0), 'J5': (12.0, 92.5, 0), 'J6': (21.0, 92.5, 0),
    'J7': (3.0, 102.0, 0), 'J8': (14.0, 102.0, 0),
    # USB-C breakout socket across end B: the breakout's USB-C overhangs the end
    'J3': (7.15, 110.0, 90),
    # mounting holes: two below the jacks, one beside the JST headers
    'H1': (3.5, 23.6, 0), 'H2': (W_BAR - 3.5, 23.6, 0), 'H3': (W_BODY - 3.3, 102.0, 0),
}


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
    for name in sorted(N.nets()):
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    for ref, value, key, pads, note in N.PARTS:
        lib, name = N.FP[key].split(':')
        fp = pcbnew.FootprintLoad(FPLIB + lib + '.pretty', name)
        fp.SetReference(ref)
        fp.SetValue(value)
        x, y, rot = PLACE[ref]
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num.isdigit() and pads.get(int(num)):
                pad.SetNet(nets[pads[int(num)]])
        board.Add(fp)
    return board


SHORT = {'1M': '1M', '1k': '1k', '100nF': '100n', '10uF': '10u', '1N5819': '1N5819', '6.2V zener 1W': '6V2 Z'}
LABELS = [  # (text, x, y, size, angle): connector names and orientation marks on the top silkscreen
    ('PORT 1', 7.8, 25.4, 1.0, 0), ('PORT 2', 23.3, 25.4, 1.0, 0), ('PORT 3', 38.8, 25.4, 1.0, 0),
    ('ESP32-C6: chip up, USB toward the ports', 13.5, 60.6, 0.8, 0),
    ('TX', 1.5, 35.0, 0.8, 90), ('5V', 22.8, 35.0, 0.8, 90),
    ('BATTERY', 4.25, 88.9, 0.8, 0), ('CHG +', 13.25, 88.9, 0.8, 0), ('LOAD +', 22.25, 88.9, 0.8, 0),
    ('CHG GND', 5.5, 98.4, 0.8, 0), ('SOLAR', 15.25, 98.4, 0.8, 0),
    ('USB-C BOARD (socket out)', 13.5, 107.0, 0.8, 0),
]


def silk(board):
    """Values on the parts instead of reference codes, connector labels, the ESP and USB-C board outlines."""
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        fp.Reference().SetVisible(False)
        val = fp.Value()
        if ref[0] in 'RCD':
            val.SetText(SHORT.get(fp.GetValue(), fp.GetValue()))
            val.SetLayer(pcbnew.F_SilkS)
            val.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
            val.SetTextThickness(MM(0.13))
            span = 7.62 if ref[0] in 'RD' else 5.0
            under_esp = PLACE[ref][1] < 60                       # the filters: value inside the body (the ESP covers them)
            val.SetPosition(P(PLACE[ref][0] + span / 2, PLACE[ref][1] - (0 if under_esp else 2.3)))
            val.SetVisible(True)
        else:
            val.SetVisible(False)
    for text, x, y, size, ang in LABELS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(size * 0.15))
        t.SetPosition(P(x, y))
        t.SetTextAngleDegrees(ang)
        board.Add(t)
    for text, x, y, size in (('Automated blinds controller v1', 13.5, 61.0, 0.9), ('ESP32-C6 + MCP73871 carrier', 13.5, 62.4, 0.8)):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(pcbnew.B_SilkS)
        t.SetMirrored(True)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(size * 0.15))
        t.SetPosition(P(x, y))
        board.Add(t)


POWER = {'VBAT': 0.8, 'GND': 0.8, 'PWR': 0.6, 'BATT+': 0.8, '+5V': 0.6, 'VBUS': 0.6, 'SOL+': 0.6}


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
    order = ['VBAT', 'BATT+', 'PWR', '+5V', 'VBUS', 'SOL+'] + sorted(n for n in N.nets() if n not in POWER) + ['GND']
    fails, (nt, nv) = router.route(b, pts, POWER, order)
    print('routed: %d track segments, %d vias' % (nt, nv))
    print('could not route:', fails or 'none')
    gnd_zones(b, pts)
    silk(b)
    b.Save(PCB)
    print('saved', PCB)
