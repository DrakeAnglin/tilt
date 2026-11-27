"""The controller box: tray and lid for the carrier PCB (hardware/pcb), the 18650 cell and the Adafruit 6092 charger,
plus mock-ups of the parts the PCB's 3D export doesn't have (jacks, ESP32-C6, plugs, cell, charger, wires).

Layout, end A (ports) to end B (USB-C):
  * PCB on three floor bosses, its RJ12 jacks through end wall A. Three M3 flat-head screws come up from under the
    box, through the bosses and the PCB's holes, into heat-set inserts in three lid posts: they clamp the PCB between
    floor and lid, and hold the lid on.
  * 18650 in two saddles along the back wall, beside the PCB body; the lid's cradles press it down.
  * Charger bay past the PCB's end: the 6092 flat on four posts, two M2 × 6 screws at its far end, two short
    indexing studs by end wall B. It goes in USB-C end first, angled down into a slot in end wall B, then drops onto
    the studs; its USB-C (the charge port) sits behind a stadium window. A 3-wire harness from the PCB's J5 runs over
    the top to its pad row; the solar lead comes in through an opening in end wall B (big enough for its plug) and
    runs along the room-side wall.
  * The rod's groove runs down the middle of the lid, centered between the box's two sides. Both long sides are beveled 45 deg, top and bottom, so the box
    tilts in past the rail's lips.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller.py --timeout 1800

Coordinates (mm): X along the rail from end A's outer face, Y across (-Y room side), Z up from the rail floor.
The box's middle, and so the rod and the rail's middle, is at Y = C['groove_y'] (-1.5), not Y 0.
The PCB's KiCad coordinates (x across, y down from the jack edge) map to X = y + pcb_x, Y = x + pcb_y.
"""

import importlib.util
import math
import os

_spec = importlib.util.spec_from_file_location('fits', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fits.py'))
FIT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FIT)

C = dict(
    # 0.4 play round the PCB (at 0.5 the H1 / H2 bosses only touched the walls along a line: non-manifold, so 0.4 makes
    # them merge). Lid top 23.0: the tallest part under it is the cell (top 20.7)
    room_out=-27.4, back_in=22.4, top=23.0, wall=2.0, floor_z=0.0, floor=1.2, lid=2.0, end_t=2.4, end_a=2.0, corner_r=4.0, edge_r=1.5,
    rail_w=FIT.RAIL_W, rail_h=FIT.RAIL_H, rail_wall=FIT.RAIL_WALL, lip_in=FIT.LIP_IN, lip_h=FIT.LIP_H, rod_z=FIT.ROD_Z, rod=FIT.ROD,
    # PTC fuses (Bel 0ZRE0075FF, datasheet: A 11.5 wide, B 23.4 seated, E 4.8 thick, C 5.1 / F 1.9 lead offset): an
    # 11.5 disc on ~11.9 mm legs (KiCad's model; B - A). Each is folded toward the ESP, legs bent 1.6 below the body,
    # so the disc lies flat over its own four resistors
    fuse_leg=11.9, fuse_bend=1.6, fuse_w=11.5, fuse_t=4.8, fuse_body=11.5,
    # width: both walls 0.4 off the PCB's 47 mm jack strip (the widest thing in the box). The box does not fill the rail
    # and has nothing on its sides to center it: it sits about 1.85 off each wall and the groove keeps it under the rod,
    # so one box fits rails of other widths too
    # 45 deg bevels along both long sides, so the box tilts in past the rail's lips without prying (the box is 51.8
    # wide, the gap between the lips 46.5): 2.6 on the bottom edges (0.2 short of the screws' countersinks), 3.0 on
    # the top edges (the lid's 2.0 and the top 1.0 of the tray's wall). A 45 deg fill inside the tray's bottom corners
    # keeps the wall 1.7 thick behind the bottom bevel. Checked by Controller/tilt_in.py
    bevel_bot=2.6, bevel_top=3.0, bevel_fill=1.8,
    # rod groove: a circle, r 5, centered between the box's sides (C['groove_y']), its center 0.37 above the rod's axis:
    # the 4 mm square rod's corners (sweep r 2.83) clear it by 1.8 at the bottom (room for stick-on feet under the box)
    # and ~2.2 each side at the axis, more than the box's play in the rail (1.85 a side), so the rod can't rub its sides.
    # The channel under it is 1.1 thick: its underside is 0.2 above the ESP's nearer row of pin tips (what stops the
    # groove going deeper) and 0.45 above the folded fuse F2
    groove_r=5.0, groove_floor=FIT.ROD_Z - FIT.ROD_CORNER_R - 1.8, groove_t=1.1,
    # PCB: 2.4 mm above the full 1.2 floor (room for the RJ12 tails and the XH headers' tails), board 1.52 (as exported)
    pcb_gap=2.4, pcb_t=1.52, pcb_x=1.8, pcb_y=-25.0, pcb_len=125.0, pcb_bar=47.0, pcb_body=27.0,
    holes=((3.5, 41.0), (43.5, 43.3), (23.8, 121.5)),            # H1, H2, H3 (KiCad x, y)
    boss_d=8.0, post_d=8.0, screw_l=10.0,            # M3 x 10 screws into M3 x 5.7 heat-set inserts (fits.INSERT_*)
    # RJ12 Amphenol 87180-066LF (drawing 87180 sheet 1-3): 13.2 W x 11.5 H, front face 0.55 behind the board edge
    rj_w=13.25, rj_h=11.5,   # measured on the real jack (2026-11-07): 13.25 W x 11.5 H (drawing: 13.2)
    rj_front=0.55, rj_back=17.32, rj_x=(7.825, 23.325, 38.825), rj_mouth_w=9.65,
    rj_mouth=(1.73, 8.50),          # the jack's plug opening, above the board (87180 drawing); latch tab-down
    # end wall A: the PCB's jack edge is trimmed 3-4 mm (by hand, so anywhere in that range) and the jacks come
    # forward through the wall: their front faces sit jack_recess behind the outer face, each in an opening that is the
    # jack's own outline + jack_clear (the jack fills it: no recess, no view into the box). The board is located by its
    # three screws, not its trimmed edge, so the cut's accuracy doesn't matter; the edge ends up 0.75-1.75 off the wall.
    # clearances: 0.3 a side (FDM prints holes ~0.1-0.2 small), 0.35 on top (the opening's top is a bridge: it sags a
    # little), 0.1 under (the jack sits on the board, which the screws locate)
    pcb_trim=(3.0, 4.0), jack_recess=0.3, jack_clear=0.3, jack_clear_top=0.35, jack_clear_bot=0.1, ap_r=0.6,
    rj_tail=2.1, rj_peg=1.9,
    # ESP32-C6 SuperMini (26 x 18) on 8.5 mm sockets + 2.5 mm header spacers, USB toward end B
    esp_l=26.0, esp_w=18.0, esp_t=1.0, esp_xc=12.12, esp_y0=47.57, sock_h=8.59, spacer=2.5, esp_tip=1.9,
    # 18650 (protected, JST-XH lead) along the back wall
    bat_d=19.0, bat_l=65.7,                      # measured
    bat_gap=0.4, stop_t=2.5, stop_hw=5.0,        # end plates: 0.4 play each end, 2.5 thick, 10 wide
    # cell cradles (tray saddles + matching lid cradles): 6 wide, never thinner than 1.5; the PCB-side face 0.6 off the
    # PCB's edge, so on that side each horn stops where its wall is still 1.5 thick; on the back side they run to the wall
    cradle_w=6.0, cradle_t=1.5, cradle_y0=2.6, cradle_lid_y0=4.6, cradle_at=(9.0, 54.0),   # lid cradles start clear of the lead's channel
    # charger: Adafruit 6092 (bq25185 + 3.3 V buck), from Adafruit's own board file (Eagle .brd, 2026-11-08): 29.21 x
    # 19.05 x 1.6, four 2.5 mm plated holes 2.54 in from the corners, USB-C (CUSB31) centered on one short edge about
    # 1.0 past it (product box 30.2 long), screw terminal (3 x 2.54) on the other short edge, the 8-pad row (VIN VU D- D+
    # G BAT 3V EN, VIN at the USB-C end) along one long edge, 2.54 in. Board coordinates: x from the USB-C edge, y from
    # the pad-row edge.
    c6_l=29.21, c6_w=19.05, c6_t=1.6, c6_holes=((2.54, 2.54), (26.67, 2.54), (2.54, 16.51), (26.67, 16.51)),
    c6_post=4.0, c6_post_d=4.4, c6_pilot=1.6,     # posts 4 tall: room under the board for the pads' solder, and the M2 x 6 screws' tips stop 0.8 above the box's underside (at 3 tall they came out through the floor); pilot for M2 × 6 screws
    c6_stud_d=2.1, c6_stud_up=0.8,                # studs in the two holes by end wall B: short, only for indexing (half the board)
    c6_bevel=1.0,                                 # 45 deg lead-in on the slot's top inner edge, so the board angles down and in
    c6_usb=(3.94, 9.525), c6_usb_w=8.94, c6_usb_h=3.26, c6_usb_len=7.35, c6_usb_over=1.0,
    c6_edge_in=1.4,      # the board's USB-C edge sits 1.4 inside end B's outer face (so the socket's mouth is 0.4 inside)
    c6_yc=-6.4,          # board center across the box: room beside it for the solar opening in end wall B
    # solar opening in end wall B: the lead's JST-ZH plug (4.5 x 3.5) goes through it, so the lead can be fitted and
    # pulled with its plug on. (y center, width, height above the floor)
    solar=(-20.4, 6.0, 4.7),
    c6_pads={'VIN': 5.715, 'VU': 8.255, 'G': 15.875, 'BAT': 18.415, '3V': 20.955, 'EN': 23.495}, c6_pad_y=2.54,
    c6_jst=(13.97, 14.1, 8.0, 6.0, 6.5), c6_term=(24.77, 9.525, 7.0, 7.8, 8.4),   # (x, y, along x, along y, height)
)
c = C
C['iw_lo'] = c['room_out'] + c['wall']                  # room-side inner face
C['iw_hi'] = c['back_in']                              # back inner face
C['out_hi'] = c['back_in'] + c['wall']
C['groove_y'] = (c['room_out'] + C['out_hi']) / 2        # the groove runs down the box's middle
C['g_zc'] = c['groove_floor'] + c['groove_r']          # groove's round top: center height
C['groove_top_hw'] = math.sqrt(c['groove_r'] ** 2 - (C['g_zc'] - c['top']) ** 2) if c['top'] < C['g_zc'] else c['groove_r']
C['fz'] = c['floor_z'] + c['floor']
C['zl'] = c['top'] - c['lid']
C['zb'] = C['fz'] + c['pcb_gap']                     # PCB underside
C['zt'] = C['zb'] + c['pcb_t']                       # PCB top
C['pcb_end'] = c['pcb_x'] + c['pcb_len']
C['c6_x0'] = C['pcb_end'] + 2.0                        # charger bay: the 6092's terminal end, 2 past the PCB's end
C['c6_x1'] = C['c6_x0'] + c['c6_l']                    # its USB-C edge
C['c6_y0'] = c['c6_yc'] - c['c6_w'] / 2
C['c6_y1'] = c['c6_yc'] + c['c6_w'] / 2
C['bat_x0'] = c['pcb_x'] + c['pcb_bar'] + 0.3 + c['stop_t'] + c['bat_gap']   # end-A plate starts clear of the H2 post
C['L'] = C['c6_x1'] + c['c6_edge_in']                  # end B's outer face: the charger's USB-C edge 1.4 inside it
C['in_b'] = C['L'] - c['end_t']                         # its inner face: the board's last 1.0 mm lies in a pocket in the wall
C['a0'] = c['pcb_x'] + c['rj_front'] - c['jack_recess']     # end wall A's outer face (the box starts here, not at X 0)
C['ia'] = C['a0'] + c['end_a']                             # end wall A's inner face
C['box_l'] = C['L'] - C['a0']
C['bat_y'] = C['iw_hi'] - 0.3 - c['bat_d'] / 2        # against the back wall: leaves a channel for the cell's lead along its PCB-side shoulder
C['bat_zc'] = C['fz'] + 0.5 + c['bat_d'] / 2
C['esp_z0'] = C['zt'] + c['sock_h'] + c['spacer']    # ESP underside
C['c6_z0'] = C['fz'] + c['c6_post']                    # the charger board's underside
C['c6_zt'] = C['c6_z0'] + c['c6_t']                     # its top
C['solar_y'] = c['solar'][0]                           # the solar lead runs along the room-side wall
L = C['L']


def z_under(y, off):
    """Lower edge of the groove (off 0) or of the channel under it (off = groove_t) at box Y = y; inf outside it."""
    R, y = c['groove_r'] + off, abs(y - C['groove_y'])
    if y > R:
        return float('inf')
    return C['g_zc'] - math.sqrt(R * R - y * y)


def K(x, y):
    """KiCad (x, y) on the PCB -> box (X, Y)."""
    return y + c['pcb_x'], x + c['pcb_y']


def E(x, y):
    """6092 board (x from its USB-C edge, y from its pad-row edge; top view) -> box (X, Y): USB-C toward end B."""
    return C['c6_x1'] - x, C['c6_y1'] - y


HOLES = [K(*h) for h in c['holes']]
SCREWS = [(x, y, c['screw_l']) for x, y in HOLES]   # (x, y, length): one size, M3 x 10


def build(bx, cyl, cone, uni, cut, rbox, obox):
    """{group: [(name, body)]}. rbox(x0, x1, y0, y1, z0, z1, r) = box with its four vertical edges rounded;
    obox(center, u, w, L, W, H) = box along unit vectors u, w."""
    ilo, ihi, fz, zl, zb, zt = C['iw_lo'], C['iw_hi'], C['fz'], C['zl'], C['zb'], C['zt']
    olo, ohi = c['room_out'], C['out_hi']
    in_b = C['in_b']
    out = {}

    def slice_off(body, p, n):
        """Cut away everything on the n side of the plane that runs along X through p; p and n are (y, z)."""
        h = math.hypot(*n)
        ny, nz = n[0] / h, n[1] / h
        return cut(body, obox((L / 2, p[0] + ny * 20, p[1] + nz * 20), (1, 0, 0), (0, nz, -ny), L + 60, 120, 40))

    def groove(off, x0, x1):
        """The groove (off 0), or its outline grown by off: a circle, open above its center."""
        R, zc = c['groove_r'] + off, C['g_zc']
        gy = C['groove_y']
        return uni(cyl((x0, gy, zc), (x1, gy, zc), R), bx(x0, x1, gy - R, gy + R, zc, zc + 20))

    # ================================================================ tray
    F0 = c['floor_z'] + 0.3                              # floor-standing features start inside the floor
    a0, ia = C['a0'], C['ia']
    tray = cut(rbox(a0, L, olo, ohi, c['floor_z'], zl, c['corner_r']),
               rbox(ia, in_b, ilo, ihi, fz, zl + 1, c['corner_r'] - c['wall']))
    # 45 deg fill inside both bottom corners (under the PCB and the cell), then the bevels along the long edges
    # (the bevels themselves are cut last, so they also trim every boss, saddle and stop that reaches the wall)
    w_ = c['bevel_fill']
    for yw, s in ((ilo, 1), (ihi, -1)):
        tray = uni(tray, slice_off(bx(ia - 0.01, in_b + 0.01, yw - s * 0.01, yw + s * w_, F0, fz + w_), (yw + s * w_, fz), (s, 1)))
    # reliefs in end A's inner corner fillets for the PCB's corners, up to the jacks' tops (jacks 1 and 3 reach into them)
    tray = cut(tray, bx(ia - 0.01, ia + 2.2, ilo - 0.01, ilo + 2.2, zb - 0.3, zt + c['rj_h'] + 0.4))
    tray = cut(tray, bx(ia - 0.01, ia + 2.2, ihi - 2.2, ihi + 0.01, zb - 0.3, zt + c['rj_h'] + 0.4))   # and the back one
    for xa, xb in ((a0 - 1, ia + 0.01), (in_b - 0.01, L + 1)):        # the lid's groove channel crosses both ends
        tray = cut(tray, groove(c['groove_t'] + 0.05, xa, xb))   # 0.05 round the lid's channel
    # --- PCB nest: it drops in and is located before the lid goes on: lengthwise by its three screws and the jacks in
    # their openings (its trimmed edge stays 0.75-1.75 off end wall A), across by the two side walls (0.4) and two
    # free-standing ribs 0.2 off the body's back edge, all below the board's top face. The ribs' tops are level with
    # the cell cradles' PCB-side horns (they run through them)
    _rc = c['bat_d'] / 2 + 0.2
    ztop = C['bat_zc'] - math.sqrt(_rc * _rc - (C['bat_y'] - c['cradle_y0'] - c['cradle_t']) ** 2)
    by_body = K(c['pcb_body'], 0)[1]
    for x0, x1, y0 in ((58.0, 72.0, by_body), (100.0, 114.0, by_body)):       # (the back wall now locates the bar's edge)
        tray = uni(tray, bx(x0, x1, y0 + 0.2, y0 + 1.4, F0, ztop))
    # --- PCB: three bosses under its holes; through holes with countersinks from below (screws come up)
    for hx, hy in HOLES:
        tray = uni(tray, cyl((hx, hy, F0), (hx, hy, zb), c['boss_d'] / 2))
    # --- jacks: plug-shaped apertures in end wall A, pockets under their tails and pegs, port marks (1, 2, 3 dots)
    def aperture(y, grow, xa, xb):
        """The jack's own front outline (13.2 x 11.5 on the PCB) + jack_clear a side and on top, jack_clear_bot
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
        for k in range(n + 1):                                  # port marks: 1, 2, 3 dots
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
    # --- charger: Adafruit 6092 on four posts. The two away from the wall take M2 × 6 screws (they cut their own thread); the two by end
    # wall B carry short indexing studs (a screw there would sit 1.5 mm off the wall: no room for a driver). End wall B
    # has a slot for the board's end and the USB-C, its top inner edge a 45 deg lead-in, so the board goes in USB-C end
    # first, angled down, then drops onto the studs.
    for hx_, hy_ in c['c6_holes']:
        px, py = E(hx_, hy_)
        tray = uni(tray, cyl((px, py, F0), (px, py, C['c6_z0']), c['c6_post_d'] / 2))
        if hx_ < c['c6_l'] / 2:                                   # by the wall: a short stud with a chamfered top
            sr, sz = c['c6_stud_d'] / 2, C['c6_z0'] + c['c6_stud_up']
            tray = uni(tray, cyl((px, py, C['c6_z0'] - 0.01), (px, py, sz - 0.4), sr), cone((px, py, sz - 0.41), sr, (px, py, sz), sr - 0.4))
        else:                                                     # a screw
            tray = cut(tray, cyl((px, py, c['floor_z'] + 0.6), (px, py, C['c6_z0'] + 0.01), c['c6_pilot'] / 2))
    ex1, ey0, ey1 = C['c6_x1'], C['c6_y0'], C['c6_y1']
    uz1 = C['c6_zt'] + c['c6_usb_h']
    stop = uz1 + 0.3
    tray = cut(tray, bx(in_b - 0.01, ex1 + 0.3, ey0 - 0.3, ey1 + 0.3, C['c6_z0'], stop))         # slot: board end + socket
    bv = c['c6_bevel'] * math.sqrt(2)
    tray = cut(tray, obox((in_b, c['c6_yc'], stop), (math.sqrt(0.5), 0, math.sqrt(0.5)), (0, 1, 0), bv, ey1 - ey0 + 0.6, bv))   # 45 deg lead-in
    _, uy = E(*c['c6_usb'])
    ur = c['c6_usb_h'] / 2 + 0.3
    uhw = c['c6_usb_w'] / 2 + 0.3 - ur
    uzc = C['c6_zt'] + c['c6_usb_h'] / 2
    tray = cut(tray, bx(in_b - 1, L + 1, uy - uhw, uy + uhw, uzc - ur, uzc + ur),
               cyl((in_b - 1, uy - uhw, uzc), (L + 1, uy - uhw, uzc), ur), cyl((in_b - 1, uy + uhw, uzc), (L + 1, uy + uhw, uzc), ur))
    # --- the solar opening in end wall B: big enough for the lead's plug
    sy_, sw_, sh_ = c['solar']
    tray = cut(tray, bx(in_b - 1, L + 1, sy_ - sw_ / 2, sy_ + sw_ / 2, fz - 0.01, fz + sh_))
    # --- screw holes + countersinks from below (all three)
    for sx, sy, _ in SCREWS:
        tray = cut(tray, cyl((sx, sy, -1), (sx, sy, zb + 1), FIT.M3_R),
                   cone((sx, sy, c['floor_z'] - 0.01), FIT.CSINK_CTRL_R, (sx, sy, c['floor_z'] + FIT.CSINK_CTRL_H), FIT.CSINK_CTRL_R_TOP))
    def beveled(body):
        for yw, s in ((olo, 1), (ohi, -1)):
            body = slice_off(body, (yw + s * c['bevel_bot'], c['floor_z']), (-s, -1))
            body = slice_off(body, (yw + s * c['bevel_top'], c['top']), (-s, 1))
        return body

    tray = beveled(tray)
    # the box's outside shape: nothing of the tray or the lid may reach outside it (checked by the Fusion driver)
    C['outline'] = beveled(rbox(a0, L, olo, ohi, c['floor_z'], c['top'], c['corner_r']))
    out['Tray'] = [('Tray', tray)]

    # ================================================================ lid
    lid = rbox(C['a0'], L, olo, ohi, zl, c['top'], c['corner_r'])
    reg = cut(rbox(C['ia'] + 0.2, in_b - 0.2, ilo + 0.2, ihi - 0.2, zl - 1.4, zl + 0.01, c['corner_r'] - c['wall'] - 0.2),
              rbox(C['ia'] + 1.6, in_b - 1.6, ilo + 1.6, ihi - 1.6, zl - 2, zl + 1, max(c['corner_r'] - c['wall'] - 1.6, 0.3)))
    # no lip along end wall B: the lid locates on the other three sides and its three posts
    reg = cut(reg, bx(in_b - 2.0, in_b + 1, ilo - 1, ihi + 1, zl - 2, zl))
    lid = uni(lid, reg)
    # the channel under the groove (the groove itself is cut last, so it also trims every feature that reaches it)
    lid = uni(lid, cut(groove(c['groove_t'], C['a0'], L), bx(C['a0'] - 1, L + 1, -30, 30, c['top'], c['top'] + 30)))
    # posts with inserts: three on the PCB's holes (they clamp it)
    def root(px, py, r, top, want=2.0):
        """A 45 deg root fillet (cone) where a post meets the lid, as big as the room to the wall / groove allows."""
        gy = C['groove_y']
        if z_under(gy + max(abs(py - gy) - r - want, 0.0), c['groove_t']) < zl + 0.5:      # under the groove's channel: it merges into it
            return None
        room = (ihi if py > 0 else -ilo) - 0.6 - abs(py) - r
        f = min(want, room)
        return cone((px, py, top - f), r, (px, py, top + 0.01), r + f) if f >= 0.6 else None

    # lid features run up to the lid's underside (zl); under the groove the final groove cut trims them
    pr = c['post_d'] / 2
    for (px, py), zbot in [(h, zt) for h in HOLES]:
        top = zl
        lid = uni(lid, cyl((px, py, zbot), (px, py, top + 0.01), pr))
        f = root(px, py, pr, top)
        if f:
            lid = uni(lid, f)
        lid = cut(lid, bx(px - 5, px + 5, ihi - 0.2, ihi + 5, zbot - 1, zl - 0.01), bx(px - 5, px + 5, ilo - 5, ilo + 0.2, zbot - 1, zl - 0.01))   # flats 0.2 off the walls
        lid = cut(lid, cyl((px, py, zbot - 0.01), (px, py, zbot + FIT.INSERT_LEN), FIT.INSERT_R),
                  cone((px, py, zbot - 0.01), FIT.INSERT_R + 0.4, (px, py, zbot + 0.4), FIT.INSERT_R),   # lead-in
                  cyl((px, py, zbot), (px, py, c['floor_z'] + c['screw_l'] + 0.8), FIT.M3_R))      # room past the insert
    # hold-downs: jacks, cell; a stop over the ESP (0.5 clear)
    jtop = zt + c['rj_h']
    for xk in c['rj_x']:
        x, y = K(xk, 9.0)
        lid = uni(lid, bx(x - 2, x + 2, y - 2, y + 2, jtop + 0.05, zl + 0.01))
    # cell: two cradles matching the tray's saddles (same X, same width, same bore, the same 1.5 trim on the PCB side),
    # coming down to the cell's axis on the back side, 0.2 off the back wall
    for sx in (C['bat_x0'] + a for a in c['cradle_at']):
        ylt = c['cradle_lid_y0'] + c['cradle_t']
        lhz = math.sqrt(rc * rc - (by - ylt) ** 2)
        lid = uni(lid, cut(bx(sx, sx + c['cradle_w'], c['cradle_lid_y0'], ihi - 0.2, bc + 0.5, zl + 0.01),
                           cyl((sx - 1, by, bc), (sx + c['cradle_w'] + 1, by, bc), rc),
                           bx(sx - 1, sx + c['cradle_w'] + 1, c['cradle_lid_y0'] - 1, ylt, bc - 1, bc + lhz)))
    ex, ey = K(c['esp_xc'] - 4.0, c['esp_y0'] + 4.0)
    lid = uni(lid, bx(ex - 2, ex + 2, ey - 2, ey + 2, C['esp_z0'] + c['esp_t'] + 0.5, zl + 0.01))
    lid = cut(lid, groove(0, -1, L + 1))
    lid = beveled(lid)
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
    # 18650
    P.append(('18650', cyl((C['bat_x0'], by, bc), (C['bat_x0'] + c['bat_l'], by, bc), c['bat_d'] / 2)))
    # charger: Adafruit 6092 - board, USB-C socket (out past its edge), JST-PH socket (unused), screw terminal (unused),
    # the three wired pads, and its two M2 screws (head on top, 6 long)
    ex1, ey0, ey1, ez0, ezt = C['c6_x1'], C['c6_y0'], C['c6_y1'], C['c6_z0'], C['c6_zt']
    cb = bx(C['c6_x0'], ex1, ey0, ey1, ez0, ezt)
    for hx_, hy_ in c['c6_holes']:
        qx, qy = E(hx_, hy_)
        cb = cut(cb, cyl((qx, qy, ez0 - 1), (qx, qy, ezt + 1), 1.25))
    P.append(('Charger board', cb))
    ux0, uy = E(c['c6_usb_len'] - c['c6_usb_over'], c['c6_usb'][1])
    ur_, uhw_ = c['c6_usb_h'] / 2, c['c6_usb_w'] / 2 - c['c6_usb_h'] / 2      # a stadium, like the real shell
    uzc_ = ezt + ur_
    P.append(('Charger USB-C', uni(bx(ux0, ex1 + c['c6_usb_over'], uy - uhw_, uy + uhw_, ezt, ezt + c['c6_usb_h']),
                                   cyl((ux0, uy - uhw_, uzc_), (ex1 + c['c6_usb_over'], uy - uhw_, uzc_), ur_),
                                   cyl((ux0, uy + uhw_, uzc_), (ex1 + c['c6_usb_over'], uy + uhw_, uzc_), ur_))))
    for nm, (jx, jy, lx, ly, h) in (('Charger JST', c['c6_jst']), ('Charger terminal', c['c6_term'])):
        qx, qy = E(jx, jy)
        P.append((nm, bx(qx - lx / 2, qx + lx / 2, qy - ly / 2, qy + ly / 2, ezt, ezt + h)))
    for nm in ('VIN', 'G', 'BAT'):
        qx, qy = E(c['c6_pads'][nm], c['c6_pad_y'])
        P.append(('Charger pad %s' % nm, cyl((qx, qy, ez0 - 0.8), (qx, qy, ezt + 0.3), 0.9)))
    for hx_, hy_ in [h for h in c['c6_holes'] if h[0] > c['c6_l'] / 2]:
        qx, qy = E(hx_, hy_)
        P.append(('Charger screw %.0f %.0f' % (hx_, hy_), uni(cyl((qx, qy, ezt + 0.02), (qx, qy, ezt + 1.6), 1.9),
                                                              cyl((qx, qy, ezt + 0.02 - 6.0), (qx, qy, ezt + 0.03), 1.0))))
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
    jx5 = K(0, 113.5)[0]                              # charger socket pins: y 113.5, x 3 + 2.5 k (G, B+, -, L+, -, P+)
    j5 = {n: K(3.0 + 2.5 * (n - 1), 0)[1] for n in range(1, 7)}
    pad = {nm: E(c['c6_pads'][nm], c['c6_pad_y']) for nm in ('VIN', 'G', 'BAT')}
    ptop = C['c6_zt'] + 0.35
    R = {}
    # harness over the top to the 6092's pad row. G and BAT leave the plug at 17.7 (over the plug and the solar cable),
    # drop to 15.0 past X 132 (over the 6092's screw terminal and JST socket) and come in from the room side; PWR stays
    # at 19.4 over them. B+ and L+ join in one splice past the plug and go on as one wire to BAT
    px_, py_ = pad['G']
    R['Harness G (G)'] = [(jx5, j5[1], PLUG), (jx5, j5[1], 17.7), (130.0, j5[1], 17.7), (132.5, j5[1], 15.0), (px_, j5[1], 15.0),
                          (px_, py_ - 1.6, 15.0), (px_, py_, ptop)]
    px_, py_ = pad['BAT']
    sx_, sy_ = 124.0, -17.0
    R['Harness BAT (B+ / L+ splice)'] = [(jx5, j5[2], PLUG), (jx5, j5[2], 17.7), (sx_, sy_, 17.7), (130.0, sy_, 17.7), (132.5, sy_, 15.0),
                                         (px_, sy_, 15.0), (px_, py_ - 1.6, 15.0), (px_, py_, ptop)]
    R['Harness BAT leg (L+)'] = [(jx5, j5[4], PLUG), (jx5, j5[4], 17.7), (sx_, sy_, 17.7)]
    px_, py_ = pad['VIN']
    R['Harness PWR (P+)'] = [(jx5, j5[6], PLUG), (jx5, j5[6], 19.4), (px_, j5[6], 19.4), (px_, py_ - 3.0, 15.0), (px_, py_, ptop)]
    # cell lead (both wires out of the cell's end-B face): down the end face's PCB side, past the H3 post's back, along the
    # channel between the cell's PCB-side shoulder and the PCB's back edge (the two wires one above the other), into J4
    ce = C['bat_x0'] + c['bat_l'] + 0.05
    j4x, j4a = K(0, 105.0)[0], K(17.5, 0)[1]
    j4b = K(20.0, 0)[1]
    # Both cross under the groove's channel at 16.2 or lower, one round each end of the plug
    R['Cell lead -'] = [(ce + 0.85, by - 0.9, bc - 0.5), (ce + 2.0, by - 0.9, bc - 0.5), (ce + 0.9, 6.0, 12.6),
                        (ce + 0.9, 2.7, 14.4), (118.6, 2.7, 14.4), (110.0, 2.7, 14.4), (104.0, -1.5, 16.2),
                        (104.0, j4a, 17.7), (j4x, j4a, 17.7), (j4x, j4a, PLUG)]
    R['Cell lead +'] = [(ce + 0.85, by + 0.9, bc + 0.5), (ce + 2.0, by + 0.9, bc + 0.5), (ce + 0.9, 6.0, 14.6),
                        (ce + 0.9, 2.7, 16.2), (118.6, 2.7, 16.2), (111.0, 2.7, 16.2), (111.0, -2.0, 16.2),
                        (111.0, j4b, 17.7), (j4x, j4b, 17.7), (j4x, j4b, PLUG)]
    W = []
    for nm, pts in R.items():
        if nm == 'Harness BAT leg (L+)':
            continue
        b_ = wire(pts, 0.8)
        if nm.startswith('Harness BAT'):                # the splice: both legs and the run to BAT are one wire
            b_ = uni(b_, wire(R['Harness BAT leg (L+)'], 0.8))
        W.append((nm, b_))
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

    # solar cable: flat 2-core lying on the floor along the room-side wall from the end-B slot, up beside the PCB's end, into J8
    sx8 = K(0, 113.5)[0]
    sp = [(L + 0.5, C['solar_y'], fz + 1.0), (128.0, C['solar_y'], fz + 1.0), (128.0, C['solar_y'], 15.7),
          (126.3, C['solar_y'] + 0.6, 15.7), (124.6, -18.2, 15.7), (123.0, -13.5, 15.7), (122.0, -8.3, 15.7), (119.2, -6.0, 15.7), (116.8, -2.6, 15.7), (sx8, -2.25, 15.7), (sx8, -2.25, zt + 9.5 + 0.05)]
    for k, pts in enumerate(pair(sp, 2.2)):
        W.append(('Solar cable core %d' % (k + 1), wire(pts, 1.0)))
    R['Solar cable'] = sp
    C['wire_lengths'] = {nm: round(length(pts), 1) for nm, pts in R.items()}
    out['Wires'] = W
    return out


if __name__ == '__main__':
    print('Box %.1f x %.1f x %.1f mm' % (L, C['out_hi'] - c['room_out'], c['top']))
    print('PCB underside Z %.2f, top %.2f; ESP underside %.2f, pin tips %.2f; channel underside %.2f at its middle, %.2f at the inner edge of the ESP pin row' % (
        C['zb'], C['zt'], C['esp_z0'], C['esp_z0'] + c['esp_t'] + c['esp_tip'], z_under(C['groove_y'], c['groove_t']), z_under(K(19.74 + 0.32, 0)[1], c['groove_t'])))
    print('cell Y %.1f..%.1f; charger X %.1f..%.1f Y %.1f..%.1f, board top Z %.2f' % (C['bat_y'] - c['bat_d'] / 2, C['bat_y'] + c['bat_d'] / 2,
          C['c6_x0'], C['c6_x1'], C['c6_y0'], C['c6_y1'], C['c6_zt']))
    print('screws (from below):', ', '.join('(%.1f, %.1f) M3x%.0f' % (x, y, l) for x, y, l in SCREWS))
