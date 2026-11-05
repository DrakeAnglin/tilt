"""ControllerV5: the controller box for the carrier PCB (hardware/pcb, v2.1), with the 18650, the MCP73871 charger
module and its bulk capacitor, and the USB-C charge port.

Why it is longer than V4 (126 -> 165 mm): the rod's groove runs down the middle of the lid, and under it there is only
19.2 mm of height. The PCB is 47 mm wide at the jacks and 27 mm beside the cell, so the cell takes the back side
and the charger (30.5 x 31.5 mm) can only go in its own bay past the end of the PCB. The USB-C breakout therefore
moves off the PCB's J3 socket onto end wall B, standing on edge in a card slot, joined to J3 by a 2-wire lead.

Layout, end A (ports) to end B (USB-C):
  * PCB on three floor bosses, jacks behind windows in end wall A. Three M3 flat-head screws come up from under the
    box, through the bosses and the PCB's holes, into heat-set inserts in three lid posts: the screws clamp the PCB
    between the floor and the lid, and hold the lid on.
  * 18650 in two saddles along the back wall, beside the PCB body; the lid presses it down.
  * Charger bay: the charger goes in as ONE subassembly - module + its capacitor + the 6-pin harness, soldered on the
    bench. The capacitor is soldered in the module's own footprint (two holes 7 mm apart at one corner) with its legs
    bent 90 deg, so it lies on its side across the module (standing up it would be 33 mm: too tall). It covers the
    LOAD pad, so that one harness wire is soldered from underneath and runs under the module (3 mm standoffs).
    The module sits on four corner pads between guides; two lid pins clamp its edges; a tray saddle carries the
    capacitor's free end. A lid post with a fourth insert (fourth screw from below) and the solar lead's floor
    route are on the room side of the bay.
  * USB-C breakout on edge: front edge in a pocket in end wall B (socket face flush), back edge in a slot, bottom edge
    in a floor groove, top edge under a lid fin.

Height budget (the reason the PCB sits 2 mm off the floor): ESP pins on its sockets reach 18.7 mm under a 19.2 mm groove.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v5.py --timeout 1800

Coordinates (mm): X along the rail from end A's outer face, Y across (-Y room side), Z up from the rail floor.
The PCB's KiCad coordinates (x across, y down from the jack edge) map to X = y + PCB_X, Y = x + PCB_Y.
"""

import math
import os

C = dict(
    half_w=27.7, top=25.8, wall=2.0, floor_z=0.0, floor=1.2, lid=2.0, end_t=2.4, end_a=1.6, corner_r=4.0, edge_r=1.5,
    rail_w=55.5, rail_h=36.5, rail_wall=2.0, lip_in=4.5, lip_h=3.0, rod_z=24.0, rod=4.0,
    # height: with the three fuses folded, the tallest part outside the groove is the charger's capacitor lying on its
    # module (top 23.3), so the lid's underside is at 23.8 and its top at 25.8 (was 33.3 with the fuses upright)
    # PTC fuses (Bel 0ZRE0075FF, datasheet: A 11.5 wide, B 23.4 seated, E 4.8 thick, C 5.1 / F 1.9 lead offset): an
    # 11.5 disc on ~11.9 mm legs (KiCad's model; B - A). Each is folded toward the ESP, legs bent 1.6 below the body,
    # so the disc lies flat over its own four resistors
    fuse_leg=11.9, fuse_bend=1.6, fuse_w=11.5, fuse_t=4.8, fuse_body=11.5,
    # rod groove: floor 20.2 (the rod sweeps down to 21.17), 1.0 thick, so its underside is 19.2
    groove_hw=6.0, groove_floor=20.2, groove_t=1.0, groove_wall=1.2,
    # PCB: 1.7 mm above the floor, which is recessed 0.4 under the PCB (2.1 mm for its leads: the XH headers' tails
    # reach 1.8 below), board 1.52 (as exported)
    pcb_gap=1.7, floor_recess=0.4, pcb_t=1.52, pcb_x=1.8, pcb_y=-25.0, pcb_len=125.0, pcb_bar=47.0, pcb_body=27.0,
    holes=((3.5, 41.0), (43.5, 43.3), (23.8, 121.5)),            # H1, H2, H3 (KiCad x, y)
    boss_d=8.0, post_d=8.0, ins_d=4.0, ins_depth=6.7, screw_l=10.0,            # M3 x 5.7 heat-set inserts, Ø4.0 hole
    # RJ12 Amphenol 87180-066LF (drawing 87180 sheet 1-3): 13.2 W x 11.5 H, front face 0.55 behind the board edge
    rj_w=13.2, rj_h=11.5, rj_front=0.55, rj_back=17.32, rj_x=(7.825, 23.325, 38.825), rj_mouth_w=9.65,
    rj_mouth=(1.73, 8.50),          # the jack's plug opening, above the board (87180 drawing); latch tab-down
    # end wall A aperture: the plug's outline + 0.25 a side, a notch under it for the latch lever, 0.4 chamfered bezel
    ap_w=10.15, ap_z=(1.45, 8.80), ap_r=0.6, latch_w=5.0, latch_z0=0.3, bezel=0.5,
    rj_tail=2.1, rj_peg=1.9,
    # ESP32-C6 SuperMini (26 x 18) on 8.5 mm sockets + 2.5 mm header spacers, USB toward end B
    esp_l=26.0, esp_w=18.0, esp_t=1.0, esp_xc=12.12, esp_y0=47.57, sock_h=8.59, spacer=2.5, esp_tip=1.9,
    # 18650 (protected, JST-XH lead) along the back wall
    bat_d=19.0, bat_l=69.0,
    # charger module (DIYMORE MCP73871, 31.5 x 30.5) and its capacitor (16 x 26)
    # module photo x (31.5) runs across the box (+Y), photo y (30.5) along it (+X): its capacitor corner ends up at the
    # back wall, its PWR / BATT pads on the groove side
    chg_w=31.5, chg_d=30.5, chg_t=1.6, chg_gap=3.0, chg_y0=-6.1,
    cap_d=16.0, cap_h=26.0, cap_holes=((19.0, 5.5), (26.0, 5.5)), cap_up=1.5, cap_end=1.5,
    # USB-C breakout (Cermant, 22.1 x 13.05, socket 9.1 x 3.26 x 7.35 sticking out 1.45), on edge, socket face flush
    usb_w=22.1, usb_d=13.05, usb_t=1.6, usb_sw=9.1, usb_sh=3.26, usb_sl=7.35, usb_stick=1.45, usb_yc=-21.2,
    usb_z0=0.7, usb_pin_row=1.04,
)
c = C
C['iw'] = c['half_w'] - c['wall']
C['fz'] = c['floor_z'] + c['floor']
C['zl'] = c['top'] - c['lid']
C['zb'] = C['fz'] + c['pcb_gap']                     # PCB underside
C['zt'] = C['zb'] + c['pcb_t']                       # PCB top
C['g_under'] = c['groove_floor'] - c['groove_t']     # 19.2
C['gw_out'] = c['groove_hw'] + c['groove_wall']      # 7.2
C['pcb_end'] = c['pcb_x'] + c['pcb_len']
C['chg_x0'] = C['pcb_end'] + 2.0                       # charger bay: room for its corner seat between it and the PCB
C['bat_x0'] = c['pcb_x'] + c['pcb_bar'] + 2.0          # cell starts past the PCB's bar (end stop clear of the H2 post)
C['in_b'] = C['chg_x0'] + c['cap_holes'][0][1] + c['cap_end'] + c['cap_h'] + 0.4    # end wall B inner face: past the capacitor
C['L'] = C['in_b'] + c['end_t']
C['bat_y'] = C['iw'] - 0.4 - c['bat_d'] / 2
C['bat_zc'] = C['fz'] + 0.5 + c['bat_d'] / 2
C['esp_z0'] = C['zt'] + c['sock_h'] + c['spacer']    # ESP underside
# USB-C breakout on edge: component face toward the room-side wall, socket face flush with end B's outer face
C['usb_front'] = C['L'] - c['usb_stick']
C['usb_back'] = C['usb_front'] - c['usb_d']
C['usb_yf'] = c['usb_yc'] + c['usb_sh'] / 2          # board's component face
C['usb_zc'] = c['usb_z0'] + c['usb_w'] / 2
C['solar_y'] = -9.8
L = C['L']


def K(x, y):
    """KiCad (x, y) on the PCB -> box (X, Y)."""
    return y + c['pcb_x'], x + c['pcb_y']


HOLES = [K(*h) for h in c['holes']]
POST_B = (C['chg_x0'] + 6.6, -17.5)                              # fourth screw: the lid post in the charger bay
SCREWS = [(x, y, C['zb'], c['screw_l']) for x, y in HOLES + [POST_B]]   # (x, y, boss top, length): one size, M3 x 10


def build(tbm, bx, cyl, cone, uni, cut, rbox):
    """{group: [(name, body)]}. rbox(x0, x1, y0, y1, z0, z1, r) = box with its four vertical edges rounded."""
    iw, fz, zl, zb, zt = C['iw'], C['fz'], C['zl'], C['zb'], C['zt']
    hw, gu, gw = c['half_w'], C['g_under'], C['gw_out']
    in_b = C['in_b']
    out = {}

    def ceiling(y, half=0.0):
        """Lid underside over a feature spanning y +/- half: the groove channel's underside if it overlaps it."""
        return gu if abs(y) - half < gw + 0.3 else zl

    # ================================================================ tray
    F0 = c['floor_z'] + 0.3                              # floor-standing features start inside the floor
    tray = cut(rbox(0, L, -hw, hw, c['floor_z'], zl, c['corner_r']),
               rbox(c['end_a'], in_b, -iw, iw, fz, zl + 1, c['corner_r'] - c['wall']))
    # relief in end A's room-side inner corner fillet for the PCB's corner (the board sits 0.2 off end wall A)
    tray = cut(tray, bx(c['end_a'] - 0.01, c['end_a'] + 2.2, -iw - 0.01, -iw + 2.2, zb - 0.3, zt + 0.3))
    for xa, xb in ((-1, c['end_a'] + 0.01), (in_b - 0.01, L + 1)):        # the lid's groove channel crosses both ends
        tray = cut(tray, bx(xa, xb, -gw - 0.15, gw + 0.15, gu - 0.15, zl + 1))
    # --- floor recessed 0.4 under the PCB's outline (+0.5): room for its leads without raising the ESP
    fr = fz - c['floor_recess']
    bar_x1, _ = K(0, c['pcb_bar'])
    tray = cut(tray, bx(c['end_a'] - 0.01, bar_x1 + 0.5, -iw - 0.01, K(c['pcb_bar'], 0)[1] + 0.5, fr, fz + 0.01),
               bx(bar_x1 - 0.01, C['pcb_end'] + 0.5, -iw - 0.01, K(c['pcb_body'], 0)[1] + 0.5, fr, fz + 0.01))
    # --- PCB nest: it drops in and is located before the lid goes on: end wall A (0.2), the room-side wall (0.7) and
    # free-standing ribs along the bar's and the body's back edges (0.2); all below the board's top face
    ztop = C['zt'] - 0.3
    by_bar, by_body = K(c['pcb_bar'], 0)[1], K(c['pcb_body'], 0)[1]
    for x0, x1, y0 in ((20.0, 40.0, by_bar), (58.0, 72.0, by_body), (100.0, 114.0, by_body)):
        tray = uni(tray, bx(x0, x1, y0 + 0.2, y0 + 1.4, F0, ztop))
    # --- PCB: three bosses under its holes; through holes with countersinks from below (screws come up)
    for hx, hy in HOLES:
        tray = uni(tray, cyl((hx, hy, F0), (hx, hy, zb), c['boss_d'] / 2))
    # --- jacks: plug-shaped apertures in end wall A, pockets under their tails and pegs, port marks (1, 2, 3 dots)
    def aperture(y, grow, xa, xb):
        """The plug's outline (rounded corners) + the latch-lever notch under it, grown by `grow` all round."""
        w, (z0, z1), r = c['ap_w'] / 2 + grow, c['ap_z'], c['ap_r'] + grow
        z0, z1 = zt + z0 - grow, zt + z1 + grow
        a = uni(bx(xa, xb, y - w + r, y + w - r, z0, z1), bx(xa, xb, y - w, y + w, z0 + r, z1 - r))
        for yy in (y - w + r, y + w - r):
            for zz in (z0 + r, z1 - r):
                a = uni(a, cyl((xa, yy, zz), (xb, yy, zz), r))
        lw = c['latch_w'] / 2 + grow
        return uni(a, bx(xa, xb, y - lw, y + lw, zt + c['latch_z0'] - grow, z0 + r))

    for n, xk in enumerate(c['rj_x']):
        _, y = K(xk, 0)
        tray = cut(tray, aperture(y, 0.0, -1, c['end_a'] + 0.01),
                   aperture(y, c['bezel'], -1, 0.4))                                 # 0.4 deep bezel round it
        x0, _ = K(0, 7.0)
        x1, _ = K(0, c['rj_back'] + 1.0)
        tray = cut(tray, bx(x0, x1, y - 6.6, y + 6.6, c['floor_z'] + 0.5, fz + 0.01))
        for k in range(n + 1):
            dy = (k - n / 2.0) * 2.4
            tray = cut(tray, cyl((-1, y + dy, 2.6), (0.5, y + dy, 2.6), 0.6))
    # --- 18650: two saddles and two end stops (the end-B stop is low: the lead leaves that end)
    by, bc = C['bat_y'], C['bat_zc']
    for sx in (C['bat_x0'] + 9, C['bat_x0'] + c['bat_l'] - 13):
        tray = uni(tray, cut(bx(sx, sx + 4, by - 6.5, iw + 0.5, F0, bc - 2.0),
                             cyl((sx - 1, by, bc), (sx + 5, by, bc), c['bat_d'] / 2 + 0.2)))
    # end stops, centred on the cell's axis; they bear on its end below the + button (the lead leaves the end-B end higher up)
    tray = uni(tray, bx(C['bat_x0'] - 1.4, C['bat_x0'] - 0.2, by - 4.0, by + 4.0, F0, bc - 2.5),
               bx(C['bat_x0'] + c['bat_l'] + 0.2, C['bat_x0'] + c['bat_l'] + 1.4, by - 4.0, by + 4.0, F0, bc - 4.0))
    # --- charger subassembly: four one-piece corner seats. Each is a 2 x 2 ledge under the board's corner (clear of the
    # pads' solder) joined to an L of 1.2 mm walls round the corner, 0.2 clear of the board and 1 mm above its top. On
    # the back-wall side there is no wall leg (the tray wall is 0.3 away and locates it); the ledge runs into the wall.
    gx0, gx1, gy0 = C['chg_x0'], C['chg_x0'] + c['chg_d'], c['chg_y0']
    gy1 = gy0 + c['chg_w']
    cz = fz + c['chg_gap']
    gtop = cz + c['chg_t'] + 1.0
    for px, py in ((gx0, gy0), (gx1, gy0), (gx0, gy1), (gx1, gy1)):
        sx, sy = (1 if px == gx0 else -1), (1 if py == gy0 else -1)
        wall_side = py == gy1                                  # back wall within 0.3
        yo = (iw + 0.01) if wall_side else py - sy * 1.4       # outer edge of the seat across the box
        seat = bx(px - sx * 1.4, px + sx * 2.0, yo, py + sy * 2.0, F0, cz)                          # ledge
        seat = uni(seat, bx(px - sx * 1.4, px - sx * 0.2, yo, py + sy * 5.0, F0, gtop))             # leg along the end
        if not wall_side:
            seat = uni(seat, bx(px - sx * 1.4, px + sx * 5.0, py - sy * 1.4, py - sy * 0.2, F0, gtop))   # leg along the side
        tray = uni(tray, seat)
    cap_y = gy0 + (c['cap_holes'][0][0] + c['cap_holes'][1][0]) / 2
    cap_x0 = gx0 + c['cap_holes'][0][1] + c['cap_end']
    cap_z = cz + c['chg_t'] + c['cap_up'] + c['cap_d'] / 2
    tray = uni(tray, cut(bx(gx1 + 0.3, in_b + 0.01, cap_y - 6.5, cap_y + 6.5, F0, cap_z - 3.0),
                         cyl((gx1, cap_y, cap_z), (in_b + 1, cap_y, cap_z), c['cap_d'] / 2 + 0.3)))
    # --- USB-C breakout: front edge in a pocket in end wall B, back edge in a slot, bottom edge in a floor groove;
    # vertical stadium window for the socket
    yf, yb = C['usb_yf'], C['usb_yf'] + c['usb_t']
    zu0, zu1 = c['usb_z0'], c['usb_z0'] + c['usb_w']
    tray = cut(tray, bx(in_b - 0.01, C['usb_front'] + 0.2, yf - 0.15, yb + 0.15, zu0 - 0.2, zu1 + 0.2))
    tray = cut(tray, bx(C['usb_back'] - 0.2, in_b + 0.01, yf - 0.15, yb + 0.15, zu0 - 0.2, fz + 0.01))
    xs = C['usb_back']
    slot = uni(bx(xs - 2.0, xs + 1.6, yf - 2.0, yf - 0.15, F0, zu1 - 2.0),          # component side
               bx(xs - 2.0, xs - 0.6, yb + 0.15, yb + 1.4, F0, zu1 - 2.0),           # back side (short of its header)
               bx(xs - 2.0, xs - 0.2, yf - 2.0, yb, F0, zu1 - 2.0))                  # end stop
    tray = uni(tray, slot)
    wr = c['usb_sh'] / 2 + 0.2
    hz = c['usb_sw'] / 2 - c['usb_sh'] / 2
    zc = C['usb_zc']
    tray = cut(tray, bx(in_b - 1, L + 1, c['usb_yc'] - wr, c['usb_yc'] + wr, zc - hz, zc + hz),
               cyl((in_b - 1, c['usb_yc'], zc - hz), (L + 1, c['usb_yc'], zc - hz), wr),
               cyl((in_b - 1, c['usb_yc'], zc + hz), (L + 1, c['usb_yc'], zc + hz), wr))
    wr2 = wr + 0.6
    tray = cut(tray, bx(L - 0.5, L + 1, c['usb_yc'] - wr2, c['usb_yc'] + wr2, zc - hz, zc + hz),
               cyl((L - 0.5, c['usb_yc'], zc - hz), (L + 1, c['usb_yc'], zc - hz), wr2),
               cyl((L - 0.5, c['usb_yc'], zc + hz), (L + 1, c['usb_yc'], zc + hz), wr2))
    # --- charger vents: four slots in end wall B above the module (the floor sits on the rail, so not there)
    # 2 mm slots on a 5 mm pitch (3 mm webs), tops 5 mm below the groove notch in the wall
    for vy in (-4.0, 1.0, 6.0):
        tray = cut(tray, bx(in_b - 1, L + 1, vy - 1.0, vy + 1.0, fz + 5.0, fz + 12.0),
                   cyl((in_b - 1, vy, fz + 5.0), (L + 1, vy, fz + 5.0), 1.0), cyl((in_b - 1, vy, fz + 12.0), (L + 1, vy, fz + 12.0), 1.0))
    # --- fourth screw boss (charger bay) and the solar lead slot in end wall B (flat 2-core cable lying flat)
    tray = uni(tray, cyl((POST_B[0], POST_B[1], F0), (POST_B[0], POST_B[1], zb), c['boss_d'] / 2 + 0.5))
    tray = cut(tray, bx(in_b - 1, L + 1, C['solar_y'] - 2.4, C['solar_y'] + 2.4, fz - 0.01, fz + 2.5))   # flat cable
    # --- screw holes + countersinks from below (all four)
    for sx, sy, _, _ in SCREWS:
        tray = cut(tray, cyl((sx, sy, -1), (sx, sy, zb + 1), 1.7),
                   cone((sx, sy, c['floor_z'] - 0.01), 3.1, (sx, sy, c['floor_z'] + 1.65), 1.45))
    out['Tray'] = [('Tray', tray)]

    # ================================================================ lid
    lid = rbox(0, L, -hw, hw, zl, c['top'], c['corner_r'])
    reg = cut(rbox(c['end_a'] + 0.2, in_b - 0.2, -iw + 0.2, iw - 0.2, zl - 1.4, zl + 0.01, c['corner_r'] - c['wall'] - 0.2),
              rbox(c['end_a'] + 1.6, in_b - 1.6, -iw + 1.6, iw - 1.6, zl - 2, zl + 1, max(c['corner_r'] - c['wall'] - 1.6, 0.3)))
    # no lip along end wall B: the capacitor's end and the USB-C board's top edge come up to within 1 mm of the lid there;
    # the lid locates on the other three sides and its four posts
    reg = cut(reg, bx(in_b - 2.0, in_b + 1, -iw - 1, iw + 1, zl - 2, zl))
    lid = uni(lid, reg)
    lid = cut(lid, bx(-1, L + 1, -gw, gw, gu, c['top'] + 1))
    lid = uni(lid, cut(bx(0, L, -gw, gw, gu, c['top']),
                       bx(-1, L + 1, -c['groove_hw'], c['groove_hw'], c['groove_floor'], c['top'] + 1)))
    # posts with inserts: three on the PCB's holes (they clamp it), one on the charger-bay boss
    def root(px, py, r, top, want=2.0):
        """A 45 deg root fillet (cone) where a post meets the lid, as big as the room to the wall / groove allows."""
        room = (gw - abs(py) - r) if top == gu else (iw - 0.6 - abs(py) - r)
        f = min(want, room)
        return cone((px, py, top - f), r, (px, py, top + 0.01), r + f) if f >= 0.6 else None

    pr = c['post_d'] / 2
    for (px, py), zbot in [(h, zt) for h in HOLES] + [(POST_B, zb)]:
        top = ceiling(py, pr)
        lid = uni(lid, cyl((px, py, zbot), (px, py, top + 0.01), pr))
        f = root(px, py, pr, top)
        if f:
            lid = uni(lid, f)
        lid = cut(lid, cyl((px, py, zbot - 0.01), (px, py, zbot + c['ins_depth']), c['ins_d'] / 2),
                  cone((px, py, zbot - 0.01), c['ins_d'] / 2 + 0.4, (px, py, zbot + 0.4), c['ins_d'] / 2),   # lead-in
                  cyl((px, py, zbot), (px, py, c['floor_z'] + c['screw_l'] + 0.8), 1.7))      # room past the insert
    # hold-downs: jacks, cell, charger module, capacitor, USB-C board's top edge; a stop over the ESP (0.5 clear)
    jtop = zt + c['rj_h']
    for xk in c['rj_x']:
        x, y = K(xk, 9.0)
        lid = uni(lid, bx(x - 2, x + 2, y - 2, y + 2, jtop + 0.05, ceiling(y, 2) + 0.01))
    btop = bc + c['bat_d'] / 2
    for fx in (C['bat_x0'] + 24, C['bat_x0'] + c['bat_l'] - 24):
        lid = uni(lid, bx(fx - 2.5, fx + 2.5, by - 3, by + 3, btop + 0.05, zl + 0.01))
    # charger: two pins clamp the module's edges where it has no pads (left edge between CN1 and GND, top edge
    # between PWR and the capacitor), mostly off the board; a pad 0.2 over the capacitor (it never bears on its legs)
    ctop = cz + c['chg_t']
    for fx, fy in ((gx0 + 21.5, gy0 - 0.3), (gx0 - 0.3, gy0 + 14.0)):
        tp = ceiling(fy, 1.6)
        lid = uni(lid, cyl((fx, fy, ctop + 0.05), (fx, fy, tp + 0.01), 1.6))
        f = root(fx, fy, 1.6, tp, 1.5)
        if f:
            lid = uni(lid, f)
    lid = uni(lid, bx(cap_x0 + 10, cap_x0 + 18, cap_y - 3, cap_y + 3, cap_z + c['cap_d'] / 2 + 0.2, zl + 0.01))
    lid = uni(lid, bx(C['usb_back'] + 2.0, C['usb_front'] - 3.0, yf + 0.1, yb - 0.1, zu1 + 0.05, zl + 0.01))
    ex, ey = K(c['esp_xc'] - 4.0, c['esp_y0'] + 4.0)
    lid = uni(lid, bx(ex - 2, ex + 2, ey - 2, ey + 2, C['esp_z0'] + c['esp_t'] + 0.5, zl + 0.01))
    out['Lid'] = [('Lid', lid)]

    # ================================================================ parts that are not in the PCB's 3D export
    P = []
    # RJ12 jacks (87180-066LF): body with the plug mouth, tails and pegs under the board
    for n, xk in enumerate(c['rj_x']):
        _, y = K(xk, 0)
        xf, xr = c['pcb_x'] + c['rj_front'], c['pcb_x'] + c['rj_back']
        j = bx(xf, xr, y - c['rj_w'] / 2, y + c['rj_w'] / 2, zt, zt + c['rj_h'])
        j = cut(j, bx(xf - 1, xf + 12, y - c['rj_mouth_w'] / 2, y + c['rj_mouth_w'] / 2, zt + c['rj_mouth'][0], zt + c['rj_mouth'][1]))
        P.append(('RJ12 %d jack' % (n + 1), j))
        P.append(('RJ12 %d tails' % (n + 1), bx(xr - 3.6, xr + 0.6, y - 3.8, y + 3.8, zb - c['rj_tail'], zb)))
        for s in (-1, 1):
            P.append(('RJ12 %d peg %d' % (n + 1, s), cyl((K(0, 8.43)[0], y + s * 5.08, zb - c['rj_peg']), (K(0, 8.43)[0], y + s * 5.08, zb), 1.5)))
    # 470 uF as bought (8 x 11.5 + 0.5 seal): the PCB export's model is a short generic one
    x9, y9 = K(32.75, 42.0)
    P.append(('C9 470uF', cyl((x9, y9, zt + 0.5), (x9, y9, zt + 12.0), 4.0)))
    # the three fuses, folded (see fuse_* above): legs up from their pads, bent over 1.6 below the body, disc flat
    fxc, _ = K(0, 23.55)                                  # between the staggered pads (y 22.6 / 24.5)
    hb = zt + c['fuse_leg'] - c['fuse_bend']              # height of the bend
    for n, jx in enumerate((11.0, 26.5, 42.0)):
        _, fyc = K(jx - 7.4 + 2.55, 0)
        legs = uni(bx(fxc - 0.4, fxc + 0.4, fyc - 2.95, fyc - 2.15, zt, hb + 0.4),
                   bx(fxc - 0.4, fxc + 0.4, fyc + 2.15, fyc + 2.95, zt, hb + 0.4),
                   bx(fxc - 0.4, fxc + c['fuse_bend'], fyc - 2.95, fyc + 2.95, hb - 0.4, hb + 0.4))
        disc = bx(fxc + c['fuse_bend'], fxc + c['fuse_bend'] + c['fuse_body'], fyc - c['fuse_w'] / 2, fyc + c['fuse_w'] / 2,
                  hb - c['fuse_t'] / 2, hb + c['fuse_t'] / 2)
        P.append(('F%d folded' % (n + 1), uni(legs, disc)))
    # ESP32-C6 SuperMini: header spacers, board, USB-C, buttons, chip, pin tips
    for xk in (4.5, 19.74):
        x0, y0 = K(xk - 1.27, 47.86)
        x1, y1 = K(xk + 1.27, 73.28)
        P.append(('ESP32-C6 spacer %.0f' % xk, bx(x0, x1, y0, y1, C['zt'] + c['sock_h'], C['esp_z0'])))
        P.append(('ESP32-C6 pin tips %.0f' % xk, bx(x0 + 0.3, x1 - 0.3, y0 + 0.95, y1 - 0.95, C['esp_z0'] + c['esp_t'], C['esp_z0'] + c['esp_t'] + c['esp_tip'])))
    ez0, ez1 = C['esp_z0'], C['esp_z0'] + c['esp_t']
    x0, y0 = K(c['esp_xc'] - c['esp_w'] / 2, c['esp_y0'])
    x1, y1 = K(c['esp_xc'] + c['esp_w'] / 2, c['esp_y0'] + c['esp_l'])
    P.append(('ESP32-C6 board', bx(x0, x1, y0, y1, ez0, ez1)))
    ux, uy = K(c['esp_xc'], c['esp_y0'] + c['esp_l'])
    P.append(('ESP32-C6 USB-C', bx(ux - 5.9, ux + 1.5, uy - 4.55, uy + 4.55, ez1, ez1 + 3.26)))
    for bxk, name in ((c['esp_xc'] + 3.4, 'BOOT'), (c['esp_xc'] - 5.0, 'RST')):
        bxx, byy = K(bxk, c['esp_y0'] + c['esp_l'] - 11.8)
        P.append(('ESP32-C6 %s' % name, bx(bxx - 2.0, bxx + 2.0, byy - 1.5, byy + 1.5, ez1, ez1 + 2.0)))
    chx, chy = K(c['esp_xc'], c['esp_y0'] + 11.0)
    P.append(('ESP32-C6 chip', bx(chx - 2.5, chx + 2.5, chy - 2.5, chy + 2.5, ez1, ez1 + 0.9)))
    # plugs: battery (J4, XH 2), charger harness (J5, XH 6), solar (J8, ZH 2), USB lead (J3 pins 1-2)
    for name, (xa, xb, ya, yb_) in (('J4 battery plug', (15.04, 22.46, 102.64, 108.41)),
                                    ('J5 charger plug', (0.54, 17.96, 111.14, 116.91))):
        x0, y0 = K(xa + 0.6, ya + 0.6)
        x1, y1 = K(xb - 0.6, yb_ - 0.6)
        P.append((name, bx(x0, x1, y0, y1, zt + 3.0, zt + 11.7)))
        P.append((name + ' wires', bx(x0 + 1, x1 - 1, y0 + 1, y1 - 1, zt + 11.7, zt + 13.3)))
    x0, y0 = K(22.75 - 2.25, 113.5 - 1.7)
    x1, y1 = K(22.75 + 2.25, 113.5 + 1.7)
    P.append(('J8 ZH header', bx(x0, x1, y0, y1, zt, zt + 6.0)))
    P.append(('J8 solar plug', bx(x0 + 0.4, x1 - 0.4, y0 + 0.4, y1 - 0.4, zt + 6.0, zt + 9.5)))
    x0, y0 = K(4.5 - 1.27, 122.5 - 1.27)
    x1, y1 = K(7.04 + 1.27, 122.5 + 1.27)
    P.append(('J3 USB lead plug', bx(x0, x1, y0, y1, zt + c['sock_h'], zt + c['sock_h'] + 2.5)))
    # 18650
    P.append(('18650', cyl((C['bat_x0'], by, bc), (C['bat_x0'] + c['bat_l'], by, bc), c['bat_d'] / 2)))
    # charger module: board, parts area, the big pads (rings), its capacitor and legs
    P.append(('Charger board', bx(gx0, gx1, gy0, gy1, cz, cz + c['chg_t'])))

    def M(xm, ym):
        """module (listing photo: x right, y down) -> box."""
        return gx0 + ym, gy0 + xm

    x0, y0 = M(6.0, 6.0)
    x1, y1 = M(28.0, 25.0)
    P.append(('Charger parts', bx(x0, x1, y0, y1, cz + c['chg_t'], cz + c['chg_t'] + 1.0)))
    for nm, (xm, ym) in (('PWR', (9.0, 3.3)), ('GND a', (4.3, 3.3)), ('BATT', (9.0, 26.5)), ('GND b', (4.3, 26.5)),
                         ('LOAD', (20.0, 26.5)), ('GND c', (24.7, 26.5))):
        px, py = M(xm, ym)
        P.append(('Charger pad %s' % nm, cyl((px, py, cz - 1.0), (px, py, cz + c['chg_t'] + 0.3), 2.0)))
    P.append(('Charger capacitor', cyl((cap_x0, cap_y, cap_z), (cap_x0 + c['cap_h'], cap_y, cap_z), c['cap_d'] / 2)))
    for xm, ym in c['cap_holes']:
        px, py = M(xm, ym)
        P.append(('Charger cap leg %.0f' % xm, uni(bx(px - 0.3, cap_x0 + 0.01, py - 0.3, py + 0.3, cap_z - 0.3, cap_z + 0.3),
                                                   bx(px - 0.3, px + 0.3, py - 0.3, py + 0.3, cz - 1.0, cap_z + 0.3))))
    # USB-C breakout on edge
    P.append(('USB-C board', bx(C['usb_back'], C['usb_front'], yf, yb, zu0, zu1)))
    hz0 = C['usb_zc'] - c['usb_sw'] / 2 + c['usb_sh'] / 2
    hz1 = C['usb_zc'] + c['usb_sw'] / 2 - c['usb_sh'] / 2
    sock = uni(bx(C['usb_front'] + c['usb_stick'] - c['usb_sl'], L, yf - c['usb_sh'], yf, hz0, hz1),
               cyl((C['usb_front'] + c['usb_stick'] - c['usb_sl'], c['usb_yc'], hz0), (L, c['usb_yc'], hz0), c['usb_sh'] / 2),
               cyl((C['usb_front'] + c['usb_stick'] - c['usb_sl'], c['usb_yc'], hz1), (L, c['usb_yc'], hz1), c['usb_sh'] / 2))
    P.append(('USB-C socket', sock))
    upx = C['usb_back'] + c['usb_pin_row']
    P.append(('USB-C header', bx(upx - 1.27, upx + 1.27, yb, yb + 2.5, C['usb_zc'] - 7.62, C['usb_zc'] + 7.62)))
    P.append(('USB-C pins', bx(upx - 0.32, upx + 0.32, yb + 2.5, yb + 8.5, C['usb_zc'] - 6.67, C['usb_zc'] + 6.67)))
    out['Parts'] = P

    # ================================================================ wires (render only)
    def wire(pts, r=0.8):
        body = None
        for a, b in zip(pts, pts[1:]):
            if math.dist(a, b) < 0.05:
                continue
            seg = cyl(a, b, r)
            body = seg if body is None else uni(body, seg)
        return body

    W = []
    jx, jy = K(9.25, 114.0)
    for nm, (xm, ym) in (('PWR', (9.0, 3.3)), ('BATT', (9.0, 26.5)), ('GND', (4.3, 3.3))):
        px, py = M(xm, ym)
        zz = zt + 12.5 + 1.7 * len(W)
        W.append(('Harness %s' % nm, wire([(jx, jy, zt + 12.5), (jx, jy, zz), (px, jy, zz), (px, py, zz), (px, py, cz + c['chg_t'])])))
    px, py = M(20.0, 26.5)                      # LOAD: under the capacitor, so soldered from underneath, run under the module
    W.append(('Harness LOAD', wire([(jx, jy, zt + 12.5), (jx, jy, zt + 17.6), (gx0 - 1.0, jy, zt + 17.6), (gx0 - 1.0, py, zt + 17.6),
                                    (gx0 - 1.0, py, fz + 1.4), (px, py, fz + 1.4), (px, py, cz + 0.5)])))
    bx4, by4 = K(18.75, 105.5)
    end = C['bat_x0'] + c['bat_l']
    W.append(('Battery lead', wire([(end, by, bc), (end + 3, by, bc), (end + 3, by4 + 6, bc), (bx4, by4 + 6, bc), (bx4, by4, zt + 12.5)])))
    sx8, sy8 = K(22.75, 113.5)
    W.append(('Solar lead', uni(bx(sx8 + 3, L + 10, C['solar_y'] - 1.0, C['solar_y'] + 1.0, fz + 0.5, fz + 4.5),
                                wire([(sx8 + 3, C['solar_y'], fz + 2.5), (sx8, sy8, fz + 2.5), (sx8, sy8, zt + 9.5)]))))
    jx3, jy3 = K(5.77, 122.5)
    W.append(('USB lead', wire([(upx, yb + 8.5, C['usb_zc']), (upx, C['solar_y'] - 2.2, C['usb_zc']),
                                (jx3 + 3, C['solar_y'] - 2.2, C['usb_zc']), (jx3, jy3, zt + c['sock_h'] + 2.5)], 0.7)))
    out['Wires'] = W
    return out


if __name__ == '__main__':
    print('Box %.1f x %.1f x %.1f mm (V4 was 126.1 long)' % (L, 2 * c['half_w'], c['top']))
    print('PCB underside Z %.2f, top %.2f; ESP underside %.2f, pin tips %.2f; groove underside %.2f' % (
        C['zb'], C['zt'], C['esp_z0'], C['esp_z0'] + c['esp_t'] + c['esp_tip'], C['g_under']))
    print('screws (from below):', ', '.join('(%.1f, %.1f) M3x%.0f' % (x, y, l) for x, y, _, l in SCREWS))
