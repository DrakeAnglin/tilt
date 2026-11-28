"""Fit study for the controller PCB v3 (docs/pcb-v3-concept.md): board, cell, cell contacts and box, before the board is
drawn in KiCad. Not a print file yet: the board here is a mock-up (outline, tall parts), not a KiCad export.

Layout, end A to end B:
  * End A wall: port 1's RJ12 jack, the USB-C socket, the reset button's hole and the solar jack.
  * The board's 27 mm body runs along the room side with the ESP32-C6 on sockets; the 18650 lies in the board's notch
    on two tray saddles along the back wall, exactly where it lies in the v2.2 box, between a Keystone 596 button
    contact (+, fixed) and a Keystone 590 leaf contact (-, sprung) that stand on the board at the notch's ends.
  * Past the cell the board is full width again: the bay for the fuses and the battery header.
  * Ports 2 and 3 are on an end section joined by a 10 mm neck; their jacks come through end wall B. PORTS = 1 builds
    the short box for a board with the end section sawn off.
  * The lid and the rod's groove are the v2.2 box's: top 23.0, same groove center, floor height and radius.

Putting the board in: end A first, tilted a couple of degrees, so jack 1, the USB-C socket and the solar jack's nose
go into end wall A; then end B comes down onto the tray's low sill. End wall B above the sill is an apron on the lid,
with windows for jacks 2 and 3 open downward, so the lid drops over them. The Fusion driver walks the board's path
backwards as a check.

The contacts are made for a cell that rests on the board. Here the cell hangs through the board, so each contact's
center leg (on the plate's line, right under the cell's end) is clipped off and the notch starts just behind the
plate; the two outer legs, 3.0 behind the plate, hold it. To be proven with sample parts before the layout.

Coordinates (mm): X along the rail from end A's outer face, Y across (-Y room side), Z up from the rail floor.
Board coordinates (bx across from the room-side edge, by along from the end A edge): X = by + pcb_x, Y = bx + pcb_y.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v3.py --timeout 1800
"""

import importlib.util
import math
import os

_spec = importlib.util.spec_from_file_location('fits', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fits.py'))
FIT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FIT)

PORTS = 3          # 3 = the full board; 1 = the end section sawn off (short box)


def params(ports=PORTS):
    c = dict(
        ports=ports,
        # the v2.2 box's section: width, top, walls, bevels (Controller.py)
        room_out=-27.4, back_in=22.4, top=23.0, wall=2.0, floor_z=0.0, floor=1.2, lid=2.0, end_t=2.0, corner_r=4.0,
        bevel_bot=2.6, bevel_top=3.0, bevel_fill=1.8, rim=1.6,
        # rod groove: exactly the v2.2 box's: r 5, its floor 1.8 under the rod's corners, channel 1.1
        groove_r=5.0, groove_floor=FIT.ROD_Z - FIT.ROD_CORNER_R - 1.8, groove_t=1.1,
        # board: 2.4 above the floor (RJ12 tails), 1.6 thick, 47 wide, 0.6 off each end wall
        pcb_gap=2.4, pcb_t=1.6, pcb_x=2.6, pcb_y=-25.0, pcb_w=47.0, pcb_body=27.0, end_gap=0.6,
        bay=14.0,                     # full-width board past the cell: fuses, battery header
        neck=(18.5, 28.5, 3.0),       # the neck: bx from, to; length
        tab_len=17.0,                 # the end section
        # RJ12 Amphenol 87180-066LF: 13.25 W x 11.5 H, 16.77 deep; its front 0.3 inside the wall's outer face
        rj_w=13.25, rj_h=11.5, rj_d=16.77, rj_recess=0.3, rj_bx=(7.825, 7.825, 23.325), rj_mouth_w=9.65, rj_mouth=(1.73, 8.50),
        jack_clear=0.3, jack_clear_top=0.35, jack_clear_bot=0.1, rj_tail=2.1,
        # USB-C GCT USB4125: 8.94 x 6.8 x 3.16; mouth 1.3 inside end A's outer face, so its shell stakes (2.6 behind the
        # mouth) are on the board. A plug's overmold stops 1.85 before the mouth (GCT's mating view): 0.55 outside the wall
        usb=(21.0, 8.94, 6.8, 3.16), usb_in=1.3,
        # solar jack Same Sky PJ-007 (3.5 x 1.35 plug): 11.1 long, 5.0 wide, 7.4 high, barrel axis 4.7 above the board;
        # its nose 1.0 into the wall
        sol=(38.5, 5.0, 11.1, 7.4), sol_axis=4.7, sol_hole_r=2.2, sol_nose=1.0,
        # reset button C&K PTS645VL39 (right-angle): frame 7.5 wide (8.5 over its legs), 6 deep, 7 high; pressed with a
        # pen tip through a hole in end wall A
        btn=(30.6, 8.5, 6.0, 7.0), btn_axis=4.0, btn_hole_r=1.3,
        # ESP32-C6 SuperMini (26 x 18 taken; to measure) on 8.59 sockets + 2.5 spacers; rows 15.24 apart, 1.5 nearer the
        # room side than v2.2; its USB-C faces end B, with a clear corridor for a cable when the lid is off
        esp_l=26.0, esp_w=18.0, esp_t=1.0, esp_bx=10.62, esp_by=20.5, sock_h=8.59, spacer=2.5, esp_tip=1.9, esp_rows=(3.0, 18.24),
        esp_plug=(12.4, 6.5, 35.0),   # a USB-C plug's overmold: width, height, length with the cable's bend
        # 18650 in the notch, where it lies in the v2.2 box. This box takes protected button-top cells of 68 to 70 mm
        bat_d=19.0, bat_l=69.0, bat_lmin=68.0, bat_lmax=70.0, bat_up=0.5,
        cradle_w=6.0, cradle_t=1.5, cradle_y0=2.6, cradle_lid_y0=4.6, cradle_off=(-22.0, 16.0),
        # Keystone 596 (+ button) and 590 (- leaf), catalog M65 p11 and p35. Both: plate 9.1 wide x 11.4 high on the "L"
        # line, base 6.3 deep behind it, a center leg on the L line (clipped off here) and two legs 3.0 behind it, 8.9
        # apart, in dia 1.3 holes. 596: button dia 6.4, center 7.0 above the board, about 0.2 proud of the plate.
        # 590: leaf 5.1 wide, 4.1 free reach, its contact bend about 6.2 above the board free and 5.0 fully pressed
        # (scaled from the drawing); its top fold stands about 12.5 high. L = cell + 2.3 (p35: AA 50.3 -> 52.6)
        ct_w=9.1, ct_h=11.4, ct_fold=12.5, ct_base=6.3, ct_t=0.3, ct_leg_back=3.0, ct_leg_span=8.9,
        btn_d=6.4, btn_z=7.0, btn_proud=0.2, leaf_w=5.1, leaf_reach=4.1, leaf_z=(6.2, 5.0), ct_l_extra=2.3, ct_by0=17.4,
        ct_edge=0.5,                  # the notch starts this far behind each plate (the cell's end must not meet the board)
        boss_d=8.0, post_d=8.0, screw_l=10.0,
        cap=(10.0, 88.0, 4.0, 12.0),  # 470 uF: bx, by, radius, height (past the ESP's cable corridor, off the groove line)
        pull_r=7.0,                   # finger notch in the back wall beside the cell (a tab on the lid fills it)
        # fuses standing: a 16 V radial resettable fuse of about 1.1 A (7.5 x 3.1 x 13 taken) per port, and one of about
        # 3 A for the cell (10 x 3.5 x 15 taken). The parts are not picked yet; these are the sizes they must stay inside
        fuse=(3.1, 7.5, 13.0), fuse_cell=(10.0, 3.5, 15.0),
    )
    c['iw_lo'] = c['room_out'] + c['wall']
    c['iw_hi'] = c['back_in']
    c['out_hi'] = c['back_in'] + c['wall']
    c['groove_y'] = (c['room_out'] + c['out_hi']) / 2
    c['g_zc'] = c['groove_floor'] + c['groove_r']
    c['fz'] = c['floor_z'] + c['floor']
    c['zl'] = c['top'] - c['lid']
    c['zs'] = c['top'] - c['bevel_top']       # where tray and lid meet: the top bevel is all in the lid's rim
    c['zb'] = c['fz'] + c['pcb_gap']
    c['zt'] = c['zb'] + c['pcb_t']
    c['ct_span'] = c['bat_l'] + c['ct_l_extra']
    c['ct_x'] = (c['pcb_x'] + c['ct_by0'], c['pcb_x'] + c['ct_by0'] + c['ct_span'])      # the two contacts' L lines
    c['notch'] = (c['ct_by0'] - c['ct_edge'], c['ct_by0'] + c['ct_span'] + c['ct_edge'])
    c['bar_end'] = c['ct_by0'] + c['ct_span'] + c['ct_base'] + 0.6 + c['bay']
    c['pcb_len'] = c['bar_end'] + (c['neck'][2] + c['tab_len'] if ports > 1 else 0.0)
    c['L'] = c['pcb_x'] + c['pcb_len'] + c['end_gap'] + c['end_t']
    c['ia'], c['in_b'] = c['end_t'], c['L'] - c['end_t']
    c['bat_y'] = c['iw_hi'] - 0.3 - c['bat_d'] / 2
    c['bat_zc'] = c['fz'] + c['bat_up'] + c['bat_d'] / 2
    c['bat_x0'] = c['ct_x'][0] + c['ct_t'] / 2 + c['btn_proud']          # the cell's + end rests on the button
    c['esp_z0'] = c['zt'] + c['sock_h'] + c['spacer']
    # screw holes (bx, by): H1 behind the USB-C socket, H2 room side in the bay, H3 mid-body, H4 on the end section
    c['holes'] = ((21.0, 13.0), (4.5, c['bar_end'] - 4.5), (23.0, 54.0))
    c['hole_tab'] = (39.5, c['bar_end'] + c['neck'][2] + c['tab_len'] / 2)
    return c


C = params()


def K(bx_, by_, c=None):
    """Board (bx, by) -> box (X, Y)."""
    c = c or C
    return by_ + c['pcb_x'], bx_ + c['pcb_y']


def z_under(y, off, c=None):
    """Lower edge of the groove (off 0) or of the channel under it (off = groove_t) at box Y = y; inf outside it."""
    c = c or C
    R, d = c['groove_r'] + off, abs(y - c['groove_y'])
    if d > R:
        return float('inf')
    return c['g_zc'] - math.sqrt(R * R - d * d)


def holes(c=None):
    c = c or C
    hs = list(c['holes'])
    if c['ports'] > 1:
        hs.append(c['hole_tab'])
    return [K(*h, c=c) for h in hs]


def jacks(c=None):
    """[(port, y center, x front, x back, +1 toward end B / -1 toward end A)]."""
    c = c or C
    out = [(1, K(c['rj_bx'][0], 0, c)[1], c['rj_recess'], c['rj_recess'] + c['rj_d'], -1)]
    if c['ports'] > 1:
        for p in (2, 3):
            out.append((p, K(c['rj_bx'][p - 1], 0, c)[1], c['L'] - c['rj_recess'], c['L'] - c['rj_recess'] - c['rj_d'], 1))
    return out


def leaf_squeeze(cell_len, c=None):
    """How far a cell of this length presses the 590's leaf back (mm): the + end rests on the 596's button."""
    c = c or C
    free_tip = c['ct_x'][1] - c['ct_t'] / 2 - c['leaf_reach']
    return c['bat_x0'] + cell_len - free_tip


def room_under_lid(y, c=None):
    """Height of the lid's underside (or the groove's channel, where lower) above the board's top at box Y = y."""
    c = c or C
    return min(c['zl'], z_under(y, c['groove_t'], c)) - c['zt']


def facts(c=None):
    """The numbers the fit depends on, worked out without Fusion (also used by the tests)."""
    c = c or C
    zt, zl = c['zt'], c['zl']
    f = {}
    f['box'] = (round(c['L'], 1), round(c['out_hi'] - c['room_out'], 1), c['top'])
    f['board_len'] = round(c['pcb_len'], 1)
    f['cell_top_to_lid'] = round(zl - (c['bat_zc'] + c['bat_d'] / 2), 2)
    f['cell_to_groove_channel'] = round(
        math.hypot(c['bat_y'] - c['groove_y'], c['bat_zc'] - c['g_zc']) - c['bat_d'] / 2 - (c['groove_r'] + c['groove_t']), 2)
    f['cell_to_board_edge'] = round((c['bat_y'] - c['bat_d'] / 2) - (c['pcb_y'] + c['pcb_body']), 2)
    f['cell_axis_above_board'] = round(c['bat_zc'] - zt, 2)
    f['button_above_cell_axis'] = round(zt + c['btn_z'] - c['bat_zc'], 2)
    f['leaf_above_cell_axis'] = tuple(round(zt + z - c['bat_zc'], 2) for z in c['leaf_z'])
    f['leaf_squeeze'] = {ln: round(leaf_squeeze(ln, c), 2) for ln in (c['bat_lmin'], c['bat_l'], c['bat_lmax'])}
    f['leaf_reach'] = c['leaf_reach']
    f['cell_ends_inside_notch'] = (round(c['bat_x0'] - (c['pcb_x'] + c['notch'][0]), 2),
                                   round((c['pcb_x'] + c['notch'][1]) - (c['bat_x0'] + c['bat_lmax']), 2))
    f['contact_top_to_lid'] = round(zl - (zt + c['ct_fold']), 2)
    tip = c['sock_h'] + c['spacer'] + c['esp_t'] + c['esp_tip']
    f['esp_tips_to_lid'] = round(min(room_under_lid(K(r, 0, c)[1], c) - tip for r in c['esp_rows']), 2)
    f['jack_top_to_lid'] = round(min(room_under_lid(y + s * c['rj_w'] / 2, c) - c['rj_h'] for _, y, _, _, _ in jacks(c) for s in (-1, 0, 1)), 2)
    cy = K(c['cap'][0], 0, c)[1]
    f['cap_top_to_lid'] = round(min(room_under_lid(cy + d, c) for d in (-c['cap'][2], 0, c['cap'][2])) - 0.5 - c['cap'][3], 2)
    f['groove'] = (c['groove_y'], round(c['groove_floor'], 2), c['groove_r'], c['groove_t'])
    return f


def outline_pts(c=None):
    """The box's cross-section (Y, Z), with its four 45 deg bevels: for the tilt-in check."""
    c = c or C
    lo, hi, z0, z1, bb, bt = c['room_out'], c['out_hi'], c['floor_z'], c['top'], c['bevel_bot'], c['bevel_top']
    return [(lo + bb, z0), (hi - bb, z0), (hi, z0 + bb), (hi, z1 - bt), (hi - bt, z1), (lo + bt, z1), (lo, z1 - bt), (lo, z0 + bb)]


def build(bx, cyl, cone, uni, cut, rbox, obox, c=None):
    """{group: [(name, body)]}; the same helper functions as Controller.build."""
    c = c or C
    ilo, ihi, fz, zl, zb, zt, zs = c['iw_lo'], c['iw_hi'], c['fz'], c['zl'], c['zb'], c['zt'], c['zs']
    olo, ohi, L, ia, in_b = c['room_out'], c['out_hi'], c['L'], c['ia'], c['in_b']
    gy = c['groove_y']
    out = {}
    F0 = c['floor_z'] + 0.3

    def slice_off(body, p, n):
        h = math.hypot(*n)
        ny, nz = n[0] / h, n[1] / h
        return cut(body, obox((L / 2, p[0] + ny * 20, p[1] + nz * 20), (1, 0, 0), (0, nz, -ny), L + 60, 120, 40))

    def groove(off, x0, x1):
        R, zc = c['groove_r'] + off, c['g_zc']
        return uni(cyl((x0, gy, zc), (x1, gy, zc), R), bx(x0, x1, gy - R, gy + R, zc, zc + 20))

    def beveled(body):
        for yw, s in ((olo, 1), (ohi, -1)):
            body = slice_off(body, (yw + s * c['bevel_bot'], c['floor_z']), (-s, -1))
            body = slice_off(body, (yw + s * c['bevel_top'], c['top']), (-s, 1))
        return body

    def stadium(x0, x1, y, zc, hw, hh):
        """A rounded slot through an end wall: half width hw, half height hh, centered (y, zc)."""
        r = min(hw, hh)
        a = bx(x0, x1, y - hw + r, y + hw - r, zc - hh, zc + hh)
        for yy in (y - hw + r, y + hw - r):
            a = uni(a, cyl((x0, yy, zc), (x1, yy, zc), r))
        return a

    jw = c['rj_w'] / 2 + c['jack_clear']
    jz0, jz1 = zt - c['jack_clear_bot'], zt + c['rj_h'] + c['jack_clear_top']
    HOLES = holes(c)
    by, bc, rc = c['bat_y'], c['bat_zc'], c['bat_d'] / 2 + 0.2

    # ================================================================ tray
    tray = cut(rbox(0, L, olo, ohi, c['floor_z'], zs, c['corner_r']),
               rbox(ia, in_b, ilo, ihi, fz, zs + 1, c['corner_r'] - c['wall']))
    w_ = c['bevel_fill']
    for yw, s in ((ilo, 1), (ihi, -1)):
        tray = uni(tray, slice_off(bx(ia - 0.01, in_b + 0.01, yw - s * 0.01, yw + s * w_, F0, fz + w_), (yw + s * w_, fz), (s, 1)))
    for xa, xb in ((-1, ia + 0.01), (in_b - 0.01, L + 1)):                 # the lid's groove channel crosses both ends
        tray = cut(tray, groove(c['groove_t'] + 0.05, xa, xb))
    for hx, hy in HOLES:                                                   # bosses under the board's holes
        tray = uni(tray, cyl((hx, hy, F0), (hx, hy, zb), c['boss_d'] / 2))
    # end wall A: closed windows (the board goes in this end first, tilted a little). End wall B: the tray only has
    # a low sill, up to the board's top; the rest of that wall is an apron on the lid, with the jacks' windows open
    # downward in it. So the board's end B comes almost straight down, and the lid then drops over the jacks.
    for p, y, xf, xr, s in jacks(c):
        if s < 0:
            tray = cut(tray, bx(-1, ia + 0.01, y - jw, y + jw, jz0, jz1))
    tray = cut(tray, bx(in_b - 0.01, L + 1, olo - 1, ohi + 1, jz0, zs + 1))
    for ya, yb_ in ((ilo, ilo + 2.2), (ihi - 2.2, ihi)):                  # and no inner corner fillets above the sill: the board's corners pass there
        tray = cut(tray, bx(in_b - 2.2, in_b + 0.01, ya, yb_, jz0, zs + 1))
    ux, uw, ul, uh = c['usb']
    _, uy = K(ux, 0, c)
    tray = cut(tray, bx(-1, ia + 0.01, uy - uw / 2 - 0.4, uy + uw / 2 + 0.4, zt - 0.35, zt + uh + 0.4))       # a plain window round the socket's shell
    _, sy = K(c['sol'][0], 0, c)
    sw, sl, sh = c['sol'][1:]
    tray = cut(tray, cyl((-1, sy, zt + c['sol_axis']), (ia + 0.01, sy, zt + c['sol_axis']), c['sol_hole_r']))
    tray = cut(tray, bx(ia - c['sol_nose'] - 0.1, ia + 0.01, sy - sw / 2 - 0.3, sy + sw / 2 + 0.3, zt - 0.1, zt + sh + 0.3))   # the jack's nose
    _, ry = K(c['btn'][0], 0, c)
    tray = cut(tray, cyl((-1, ry, zt + c['btn_axis']), (ia + 0.01, ry, zt + c['btn_axis']), c['btn_hole_r']))
    for xa, xb in ((ia - 0.01, ia + 2.2), (in_b - 2.2, in_b + 0.01)):      # inner corner fillets: room for the board's corners and the jacks'
        tray = cut(tray, bx(xa, xb, ihi - 2.2, ihi + 0.01, zb - 0.3, zt + 2.0), bx(xa, xb, ilo - 0.01, ilo + 2.2, zb - 0.3, zt + c['rj_h'] + 0.4))
    # the cell: two saddles under it (in the board's notch), back horns into the wall
    ytrim = c['cradle_y0'] + c['cradle_t']
    chz = math.sqrt(rc * rc - (by - ytrim) ** 2)
    bat_xc = c['bat_x0'] + c['bat_l'] / 2
    for off in c['cradle_off']:
        sx = bat_xc + off
        sad = cut(bx(sx, sx + c['cradle_w'], c['cradle_y0'], ihi + 0.5, F0, bc - 0.5),
                  cyl((sx - 1, by, bc), (sx + c['cradle_w'] + 1, by, bc), rc),
                  bx(sx - 1, sx + c['cradle_w'] + 1, c['cradle_y0'] - 1, ytrim, bc - chz, bc + 1))
        tray = uni(tray, sad)
    for sx, sy_ in HOLES:                                                  # screws come up from below
        tray = cut(tray, cyl((sx, sy_, -1), (sx, sy_, zb + 1), FIT.M3_R),
                   cone((sx, sy_, c['floor_z'] - 0.01), FIT.CSINK_CTRL_R, (sx, sy_, c['floor_z'] + FIT.CSINK_CTRL_H), FIT.CSINK_CTRL_R_TOP))
    # a finger notch in the back wall at the cell's middle, to lift the cell out
    tray = cut(tray, cyl((bat_xc, ihi - 0.5, zs), (bat_xc, ohi + 1, zs), c['pull_r']))
    tray = beveled(tray)
    out['outline'] = beveled(rbox(0, L, olo, ohi, c['floor_z'], c['top'], c['corner_r']))
    out['Tray'] = [('Tray', tray)]

    # ================================================================ lid
    # a rim as tall as the top bevel (zs to the top) and 3.6 thick, so the bevel thins neither it nor the tray's wall;
    # the rim's inner 1.4 runs on down 1.4 into the tray as the locating lip (0.2 off the walls)
    rm = c['wall'] + c['rim']
    lid = cut(rbox(0, L, olo, ohi, zs, c['top'], c['corner_r']),
              rbox(ia + c['rim'], in_b - c['rim'], ilo + c['rim'], ihi - c['rim'], zs - 1, zl, max(c['corner_r'] - rm, 0.3)))
    lip = cut(rbox(ia + 0.2, in_b - 0.2, ilo + 0.2, ihi - 0.2, zs - 1.4, zs + 0.01, c['corner_r'] - c['wall'] - 0.2),
              rbox(ia + c['rim'], in_b - c['rim'], ilo + c['rim'], ihi - c['rim'], zs - 2, zs + 1, max(c['corner_r'] - rm, 0.3)))
    lid = uni(lid, lip)
    lid = uni(lid, cut(groove(c['groove_t'], 0, L), bx(-1, L + 1, -30, 30, c['top'], c['top'] + 30)))
    # end wall B's apron: the box's own end shape from the sill up to the rim, with the jacks' windows cut into it
    apron = cut(rbox(L - 30, L, olo, ohi, jz0 + 0.1, zs + 0.01, c['corner_r']), bx(L - 31, in_b, olo - 1, ohi + 1, jz0 - 1, zs + 1))
    for p, y, xf, xr, s in jacks(c):
        if s > 0:
            apron = cut(apron, bx(in_b - 1, L + 1, y - jw, y + jw, jz0 - 1, jz1))
    # the finger between the two windows is thickened 3 mm inward (above the board), so it does not snap in handling
    ys = sorted(y for p, y, xf, xr, s in jacks(c) if s > 0)
    if len(ys) == 2:
        apron = uni(apron, bx(in_b - 3.0, in_b + 0.01, ys[0] + jw, ys[1] - jw, zt + 0.3, zs + 0.01))
    lid = uni(lid, apron)
    # the tab that fills the tray's finger notch
    lid = uni(lid, cut(cyl((bat_xc, ihi + 0.2, zs), (bat_xc, ohi, zs), c['pull_r'] - 0.25), bx(bat_xc - 10, bat_xc + 10, ihi - 1, ohi + 1, zs, zs + 10)))
    pr = c['post_d'] / 2
    for px, py in HOLES:                                                   # posts with inserts clamp the board
        lid = uni(lid, cyl((px, py, zt), (px, py, zl + 0.01), pr))
        lid = cut(lid, cyl((px, py, zt - 0.01), (px, py, zt + FIT.INSERT_LEN), FIT.INSERT_R),
                  cone((px, py, zt - 0.01), FIT.INSERT_R + 0.4, (px, py, zt + 0.4), FIT.INSERT_R),
                  cyl((px, py, zt), (px, py, c['floor_z'] + c['screw_l'] + 0.8), FIT.M3_R))
    for off in c['cradle_off']:                                            # cradles hold the cell down
        sx = bat_xc + off
        ylt = c['cradle_lid_y0'] + c['cradle_t']
        lhz = math.sqrt(rc * rc - (by - ylt) ** 2)
        lid = uni(lid, cut(bx(sx, sx + c['cradle_w'], c['cradle_lid_y0'], ihi - 0.2, bc + 0.5, zl + 0.01),
                           cyl((sx - 1, by, bc), (sx + c['cradle_w'] + 1, by, bc), rc),
                           bx(sx - 1, sx + c['cradle_w'] + 1, c['cradle_lid_y0'] - 1, ylt, bc - 1, bc + lhz)))
    lid = cut(lid, groove(0, -1, L + 1))
    lid = beveled(lid)
    out['Lid'] = [('Lid', lid)]

    # ================================================================ the board (mock-up) and its parts
    x0 = c['pcb_x']
    y0, yb, y1 = c['pcb_y'], c['pcb_y'] + c['pcb_body'], c['pcb_y'] + c['pcb_w']
    n0, n1 = x0 + c['notch'][0], x0 + c['notch'][1]
    xe = x0 + c['bar_end']
    board = cut(bx(x0, xe, y0, y1, zb, zt), bx(n0, n1, yb, y1 + 1, zb - 1, zt + 1))
    if c['ports'] > 1:
        nk0, nk1, nl = c['neck']
        board = uni(board, bx(xe - 0.01, xe + nl + 0.01, y0 + nk0, y0 + nk1, zb, zt), bx(xe + nl, xe + nl + c['tab_len'], y0, y1, zb, zt))
    for hx, hy in HOLES:
        board = cut(board, cyl((hx, hy, zb - 1), (hx, hy, zt + 1), FIT.M3_R))

    def legs(cxh, s):
        """The two outer legs of a 590 / 596 whose plate is on the L line at cxh (its center leg is clipped off);
        s = +1 if the cell is toward +X."""
        return [(cxh - s * c['ct_leg_back'], by - c['ct_leg_span'] / 2), (cxh - s * c['ct_leg_back'], by + c['ct_leg_span'] / 2)]

    for k, cxh in enumerate(c['ct_x']):
        for lx, ly in legs(cxh, 1 if k == 0 else -1):
            board = cut(board, cyl((lx, ly, zb - 1), (lx, ly, zt + 1), 0.65))
    out['Board'] = [('Board (mock-up)', board)]

    P = []
    for p, y, xf, xr, s in jacks(c):
        a, b_ = sorted((xf, xr))
        j = bx(a, b_, y - c['rj_w'] / 2, y + c['rj_w'] / 2, zt, zt + c['rj_h'])
        m0, m1 = (xf - 1, xf + 12) if s < 0 else (xf - 12, xf + 1)
        j = cut(j, bx(m0, m1, y - c['rj_mouth_w'] / 2, y + c['rj_mouth_w'] / 2, zt + c['rj_mouth'][0], zt + c['rj_mouth'][1]))
        P.append(('RJ12 %d jack' % p, j))
        t0, t1 = (xr - 3.6, xr + 0.6) if s < 0 else (xr - 0.6, xr + 3.6)
        P.append(('RJ12 %d tails' % p, bx(t0, t1, y - 3.8, y + 3.8, zb - c['rj_tail'], zb)))
    P.append(('USB-C socket', bx(c['usb_in'], c['usb_in'] + ul, uy - uw / 2, uy + uw / 2, zt, zt + uh)))
    P.append(('Solar jack', bx(ia - c['sol_nose'], ia - c['sol_nose'] + sl, sy - sw / 2, sy + sw / 2, zt, zt + sh)))
    bw, bl, bh = c['btn'][1:]
    P.append(('Reset button', uni(bx(x0 + 1.0, x0 + 1.0 + bl, ry - bw / 2, ry + bw / 2, zt, zt + bh),
                                  cyl((ia + 0.3, ry, zt + c['btn_axis']), (x0 + 1.0, ry, zt + c['btn_axis']), 0.9))))
    # ESP32-C6 on sockets: socket strips, spacers, board, pin tips
    ex0, ex1 = x0 + c['esp_by'], x0 + c['esp_by'] + c['esp_l']
    for r in c['esp_rows']:
        _, yr = K(r, 0, c)
        P.append(('ESP socket %.0f' % r, bx(ex0 + 0.3, ex1 - 0.3, yr - 1.27, yr + 1.27, zt, zt + c['sock_h'])))
        P.append(('ESP spacer %.0f' % r, bx(ex0 + 0.3, ex1 - 0.3, yr - 1.27, yr + 1.27, zt + c['sock_h'], c['esp_z0'])))
        P.append(('ESP pin tips %.0f' % r, bx(ex0 + 1.2, ex1 - 1.2, yr - 0.4, yr + 0.4, c['esp_z0'] + c['esp_t'], c['esp_z0'] + c['esp_t'] + c['esp_tip'])))
    _, eyc = K(c['esp_bx'], 0, c)
    P.append(('ESP32-C6 board', bx(ex0, ex1, eyc - c['esp_w'] / 2, eyc + c['esp_w'] / 2, c['esp_z0'], c['esp_z0'] + c['esp_t'])))
    cx_, cy_ = K(c['cap'][0], c['cap'][1], c)
    P.append(('C 470uF', cyl((cx_, cy_, zt + 0.5), (cx_, cy_, zt + 0.5 + c['cap'][3]), c['cap'][2])))
    # the bay past the cell: three port fuses standing on the room side, the cell fuse and the battery header on the back side
    ft, fl, fh = c['fuse']
    for n in range(3):
        fx, fy = K(11.5 + n * 3.8, c['bar_end'] - 7.0, c)
        P.append(('Port fuse %d' % (n + 1), bx(fx - fl / 2, fx + fl / 2, fy - ft / 2, fy + ft / 2, zt, zt + fh)))
    cl, ct_, ch = c['fuse_cell']
    fx, fy = K(35.5, c['bar_end'] - 3.6, c)
    P.append(('Cell fuse', bx(fx - ct_ / 2, fx + ct_ / 2, fy - cl / 2, fy + cl / 2, zt, zt + ch)))
    hx_, hy_ = K(43.0, c['bar_end'] - 9.4, c)                                # JST-XH 2-pin header (5.75 x 7.4 x 7.0)
    P.append(('JST-XH header', bx(hx_ - 2.9, hx_ + 2.9, hy_ - 3.7, hy_ + 3.7, zt, zt + 7.0)))
    # the cell at its nominal length, its + end on the button
    P.append(('18650 cell', cyl((c['bat_x0'], by, bc), (c['bat_x0'] + c['bat_l'], by, bc), c['bat_d'] / 2)))
    # the contacts, from the catalog drawing: plate on the L line, base behind it, two legs; the 596's button; the
    # 590's leaf drawn pressed back by the nominal cell (its bend sits lower the harder it is pressed)
    for k, cxh in enumerate(c['ct_x']):
        s = 1 if k == 0 else -1                                             # toward the cell
        top = c['ct_h'] if k == 0 else c['ct_fold']
        body = uni(bx(cxh - c['ct_t'] / 2, cxh + c['ct_t'] / 2, by - c['ct_w'] / 2, by + c['ct_w'] / 2, zt, zt + top),
                   bx(*sorted((cxh, cxh - s * c['ct_base'])), by - c['ct_w'] / 2, by + c['ct_w'] / 2, zt, zt + c['ct_t']))
        for lx, ly in legs(cxh, s):
            body = uni(body, bx(lx - 0.4, lx + 0.4, ly - 0.4, ly + 0.4, zb - 2.2, zt + 0.1))
        if k == 0:
            body = uni(body, cyl((cxh, by, zt + c['btn_z']), (cxh + c['ct_t'] / 2 + c['btn_proud'], by, zt + c['btn_z']), c['btn_d'] / 2))
            P.append(('Cell contact + (596)', body))
        else:
            sq = leaf_squeeze(c['bat_l'], c)
            zc = zt + c['leaf_z'][0] + (c['leaf_z'][1] - c['leaf_z'][0]) * max(min(sq / 3.0, 1.0), 0.0)
            tip = cxh - c['ct_t'] / 2 - (c['leaf_reach'] - max(sq, 0.0))     # where the leaf's bend is now
            body = uni(body, bx(tip, cxh, by - c['leaf_w'] / 2, by + c['leaf_w'] / 2, zc - 0.4, zc + 0.4))
            P.append(('Cell contact - (590)', body))
    out['Parts'] = P
    out['Screws'] = [('M3x%.0f %d' % (c['screw_l'], k), uni(cone((x, y, c['floor_z']), 2.95, (x, y, c['floor_z'] + 1.6), 1.45),
                                                          cyl((x, y, c['floor_z'] + 1.55), (x, y, c['floor_z'] + c['screw_l']), 1.45)))
                     for k, (x, y) in enumerate(HOLES)]
    # plugs: the charge cable's USB-C plug (12.4 x 6.5 overmold, stops 1.85 before the socket's mouth), the solar plug
    # (dia 8 body, dia 3.5 barrel), and a cable in the ESP's own USB-C (lid off: flashing)
    pw, ph, pl = c['esp_plug']
    ez = c['esp_z0'] + c['esp_t'] + 1.6
    out['Plugs'] = [('USB-C plug', uni(bx(-18, c['usb_in'] - 1.85, uy - 6.2, uy + 6.2, zt + uh / 2 - 3.25, zt + uh / 2 + 3.25),
                                       bx(c['usb_in'] - 1.85, c['usb_in'] + 5.4, uy - 4.1, uy + 4.1, zt + uh / 2 - 1.2, zt + uh / 2 + 1.2))),
                    ('Solar plug', uni(cyl((-22, sy, zt + c['sol_axis']), (-0.3, sy, zt + c['sol_axis']), 4.0),
                                       cyl((-0.3, sy, zt + c['sol_axis']), (ia + 6.0, sy, zt + c['sol_axis']), 1.75))),
                    ('ESP flashing plug', bx(ex1 + 0.5, ex1 + 0.5 + pl, eyc - pw / 2, eyc + pw / 2, ez - ph / 2, ez + ph / 2))]
    return out
