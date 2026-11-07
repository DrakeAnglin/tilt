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
    capacitor's free end. The solar lead's floor
    route is on the room side of the bay.
  * USB-C breakout on edge, held by its edges: front edge in a pocket in end wall B (socket face flush), bottom edge in
    a floor U-channel, top edge in a lid U-channel whose closed back end keeps it from being pushed back.

Height budget (the reason the PCB sits 2 mm off the floor): ESP pins on its sockets reach 18.7 mm under a 19.2 mm groove.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v5.py --timeout 1800

Coordinates (mm): X along the rail from end A's outer face, Y across (-Y room side), Z up from the rail floor.
The PCB's KiCad coordinates (x across, y down from the jack edge) map to X = y + PCB_X, Y = x + PCB_Y.
"""

import math
import os

C = dict(
    room_out=-27.7, back_in=22.8, top=25.8, wall=2.0, floor_z=0.0, floor=1.2, lid=2.0, end_t=2.4, end_a=2.0, corner_r=4.0, edge_r=1.5,
    rail_w=55.5, rail_h=36.5, rail_wall=2.0, lip_in=4.5, lip_h=3.0, rod_z=24.0, rod=4.0,
    # height: with the three fuses folded, the tallest part outside the groove is the charger's capacitor lying on its
    # module (top 23.3), so the lid's underside is at 23.8 and its top at 25.8 (was 33.3 with the fuses upright)
    # PTC fuses (Bel 0ZRE0075FF, datasheet: A 11.5 wide, B 23.4 seated, E 4.8 thick, C 5.1 / F 1.9 lead offset): an
    # 11.5 disc on ~11.9 mm legs (KiCad's model; B - A). Each is folded toward the ESP, legs bent 1.6 below the body,
    # so the disc lies flat over its own four resistors
    fuse_leg=11.9, fuse_bend=1.6, fuse_w=11.5, fuse_t=4.8, fuse_body=11.5,
    # width: the room-side wall stays put (the PCB is 0.7 off it); the back wall comes in to 0.4 past the PCB's 47 mm jack
    # strip (the widest thing in the box) and 0.3 past the H2 screw post, so the box no longer fills the rail: two rounded
    # bumpers on the back wall stop 1.0 short of the rail's wall - an easy fit that still keeps the rod off the groove's
    # sides (1.9 clear each side)
    bumper_x=(30.0, 135.0), bumper_w=2.4, bumper_gap=1.0, bumper_h=6.0,   # low: wires can run along the rail above them
    # rod groove: a circle, r 5, its center 1.67 above the rod's axis: the 4 mm square rod's corners (sweep r 2.83) clear
    # it by 0.5 at the bottom and ~1.9 each side at the axis. The channel under it is 2.0 thick, like the lid
    groove_r=5.0, groove_floor=24.0 - 2.0 * math.sqrt(2) - 0.5, groove_t=2.0,   # print 2: as thick as the lid (was 1.0)
    # PCB: 2.4 mm above the floor (print 1: was 1.7; raised so the RJ12 tails clear a full 1.2 floor), which is recessed 0.4 under the PCB (2.1 mm for its leads: the XH headers' tails
    # reach 1.8 below), board 1.52 (as exported)
    pcb_gap=2.4, floor_recess=0.0, pcb_t=1.52, pcb_x=1.8, pcb_y=-25.0, pcb_len=125.0, pcb_bar=47.0, pcb_body=27.0,
    holes=((3.5, 41.0), (43.5, 43.3), (23.8, 121.5)),            # H1, H2, H3 (KiCad x, y)
    boss_d=8.0, post_d=8.0, ins_d=4.0, ins_depth=6.7, screw_l=10.0,            # M3 x 5.7 heat-set inserts, Ø4.0 hole
    # RJ12 Amphenol 87180-066LF (drawing 87180 sheet 1-3): 13.2 W x 11.5 H, front face 0.55 behind the board edge
    rj_w=13.25, rj_h=11.5,   # measured on the real jack (2026-11-07): 13.25 W x 11.5 H (drawing: 13.2)
    rj_front=0.55, rj_back=17.32, rj_x=(7.825, 23.325, 38.825), rj_mouth_w=9.65,
    rj_mouth=(1.73, 8.50),          # the jack's plug opening, above the board (87180 drawing); latch tab-down
    # end wall A (rev M): the PCB's jack edge is trimmed 3-4 mm (by hand, so anywhere in that range) and the jacks come
    # forward through the wall: their front faces sit jack_recess behind the outer face, each in an opening that is the
    # jack's own outline + jack_clear (the jack fills it: no recess, no view into the box). The board is located by its
    # three screws, not its trimmed edge, so the cut's accuracy doesn't matter; the edge ends up 0.75-1.75 off the wall.
    # (print 2's plug-shaped openings, from the measured plug 9.55 x 6.55 with a 6.0 x 1.5 latch, are gone)
    # clearances: 0.3 a side (FDM prints holes ~0.1-0.2 small), 0.35 on top (the opening's top is a bridge: it sags a
    # little), 0.1 under (the jack sits on the board, which the screws locate)
    pcb_trim=(3.0, 4.0), jack_recess=0.3, jack_clear=0.3, jack_clear_top=0.35, jack_clear_bot=0.1, ap_r=0.6,
    rj_tail=2.1, rj_peg=1.9,
    # ESP32-C6 SuperMini (26 x 18) on 8.5 mm sockets + 2.5 mm header spacers, USB toward end B
    esp_l=26.0, esp_w=18.0, esp_t=1.0, esp_xc=12.12, esp_y0=47.57, sock_h=8.59, spacer=2.5, esp_tip=1.9,
    # 18650 (protected, JST-XH lead) along the back wall
    bat_d=19.0, bat_l=65.7,                      # measured (print 1)
    bat_gap=0.4, stop_t=2.5, stop_hw=5.0,        # end plates: 0.4 play each end, 2.5 thick, 10 wide (print 1: too loose, too thin)
    # cell cradles (tray saddles + matching lid cradles): 6 wide, never thinner than 1.5; the PCB-side face 0.6 off the
    # PCB's edge, so on that side each horn stops where its wall is still 1.5 thick; on the back side they run to the wall
    cradle_w=6.0, cradle_t=1.5, cradle_y0=2.6, cradle_lid_y0=4.6, cradle_at=(9.0, 54.0),   # lid cradles start clear of the lead's channel
    # charger module (DIYMORE MCP73871, 31.5 x 30.5) and its capacitor (16 x 26)
    # module photo x (31.5) runs across the box (+Y), photo y (30.5) along it (+X): its capacitor corner ends up at the
    # back wall, its PWR / BATT pads on the groove side
    # print 1: the module's two sides were swapped (30.5 runs across the box, 31.5 along it); its seats are now a
    # press fit (0 nominal: FDM prints the gaps a little tight, so it pushes in and stays)
    chg_w=30.5, chg_d=31.5, chg_t=1.6, chg_gap=2.4, chg_fit=0.0,   # 2.4 under the module: the LOAD wire (1.6) runs there
    cap_d=16.0, cap_h=26.0, cap_holes=((19.0, 5.5), (26.0, 5.5)), cap_up=2.1, cap_end=1.5,   # 2.1 over the module: the NTC wires run under it
    # NTC: the module's THERM resistor (the '103' beside the THERM label, ~x 23.3 y 15.8 in the listing photo) comes off;
    # two 30 AWG wires from its pads run out under the capacitor to a 10 k NTC taped on the cell's top near its end B
    therm_xy=(23.3, 15.8), ntc_on_cell=4.0,
    # USB-C breakout (Cermant, 22.1 x 13.05, socket 9.1 x 3.26 x 7.35 sticking out 1.45), on edge, socket face flush
    usb_w=22.1, usb_d=13.05, usb_t=1.6, usb_sw=9.1, usb_sh=3.26, usb_sl=7.35, usb_stick=1.45, usb_yc=-21.2,
    usb_z0=1.25, usb_pin_row=1.04,      # print 2: stands on the floor (0.05 over it) in a floor U-channel; no floor groove
)
c = C
C['iw_lo'] = c['room_out'] + c['wall']                  # room-side inner face
C['iw_hi'] = c['back_in']                              # back inner face
C['out_hi'] = c['back_in'] + c['wall']
C['g_zc'] = c['groove_floor'] + c['groove_r']          # groove's round top: center height
C['groove_top_hw'] = math.sqrt(c['groove_r'] ** 2 - (C['g_zc'] - c['top']) ** 2) if c['top'] < C['g_zc'] else c['groove_r']
C['fz'] = c['floor_z'] + c['floor']
C['zl'] = c['top'] - c['lid']
C['zb'] = C['fz'] + c['pcb_gap']                     # PCB underside
C['zt'] = C['zb'] + c['pcb_t']                       # PCB top
C['pcb_end'] = c['pcb_x'] + c['pcb_len']
C['chg_y0'] = C['iw_hi'] - c['chg_fit'] - c['chg_w']   # module against the back wall (press fit)
C['chg_x0'] = C['pcb_end'] + 2.0                       # charger bay: room for its corner seat between it and the PCB
C['bat_x0'] = c['pcb_x'] + c['pcb_bar'] + 0.3 + c['stop_t'] + c['bat_gap']   # end-A plate starts clear of the H2 post
C['in_b'] = C['chg_x0'] + c['cap_holes'][0][1] + c['cap_end'] + c['cap_h'] + 0.4    # end wall B inner face: past the capacitor
C['L'] = C['in_b'] + c['end_t']
C['a0'] = c['pcb_x'] + c['rj_front'] - c['jack_recess']     # end wall A's outer face (the box starts here, not at X 0)
C['ia'] = C['a0'] + c['end_a']                             # end wall A's inner face
C['box_l'] = C['L'] - C['a0']
C['bat_y'] = C['iw_hi'] - 0.3 - c['bat_d'] / 2        # against the back wall: leaves a channel for the cell's lead along its PCB-side shoulder
C['bat_zc'] = C['fz'] + 0.5 + c['bat_d'] / 2
C['esp_z0'] = C['zt'] + c['sock_h'] + c['spacer']    # ESP underside
# USB-C breakout on edge: component face toward the room-side wall, socket face flush with end B's outer face
C['usb_front'] = C['L'] - c['usb_stick']
C['usb_back'] = C['usb_front'] - c['usb_d']
C['usb_yf'] = c['usb_yc'] + c['usb_sh'] / 2          # board's component face
C['usb_zc'] = c['usb_z0'] + c['usb_w'] / 2
C['solar_y'] = -13.4
L = C['L']


def z_under(y, off):
    """Lower edge of the groove (off 0) or of the channel under it (off = groove_t) at |y|; inf outside it."""
    R, y = c['groove_r'] + off, abs(y)
    if y > R:
        return float('inf')
    return C['g_zc'] - math.sqrt(R * R - y * y)


def K(x, y):
    """KiCad (x, y) on the PCB -> box (X, Y)."""
    return y + c['pcb_x'], x + c['pcb_y']


HOLES = [K(*h) for h in c['holes']]
# print 2: the fourth screw (a post in the charger bay, room side) is gone: wires crowd there and it was 24 mm from H3
SCREWS = [(x, y, C['zb'], c['screw_l']) for x, y in HOLES]   # (x, y, boss top, length): one size, M3 x 10


def build(tbm, bx, cyl, cone, uni, cut, rbox, obox):
    """{group: [(name, body)]}. rbox(x0, x1, y0, y1, z0, z1, r) = box with its four vertical edges rounded;
    obox(center, u, w, L, W, H) = box along unit vectors u, w."""
    ilo, ihi, fz, zl, zb, zt = C['iw_lo'], C['iw_hi'], C['fz'], C['zl'], C['zb'], C['zt']
    olo, ohi = c['room_out'], C['out_hi']
    in_b = C['in_b']
    out = {}

    def groove(off, x0, x1):
        """The groove (off 0), or its outline grown by off: a circle, open above its center."""
        R, zc = c['groove_r'] + off, C['g_zc']
        return uni(cyl((x0, 0, zc), (x1, 0, zc), R), bx(x0, x1, -R, R, zc, zc + 20))

    def ceiling(y, half=0.0):
        """Lid features run up to the lid's underside; under the groove they are trimmed by the final groove cut."""
        return zl

    # ================================================================ tray
    F0 = c['floor_z'] + 0.3                              # floor-standing features start inside the floor
    a0, ia = C['a0'], C['ia']
    tray = cut(rbox(a0, L, olo, ohi, c['floor_z'], zl, c['corner_r']),
               rbox(ia, in_b, ilo, ihi, fz, zl + 1, c['corner_r'] - c['wall']))
    # rail bumpers on the back wall: rounded vertical fins out to 1.0 short of the rail's wall
    ry = c['rail_w'] / 2 - c['bumper_gap'] - c['bumper_w'] / 2
    for bxx in c['bumper_x']:
        tray = uni(tray, bx(bxx - c['bumper_w'] / 2, bxx + c['bumper_w'] / 2, ohi - 0.5, ry, c['floor_z'], c['bumper_h']),
                   cyl((bxx, ry, c['floor_z']), (bxx, ry, c['bumper_h']), c['bumper_w'] / 2))
    # reliefs in end A's inner corner fillets for the PCB's corners (the board sits 0.2 off end wall A)
    tray = cut(tray, bx(ia - 0.01, ia + 2.2, ilo - 0.01, ilo + 2.2, zb - 0.3, zt + 0.3))
    tray = cut(tray, bx(ia - 0.01, ia + 2.2, ihi - 2.2, ihi + 0.01, zb - 0.3, zt + 0.3))   # and the back one
    for xa, xb in ((a0 - 1, ia + 0.01), (in_b - 0.01, L + 1)):        # the lid's groove channel crosses both ends
        tray = cut(tray, groove(c['groove_t'] + 0.05, xa, xb))   # print 2: 0.05 round the channel (was 0.15, a visible gap)
    # --- floor recessed 0.4 under the PCB's outline (+0.2): room for its leads without raising the ESP
    fr = fz - c['floor_recess']
    bar_x1, _ = K(0, c['pcb_bar'])
    # (+0.2, not +0.5: the 8 mm bosses reach 0.5 (H2: 0.7) past the board, so at +0.5 they only touched the recess wall along a
    # line, which made the STL non-manifold. At +0.2 they all overlap it and merge)
    if c['floor_recess'] > 0:   # (print 1: none now - the raised PCB's header tails clear the full floor)
        tray = cut(tray, bx(ia - 0.01, bar_x1 + 0.2, ilo - 0.01, min(K(c['pcb_bar'], 0)[1] + 0.2, ihi + 0.01), fr, fz + 0.01),
                   bx(bar_x1 - 0.01, C['pcb_end'] + 0.2, ilo - 0.01, K(c['pcb_body'], 0)[1] + 0.2, fr, fz + 0.01))
    # --- PCB nest: it drops in and is located before the lid goes on: lengthwise by its three screws and the jacks in
    # their openings (rev M: its trimmed edge stays 0.75-1.75 off end wall A), across by the room-side wall (0.7) and
    # free-standing ribs along the bar's and the body's back edges (0.2); all below the board's top face
    # the ribs' tops are level with the cell cradles' PCB-side horns (they run through them)
    _rc = c['bat_d'] / 2 + 0.2
    ztop = C['bat_zc'] - math.sqrt(_rc * _rc - (C['bat_y'] - c['cradle_y0'] - c['cradle_t']) ** 2)
    by_bar, by_body = K(c['pcb_bar'], 0)[1], K(c['pcb_body'], 0)[1]
    for x0, x1, y0 in ((58.0, 72.0, by_body), (100.0, 114.0, by_body)):       # (the back wall now locates the bar's edge)
        tray = uni(tray, bx(x0, x1, y0 + 0.2, y0 + 1.4, F0, ztop))
    # --- PCB: three bosses under its holes; through holes with countersinks from below (screws come up)
    for hx, hy in HOLES:
        tray = uni(tray, cyl((hx, hy, F0), (hx, hy, zb), c['boss_d'] / 2))
    # --- jacks: plug-shaped apertures in end wall A, pockets under their tails and pegs, port marks (1, 2, 3 dots)
    def aperture(y, grow, xa, xb):
        """rev M: the jack's own front outline (13.2 x 11.5 on the PCB) + jack_clear a side and on top, jack_clear_bot
        under it; corners r ap_r (small enough to clear the jack's square corners). The jack comes through it."""
        w, r = c['rj_w'] / 2 + c['jack_clear'] + grow, c['ap_r'] + grow
        z0, z1 = zt - c['jack_clear_bot'] - grow, zt + c['rj_h'] + c['jack_clear_top'] + grow
        a = uni(bx(xa, xb, y - w + r, y + w - r, z0, z1), bx(xa, xb, y - w, y + w, z0 + r, z1 - r))
        for yy in (y - w + r, y + w - r):
            for zz in (z0 + r, z1 - r):
                a = uni(a, cyl((xa, yy, zz), (xb, yy, zz), r))
        return a

    for n, xk in enumerate(c['rj_x']):
        _, y = K(xk, 0)
        tray = cut(tray, aperture(y, 0.0, a0 - 1, ia + 0.01))   # the jack comes through it; no bezel (0.4 nozzle)
        x0, _ = K(0, 7.0)
        x1, _ = K(0, c['rj_back'] + 1.0)
        # (print 1: no pocket in the floor under the jack any more: the PCB is 0.7 higher, so its tails clear the full floor)
        for k in range(n + 1):
            dy = (k - n / 2.0) * 2.4
            tray = cut(tray, cyl((a0 - 1, y + dy, 2.6), (a0 + 0.5, y + dy, 2.6), 0.6))
    # --- 18650: two saddles and two end stops (the end-B stop is low: the lead leaves that end)
    by, bc = C['bat_y'], C['bat_zc']
    rc = c['bat_d'] / 2 + 0.2                                   # cradle bore
    ytrim = c['cradle_y0'] + c['cradle_t']                      # PCB-side horn: where its wall is cradle_t thick
    chz = math.sqrt(rc * rc - (by - ytrim) ** 2)                # bore's height above / below the axis there
    for sx in (C['bat_x0'] + a for a in c['cradle_at']):
        sad = cut(bx(sx, sx + c['cradle_w'], c['cradle_y0'], ihi + 0.5, F0, bc - 0.5),          # back horn into the wall
                  cyl((sx - 1, by, bc), (sx + c['cradle_w'] + 1, by, bc), rc),
                  bx(sx - 1, sx + c['cradle_w'] + 1, c['cradle_y0'] - 1, ytrim, bc - chz, bc + 1))   # PCB-side horn, flat top
        tray = uni(tray, sad)
    # end stops, centered on the cell's axis; they bear on its end below the + button (the lead leaves the end-B end higher up)
    g, t, hw = c['bat_gap'], c['stop_t'], c['stop_hw']
    tray = uni(tray, bx(C['bat_x0'] - g - t, C['bat_x0'] - g, by - hw, min(by + hw, ihi + 0.01), F0, bc - 2.5),
               bx(C['bat_x0'] + c['bat_l'] + g, C['bat_x0'] + c['bat_l'] + g + t, by - hw, min(by + hw, ihi + 0.01), F0, bc - 4.0))
    # --- charger subassembly: four one-piece corner seats. Each is a 2 x 2 ledge under the board's corner (clear of the
    # pads' solder) joined to an L of 1.2 mm walls round the corner, 0.2 clear of the board and 1 mm above its top. On
    # the back-wall side there is no wall leg (the tray wall is 0.3 away and locates it); the ledge runs into the wall.
    gx0, gx1, gy0 = C['chg_x0'], C['chg_x0'] + c['chg_d'], C['chg_y0']
    gy1 = gy0 + c['chg_w']
    cz = fz + c['chg_gap']
    gtop = cz + c['chg_t'] + 1.0
    for px, py in ((gx0, gy0), (gx1, gy0), (gx0, gy1)):       # (the 4th corner is the capacitor's saddle, below)
        sx, sy = (1 if px == gx0 else -1), (1 if py == gy0 else -1)
        wall_side = py == gy1                                  # back wall within 0.3
        f = c['chg_fit']
        yo = (ihi + 0.01) if wall_side else py - sy * (f + 1.2)  # outer edge of the seat across the box
        seat = bx(px - sx * (f + 1.2), px + sx * 2.0, yo, py + sy * 2.0, F0, cz)                    # ledge
        seat = uni(seat, bx(px - sx * (f + 1.2), px - sx * f, yo, py + sy * 5.0, F0, gtop))          # leg along the end
        if not wall_side:
            seat = uni(seat, bx(px - sx * (f + 1.2), px + sx * 5.0, py - sy * (f + 1.2), py - sy * f, F0, gtop))   # leg along the side
        tray = uni(tray, seat)
    cap_y = gy0 + (c['cap_holes'][0][0] + c['cap_holes'][1][0]) / 2
    cap_x0 = gx0 + c['cap_holes'][0][1] + c['cap_end']
    cap_z = cz + c['chg_t'] + c['cap_up'] + c['cap_d'] / 2
    # the capacitor's saddle: one block from the module's end to end wall B and into the back wall, bored for the
    # capacitor (0.3 clear); its face 0.2 off the module's end locates the module, and its ledge carries the module's
    # corner. Like the cell cradles, its room-side horn stops flat where the wall is still 1.5 thick.
    cr = c['cap_d'] / 2 + 0.3
    cy0 = cap_y - 6.5
    cyt = cy0 + 1.5
    chz_c = math.sqrt(cr * cr - (cap_y - cyt) ** 2)
    sad = cut(bx(gx1 + c['chg_fit'], in_b + 0.01, cy0, ihi + 0.01, F0, cap_z - 0.5),
              cyl((gx1, cap_y, cap_z), (in_b + 1, cap_y, cap_z), cr),
              bx(gx1, in_b + 1, cy0 - 1, cyt, cap_z - chz_c, cap_z + 1))
    sad = uni(sad, bx(gx1 - 2.0, gx1 + 0.3, gy1 - 2.0, ihi + 0.01, F0, cz))                        # corner ledge
    tray = uni(tray, sad)
    # print 1: the capacitor's bore runs right through to the back wall (into its face where the can reaches it), so
    # nothing stands between the can and the wall
    tray = cut(tray, cyl((cap_x0 - 0.3, cap_y, cap_z), (in_b - 0.01, cap_y, cap_z), cr))
    # --- USB-C breakout, print 2: held by its edges only, never on its faces (the header's solder joints and parts are
    # there). A U-channel on the floor takes the bottom edge, a U-channel on the lid the top edge; the front edge sits in
    # a pocket in end wall B with the socket in a closed stadium window. No tall stop behind the board: a low lip at the
    # floor channel's back end snaps it in, and the lid channel's closed back end comes down behind its back edge
    yf, yb = C['usb_yf'], C['usb_yf'] + c['usb_t']
    zu0, zu1 = c['usb_z0'], c['usb_z0'] + c['usb_w']
    sc = 0.25
    wr = c['usb_sh'] / 2 + 0.2
    hz = c['usb_sw'] / 2 - c['usb_sh'] / 2
    zc = C['usb_zc']
    xs = C['usb_back']
    # print 2b: the channel's back end is 0.15 behind the board's back edge and as tall as its sides (2.5); its top edge
    # on the board's side is rounded (r 0.8) so the board's corner rolls over it and snaps in: socket into the window
    # first, back end tipped up, then pushed down
    xu0, ru = xs - 0.15, 0.8
    tray = uni(tray, cut(bx(xu0 - 1.2, in_b + 0.01, yf - sc - 1.2, yb + sc + 1.2, F0, fz + 2.5),
                         bx(xu0, in_b + 1, yf - sc, yb + sc, fz, fz + 3),
                         bx(xu0 - ru, xu0 + 0.01, yf - sc, yb + sc, fz + 2.5 - ru, fz + 3)),
               cyl((xu0 - ru, yf - sc - 0.01, fz + 2.5 - ru), (xu0 - ru, yb + sc + 0.01, fz + 2.5 - ru), ru))
    tray = cut(tray, bx(xu0 - 3.0, xu0 - 1.2, yf - sc - 0.05, yb + sc + 0.05, fz + 0.01, fz + 2.6))   # the round's back half off
    # pocket for the front edge, open at the top (closed it left a 0.25 sliver under the rim); over the window it spans the window's width (no slivers), the wall's outer 1.25 skin intact
    tray = cut(tray, bx(in_b - 0.01, C['usb_front'] + 0.2, yf - sc, yb + sc, fz, zl + 0.01),
               bx(in_b - 0.01, C['usb_front'] + 0.2, c['usb_yc'] - wr, yf - sc + 0.01, zc - hz - wr, zl + 0.01))
    tray = cut(tray, bx(in_b - 1, L + 1, c['usb_yc'] - wr, c['usb_yc'] + wr, zc - hz, zc + hz),
               cyl((in_b - 1, c['usb_yc'], zc - hz), (L + 1, c['usb_yc'], zc - hz), wr),
               cyl((in_b - 1, c['usb_yc'], zc + hz), (L + 1, c['usb_yc'], zc + hz), wr))
    # --- charger vents: four slots in end wall B above the module (the floor sits on the rail, so not there)
    # 2 mm slots on a 3.5 mm pitch (1.5 mm webs), tops 5 mm below the groove notch in the wall
    for vy in (-1.0, 2.5, 6.0):    # print 1: the -4 slot was behind the module's corner seat (Y up to -2.7); above 6 the capacitor's end face is behind it
        tray = cut(tray, bx(in_b - 0.01, L + 1, vy - 1.0, vy + 1.0, fz + 5.0, fz + 12.0),          # through the wall only
                   cyl((in_b - 0.01, vy, fz + 5.0), (L + 1, vy, fz + 5.0), 1.0), cyl((in_b - 0.01, vy, fz + 12.0), (L + 1, vy, fz + 12.0), 1.0))
    # --- the solar lead slot in end wall B (flat 2-core cable lying flat)
    tray = cut(tray, bx(in_b - 1, L + 1, C['solar_y'] - 2.4, C['solar_y'] + 2.4, fz - 0.01, fz + 2.5))   # flat cable
    # --- screw holes + countersinks from below (all three)
    for sx, sy, _, _ in SCREWS:
        tray = cut(tray, cyl((sx, sy, -1), (sx, sy, zb + 1), 1.7),
                   cone((sx, sy, c['floor_z'] - 0.01), 3.1, (sx, sy, c['floor_z'] + 1.65), 1.45))
    out['Tray'] = [('Tray', tray)]

    # ================================================================ lid
    lid = rbox(C['a0'], L, olo, ohi, zl, c['top'], c['corner_r'])
    reg = cut(rbox(C['ia'] + 0.2, in_b - 0.2, ilo + 0.2, ihi - 0.2, zl - 1.4, zl + 0.01, c['corner_r'] - c['wall'] - 0.2),
              rbox(C['ia'] + 1.6, in_b - 1.6, ilo + 1.6, ihi - 1.6, zl - 2, zl + 1, max(c['corner_r'] - c['wall'] - 1.6, 0.3)))
    # no lip along end wall B: the capacitor's end and the USB-C board's top edge come up to within 1 mm of the lid there;
    # the lid locates on the other three sides and its three posts
    reg = cut(reg, bx(in_b - 2.0, in_b + 1, ilo - 1, ihi + 1, zl - 2, zl))
    lid = uni(lid, reg)
    # the channel under the groove (the groove itself is cut last, so it also trims every feature that reaches it)
    lid = uni(lid, cut(groove(c['groove_t'], C['a0'], L), bx(C['a0'] - 1, L + 1, -20, 20, c['top'], c['top'] + 30)))
    # posts with inserts: three on the PCB's holes (they clamp it)
    def root(px, py, r, top, want=2.0):
        """A 45 deg root fillet (cone) where a post meets the lid, as big as the room to the wall / groove allows."""
        if z_under(abs(py) + r + want, c['groove_t']) < zl + 0.5:      # under the groove's channel: it merges into it
            return None
        room = (ihi if py > 0 else -ilo) - 0.6 - abs(py) - r
        f = min(want, room)
        return cone((px, py, top - f), r, (px, py, top + 0.01), r + f) if f >= 0.6 else None

    pr = c['post_d'] / 2
    for (px, py), zbot in [(h, zt) for h in HOLES]:
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
    # cell: two cradles matching the tray's saddles (same X, same width, same bore, the same 1.5 trim on the PCB side),
    # coming down to the cell's axis on the back side, 0.2 off the back wall
    for sx in (C['bat_x0'] + a for a in c['cradle_at']):
        ylt = c['cradle_lid_y0'] + c['cradle_t']
        lhz = math.sqrt(rc * rc - (by - ylt) ** 2)
        lid = uni(lid, cut(bx(sx, sx + c['cradle_w'], c['cradle_lid_y0'], ihi - 0.2, bc + 0.5, zl + 0.01),
                           cyl((sx - 1, by, bc), (sx + c['cradle_w'] + 1, by, bc), rc),
                           bx(sx - 1, sx + c['cradle_w'] + 1, c['cradle_lid_y0'] - 1, ylt, bc - 1, bc + lhz)))
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
    # USB-C board, print 2: a U-channel over its top edge, 2 deep, from its back edge to 1 short of the wall, with a
    # closed back end 2.5 thick behind the board's back edge that comes down to the socket's top (the plug pushes
    # there); it stays on the component side of the header, which overhangs the edge by 0.23
    yf, yb, sc = C['usb_yf'], C['usb_yf'] + c['usb_t'], 0.25
    zu1 = c['usb_z0'] + c['usb_w']
    xs = C['usb_back']
    ztop_sock = C['usb_zc'] + c['usb_sw'] / 2
    lid = uni(lid, cut(bx(xs - 0.25, C['usb_front'] - 1.0, yf - sc - 1.2, yb + sc + 1.2, zu1 - 2.0, zl + 0.01),
                       bx(xs - 1, C['usb_front'], yf - sc, yb + sc, zu1 - 3.0, zu1 + 0.15)),
                   bx(xs - 2.75, xs - 0.25, yf - sc - 1.2, yb, ztop_sock - 0.5, zl + 0.01))
    ex, ey = K(c['esp_xc'] - 4.0, c['esp_y0'] + 4.0)
    lid = uni(lid, bx(ex - 2, ex + 2, ey - 2, ey + 2, C['esp_z0'] + c['esp_t'] + 0.5, zl + 0.01))
    lid = cut(lid, groove(0, -1, L + 1))
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
    P.append(('NTC on the cell', cyl((C['bat_x0'] + c['bat_l'] - c['ntc_on_cell'] - 1.2, C['bat_y'], C['bat_zc'] + c['bat_d'] / 2 + 1.0),
                                     (C['bat_x0'] + c['bat_l'] - c['ntc_on_cell'] + 1.2, C['bat_y'], C['bat_zc'] + c['bat_d'] / 2 + 1.0), 1.0)))
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
    P.append(('USB-C pins', bx(upx - 0.32, upx + 0.32, yb + 2.5, yb + 5.5, C['usb_zc'] - 6.67, C['usb_zc'] + 6.67)))
    out['Parts'] = P

    # ================================================================ wires, routed as built (checked like parts)
    # 22 AWG silicone (1.6 OD) for the charger harness and the USB lead; the cell's own lead (assumed 22 AWG); the solar
    # cable is the white flat 2-core 22 AWG (two 2.0 cores side by side). Every route keeps clear of the lid, the groove's
    # channel, the screw posts and the other wires; ends stop on the plug tops / pads they go into.
    def wire(pts, r=0.8):
        body = None
        for a_, b_ in zip(pts, pts[1:]):
            if math.dist(a_, b_) < 0.05:
                continue
            seg = cyl(a_, b_, r)
            body = seg if body is None else uni(body, seg)
        return body

    def length(pts):
        return sum(math.dist(a_, b_) for a_, b_ in zip(pts, pts[1:]))

    PLUG = zt + 11.7 + 0.05                           # top of the XH plugs (J4, J5)
    jx5 = K(0, 113.5)[0]                              # J5 pins: y 113.5, x 3 + 2.5 k (pin 1 = GND ... pin 6 = PWR)
    j5 = {n: K(3.0 + 2.5 * (n - 1), 0)[1] for n in range(1, 7)}
    pad = {nm: M(*xy) for nm, xy in (('PWR', (9.0, 3.3)), ('GND', (4.3, 3.3)), ('BATT', (9.0, 26.5)), ('LOAD', (20.0, 26.5)))}
    ptop = cz + c['chg_t'] + 0.35
    R = {}
    # charger harness: each wire on its own level where they cross (PWR and BATT 17.0, LOAD 18.7, GND 20.4)
    px_, py_ = pad['PWR']
    R['Harness PWR (J5-6)'] = [(jx5, j5[6], PLUG), (jx5, j5[6], 17.7), (127.9, -6.6, 17.7), (px_, py_ - 1.5, 17.7),
                               (px_, py_, 17.7), (px_, py_, ptop)]
    px_, py_ = pad['BATT']
    R['Harness BATT (J5-2)'] = [(jx5, j5[2], PLUG), (jx5, j5[2], 17.7), (128.0, -13.5, 17.7), (150.0, -3.0, 17.7),
                                (px_, py_, 17.7), (px_, py_, ptop)]
    px_, py_ = pad['LOAD']                            # under the capacitor: in from below, run under the module
    R['Harness LOAD (J5-4)'] = [(jx5, j5[4], PLUG), (jx5, j5[4], 19.4), (144.0, -10.2, 19.4), (144.0, -10.2, fz + 0.8),
                                (147.0, -7.5, fz + 0.8), (147.0, py_, fz + 0.8), (px_ - 1.8, py_, fz + 0.8),
                                (px_, py_, cz - 1.05)]
    px_, py_ = pad['GND']
    R['Harness GND (J5-1)'] = [(jx5, j5[1], PLUG), (jx5, j5[1], 21.1), (130.0, -9.0, 21.1), (px_, -7.6, 21.1),
                               (px_, py_ - 1.0, 17.0), (px_, py_, 16.0), (px_, py_, ptop)]   # drops before the groove's (2.0) channel
    # cell lead (both wires out of the cell's end-B face): down the end face's PCB side, past the H3 post's back, along the
    # channel between the cell's PCB-side shoulder and the PCB's back edge (the two wires one above the other), into J4
    ce = C['bat_x0'] + c['bat_l'] + 0.05
    j4x, j4a = K(0, 105.0)[0], K(17.5, 0)[1]
    j4b = K(20.0, 0)[1]
    R['Cell lead -'] = [(ce + 0.85, by - 0.9, bc - 0.5), (ce + 2.0, by - 0.9, bc - 0.5), (ce + 0.9, 6.0, 14.4),
                        (ce + 0.9, 2.7, 16.2), (118.6, 2.7, 16.2), (110.0, 2.7, 16.2), (104.0, -1.5, 16.2),
                        (104.0, j4a, 17.7), (j4x, j4a, 17.7), (j4x, j4a, PLUG)]
    R['Cell lead +'] = [(ce + 0.85, by + 0.9, bc + 0.5), (ce + 2.0, by + 0.9, bc + 0.5), (ce + 0.9, 6.0, 16.6),
                        (ce + 0.9, 2.7, 18.1), (118.6, 2.7, 18.1), (110.0, 2.7, 18.1), (108.4, -0.8, 17.6),
                        (j4x, j4b, 17.6), (j4x, j4b, PLUG)]          # under the groove's 2.0 channel
    # USB lead: soldered to the USB-C board's VBUS / GND pins (here the two lowest), low along the room side, behind the
    # bay's screw post, along the room-side wall, up into the 2-pin plug on J3 pins 1-2
    j3x = K(0, 122.5)[0]
    j3p = zt + c['sock_h'] + 2.5 + 0.05
    zv, zg = C['usb_zc'] - 6.35, C['usb_zc'] - 3.81
    zvr = max(zv, zt + 1.1)                            # VBUS's run clears the (raised) PCB
    R['USB lead VBUS'] = [(upx, yb + 5.55, zv), (upx - 1.2, -13.2, zvr), (130.8, -13.2, zvr), (130.8, -22.6, zvr),
                          (j3x, -22.6, zvr), (j3x, -22.6, 17.1), (j3x, K(4.5, 0)[1], 17.1), (j3x, K(4.5, 0)[1], j3p)]
    R['USB lead GND'] = [(upx, yb + 5.55, zg), (upx - 1.2, -14.9, zg), (132.5, -14.9, zg), (132.5, -24.3, zg),
                         (j3x, -24.3, zg), (j3x, -24.3, 18.8), (j3x, K(7.04, 0)[1], 18.8), (j3x, K(7.04, 0)[1], j3p)]
    W = []
    for nm, pts in R.items():
        W.append((nm, wire(pts, 0.8)))
    # NTC wires (30 AWG, 0.9 OD): from the THERM pads flat between the module's parts, out under the capacitor at its
    # leg end, up between its legs, across to the NTC bead on the cell's top
    tx, ty = M(*c['therm_xy'])
    zw = cz + c['chg_t'] + 1.0 + 0.5                  # just over the parts block (real parts are lower)
    nx, ny, nz = C['bat_x0'] + c['bat_l'] - c['ntc_on_cell'], by, bc + c['bat_d'] / 2 + 1.0
    for k, dx in enumerate((-0.8, 0.8)):
        pts = [(tx, ty + dx, zw), (cap_x0 - 1.0, ty + dx, zw), (cap_x0 - 1.0, ty + dx, 12.0), (124.0, by + dx, 21.0),
               (nx + 2.5, ny + dx, nz), (nx + 1.0, ny + dx, nz)]
        W.append(('NTC wire %d' % (k + 1), wire(pts, 0.45)))
        R['NTC wire %d' % (k + 1)] = pts

    def pair(pts, gap):
        """Two polylines either side of pts (horizontally, square to the local direction)."""
        a_, b_, n_prev = [], [], (0.0, 1.0)
        for i, p_ in enumerate(pts):
            d = [0.0, 0.0]
            for q0, q1 in ((pts[max(i - 1, 0)], p_), (p_, pts[min(i + 1, len(pts) - 1)])):
                dx, dy = q1[0] - q0[0], q1[1] - q0[1]
                h = math.hypot(dx, dy)
                if h > 1e-6:
                    d[0] += dx / h
                    d[1] += dy / h
            h = math.hypot(*d)
            n_ = (-d[1] / h, d[0] / h) if h > 1e-6 else n_prev
            n_prev = n_
            a_.append((p_[0] + n_[0] * gap / 2, p_[1] + n_[1] * gap / 2, p_[2]))
            b_.append((p_[0] - n_[0] * gap / 2, p_[1] - n_[1] * gap / 2, p_[2]))
        return a_, b_

    # solar cable: flat 2-core lying on the floor from the end-B slot, up beside the PCB's end, over J3, into J8
    sx8 = K(0, 113.5)[0]
    sp = [(L + 0.5, C['solar_y'], fz + 1.0), (128.0, C['solar_y'], fz + 1.0), (128.0, C['solar_y'], 15.7),
          (122.0, -8.3, 15.7), (119.2, -6.0, 15.7), (116.8, -2.6, 15.7), (sx8, -2.25, 15.7), (sx8, -2.25, zt + 9.5 + 0.05)]
    for k, pts in enumerate(pair(sp, 2.2)):
        W.append(('Solar cable core %d' % (k + 1), wire(pts, 1.0)))
    R['Solar cable'] = sp
    C['wire_lengths'] = {nm: round(length(pts), 1) for nm, pts in R.items()}
    out['Wires'] = W
    return out


if __name__ == '__main__':
    print('Box %.1f x %.1f x %.1f mm (V4 was 126.1 long)' % (L, C['out_hi'] - c['room_out'], c['top']))
    print('PCB underside Z %.2f, top %.2f; ESP underside %.2f, pin tips %.2f; channel underside %.2f at 0, %.2f at the ESP pin row' % (
        C['zb'], C['zt'], C['esp_z0'], C['esp_z0'] + c['esp_t'] + c['esp_tip'], z_under(0, c['groove_t']), z_under(5.26, c['groove_t'])))
    print('cell Y %.1f..%.1f; charger Y %.1f..%.1f' % (C['bat_y'] - c['bat_d'] / 2, C['bat_y'] + c['bat_d'] / 2, C['chg_y0'], C['chg_y0'] + c['chg_w']))
    print('screws (from below):', ', '.join('(%.1f, %.1f) M3x%.0f' % (x, y, l) for x, y, _, l in SCREWS))
