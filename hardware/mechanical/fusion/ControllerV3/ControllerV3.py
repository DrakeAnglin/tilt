"""Fit study for the controller PCB v3 (docs/pcb-v3-concept.md): the board with every part on it, the cell, its contacts
and the box, before the board is drawn in KiCad. Not a print file yet: the board here is a mock-up (its outline and a
body for every part at a place that can be routed), not a KiCad export.

Layout, end A to end B:
  * End A wall: port 1's RJ12 jack, the reset button, the solar jack and the USB-C socket. The jack and the solar jack
    hang over the board's edge and stop flush with the wall's outer face; the USB-C socket's mouth is 0.7 inside it
    (as far as its shell stakes allow); the button stands 0.4 proud.
  * The 18650 lies in the board's notch along the back wall, on two tray saddles, between a Keystone 596 button
    contact (+, fixed) and a Keystone 590 leaf contact (-, sprung) that stand on the board at the notch's ends.
    The cell sets the board's length.
  * Beside the cell, on the room side: the ESP32-C6 on sockets (small parts under it), then the ports' parts, the
    fuses, the 470 uF and the battery header.
  * Ports 2 and 3 are on an end section joined by a 10 mm neck, one jack each side of the rod's groove; their jacks
    come through end wall B. PORTS = 1 builds the short box for a board with the end section sawn off.
  * The box stands on four 2 mm foam pads (the blind's lift cords run under it), so its floor is 2 mm above the
    rail's. The rod's groove is where the v2.2 box has it, measured from the rail: same center, floor height, radius.

The tray's walls stop at the top of the jacks; each jack sits in a slot that is open upward and the lid's rim closes
it. Putting the board in needs no tilt: it is lowered flat, 1.5 mm toward end B (the jacks there stand out through
their slots meanwhile), then slid home so the USB-C socket and the solar jack enter their windows in end wall A. The
screws then hold it there. The Fusion driver walks that path backwards as a check, with 0.15 mm to spare.

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
        # four stick-on foam pads under the floor (hardware/BOM.md): dia 10, 2 thick, their centers this far in
        pad_d=10.0, pad_t=2.0, pad_in=(10.0, 10.5),
        # the v2.2 box's section: width, height, walls (Controller.py). The floor is one pad above the rail's floor, and
        # the top bevel is 3.5 (v2.2: 3.0) so the box, 2 mm higher on its pads, still tilts in past the rail's lips
        room_out=-27.4, back_in=22.4, height=23.0, wall=2.0, floor=1.2, lid=2.0, end_t=1.6, corner_r=4.0,
        bevel_bot=2.6, bevel_top=3.5, bevel_fill=1.8, lid_fill=2.0, lip_t=1.2, lip_h=1.5,
        # rod groove: exactly the v2.2 box's, from the rail's floor: r 5, its floor 1.8 under the rod's corners, channel 1.1
        groove_r=5.0, groove_floor=FIT.ROD_Z - FIT.ROD_CORNER_R - 1.8, groove_t=1.1,
        # board: 2.4 above the floor (RJ12 tails), 1.6 thick, 47 wide, 0.3 off each end wall, corners rounded 2.0
        pcb_gap=2.4, pcb_t=1.6, pcb_y=-25.0, pcb_w=47.0, pcb_body=27.0, pcb_r=2.0, end_gap=0.3,
        # at end B the gap is 1.8: the board is lowered flat, 1.5 toward end B, then slid home into end wall A's openings
        end_gap_b=1.8,
        neck=(18.5, 28.5, 3.0),       # the neck: bx from, to; length
        tab_len=15.1,                 # the end section
        # RJ12 Amphenol 87180-066LF: 13.25 W x 11.5 H, 16.77 deep; its front 0.3 inside the wall's outer face
        # (flush to the eye, and never proud whatever the parts' tolerances)
        rj_w=13.25, rj_h=11.5, rj_d=16.77, rj_recess=0.3, rj_bx=(8.6, 8.6, 38.4), rj_mouth_w=9.65, rj_mouth=(1.73, 8.50),
        jack_clear=0.2, jack_clear_top=0.25, jack_clear_bot=0.15, rj_tail=2.1,
        # every opening is tight for its outer 0.8 mm (two lines of a 0.4 nozzle) and 0.5 wider behind that, inside the
        # wall: it looks tight, and a part a little out of square still goes in
        win_lip=0.8, win_flare=0.5,
        # USB-C GCT USB4125: 8.94 x 6.8 x 3.16, a rounded shell. Its front stakes are 2.6 behind the mouth (pads 1.7
        # long), so the board's edge can be 1.2 behind the mouth at most: the mouth is 0.7 inside the wall's face.
        # A plug's overmold stops 1.85 before the mouth (GCT's mating view): 1.15 outside the wall
        usb=(40.6, 8.94, 6.8, 3.16), usb_in=0.7, usb_clear=0.15,
        # solar jack Same Sky PJ-007 (3.5 x 1.35 plug): 5.0 wide, 11.1 long, 7.4 high (its rear 3.7 is 5.5 high),
        # barrel axis 4.7 above the board, pins 6.0 / 8.3 / 10.9 behind its face (the 8.3 one 2.8 off the axis); its face
        # 0.3 inside the wall's face. Its size is +-0.2, so its window is 0.25 clear
        sol=(29.25, 5.0, 11.1, 7.4), sol_axis=4.7, sol_in=0.3, sol_clear=0.25,
        # reset button C&K PTS645VL39 (right-angle): actuator dia 3.5, its tip 3.85 in front of the front leads and
        # 4.05 above the board; body 4.2 deep behind the leads, 7.5 wide (8.5 over its frame legs), 7.3 high. It is all
        # inside the box: its tip stops 0.3 behind the wall, and a dia 2.2 hole lets a pin or a paper clip reach it
        btn=(21.0, 7.5, 4.2, 7.3), btn_frame=8.5, btn_axis=4.05, btn_d=3.5, btn_reach=3.85, btn_gap=0.3, btn_hole_r=1.1,
        # ESP32-C6 SuperMini (26 x 18 taken; to measure) on 8.59 sockets + 2.5 spacers; rows 15.24 apart, on the
        # room side clear of the groove's channel; its USB-C faces end B, with a clear corridor for a cable (lid off)
        esp_l=26.0, esp_w=18.0, esp_t=1.0, esp_by=20.0, sock_h=8.59, spacer=2.5, esp_tip=1.9, esp_rows=(2.2, 17.44),
        esp_plug=(12.4, 6.5, 26.0),   # a USB-C plug's overmold: width, height, length (the cable bends up: the lid is off)
        # 18650 in the notch, where it lies in the v2.2 box. This box takes protected button-top cells of 68 to 70 mm
        bat_d=19.0, bat_l=69.0, bat_lmin=68.0, bat_lmax=70.0, bat_up=0.5,
        # the cell's tray: a trough under the whole cell and a matching one in the lid, with + and - sunk into its floor
        cradle_t=1.5, cradle_y0=2.6, cradle_lid_y0=4.6, cradle_end=1.0, cradle_low=4.0, mark=7.0, mark_w=1.6,
        # Keystone 596 (+ button) and 590 (- leaf), catalog M65 p11 and p35. Both: plate 9.1 wide x 11.4 high on the "L"
        # line, base 6.3 deep behind it, a center leg on the L line (clipped off here) and two legs 3.0 behind it, 8.9
        # apart, in dia 1.3 holes. 596: button dia 6.4, center 7.0 above the board, about 0.2 proud of the plate.
        # 590: leaf 5.1 wide, 4.1 free reach, its contact bend about 6.2 above the board free and 5.0 fully pressed
        # (scaled from the drawing); its top fold stands about 12.5 high. L = cell + 2.3 (p35: AA 50.3 -> 52.6)
        ct_w=9.1, ct_h=11.4, ct_fold=12.5, ct_base=6.3, ct_t=0.3, ct_leg_back=3.0, ct_leg_span=8.9,
        ct_btn_d=6.4, ct_btn_z=7.0, ct_btn_proud=0.2, leaf_w=5.1, leaf_reach=4.1, leaf_z=(6.2, 5.0), ct_l_extra=2.3, ct_by0=13.1,
        ct_edge=0.5,                  # the notch starts this far behind each plate (the cell's end must not meet the board)
        boss_d=7.0, post_d=7.0, screw_l=10.0,
        pull_r=7.0,                   # finger notch in the back wall beside the cell (a tab on the lid fills it)
        # fuses standing, through-hole (Bourns says not to hand-solder its surface-mount ones). Per port a Bourns
        # MF-R110 (1.1 A, 30 V): 3.0 thick, 8.9 wide, 14.0 high at most. For the cell a Bourns MF-RG400 (4 A, 16 V,
        # 2.8 A at 60 C): 9.9 wide, 3.0 thick, 12.8 high at most
        fuse=(3.0, 8.9, 14.0), fuse_cell=(9.9, 3.0, 12.8),
    )
    c['floor_z'] = c['pad_t']
    c['top'] = c['floor_z'] + c['height']
    c['iw_lo'] = c['room_out'] + c['wall']
    c['iw_hi'] = c['back_in']
    c['out_hi'] = c['back_in'] + c['wall']
    c['groove_y'] = (c['room_out'] + c['out_hi']) / 2
    c['g_zc'] = c['groove_floor'] + c['groove_r']
    c['fz'] = c['floor_z'] + c['floor']
    c['zl'] = c['top'] - c['lid']
    c['zb'] = c['fz'] + c['pcb_gap']
    c['zt'] = c['zb'] + c['pcb_t']
    c['zs'] = c['zt'] + c['rj_h'] + c['jack_clear_top']      # where tray and lid meet: just over the jacks' tops
    c['pcb_x'] = c['end_t'] + c['end_gap']
    c['ct_span'] = c['bat_l'] + c['ct_l_extra']
    c['ct_x'] = (c['pcb_x'] + c['ct_by0'], c['pcb_x'] + c['ct_by0'] + c['ct_span'])      # the two contacts' L lines
    c['notch'] = (c['ct_by0'] - c['ct_edge'], c['ct_by0'] + c['ct_span'] + c['ct_edge'])
    c['main_len'] = c['ct_by0'] + c['ct_span'] + c['ct_base'] + 0.4                      # the cell sets the board's length
    c['pcb_len'] = c['main_len'] + (c['neck'][2] + c['tab_len'] if ports > 1 else 0.0)
    c['L'] = c['pcb_x'] + c['pcb_len'] + c['end_gap_b'] + c['end_t']
    c['ia'], c['in_b'] = c['end_t'], c['L'] - c['end_t']
    c['bat_y'] = c['iw_hi'] - 0.3 - c['bat_d'] / 2
    c['bat_zc'] = c['fz'] + c['bat_up'] + c['bat_d'] / 2
    c['bat_x1'] = c['ct_x'][1] - c['ct_t'] / 2 - c['ct_btn_proud']       # the cell's + end rests on the button, at end B
    c['bat_x0'] = c['bat_x1'] - c['bat_l']
    c['btn_tip'] = c['end_t'] + c['btn_gap']
    c['esp_bx'] = sum(c['esp_rows']) / 2
    c['esp_z0'] = c['zt'] + c['sock_h'] + c['spacer']
    # screw holes (bx, by): one line down the middle, under the rod's groove (the pads take the corners). Three on the
    # main board; the end section has its own, between its jacks, so a cord pushed in there does not lever on the neck
    c['holes'] = ((23.5, 12.8), (23.5, 86.0), (23.5, 46.0))
    c['hole_tab'] = (23.5, c['main_len'] + c['neck'][2] + c['tab_len'] / 2)
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


def pads(c=None):
    """Centers (X, Y) of the four foam pads under the floor."""
    c = c or C
    ex, ey = c['pad_in']
    return [(x, y) for x in (ex, c['L'] - ex) for y in (c['room_out'] + ey, c['out_hi'] - ey)]


def leaf_squeeze(cell_len, c=None):
    """How far a cell of this length presses the 590's leaf back (mm): the + end rests on the 596's button, at end B."""
    c = c or C
    free_tip = c['ct_x'][0] + c['ct_t'] / 2 + c['leaf_reach']
    return free_tip - (c['bat_x1'] - cell_len)


def room_under_lid(y, c=None):
    """Height of the lid's underside (the groove's channel or the lid's corner fill, where lower) above the board's
    top at box Y = y."""
    c = c or C
    fill = min(y - c['iw_lo'], c['iw_hi'] - y)             # the 45 deg fill in the lid's two long top corners
    z = min(c['zl'], z_under(y, c['groove_t'], c), c['zl'] - c['lid_fill'] + max(fill, 0.0))
    return z - c['zt']


# ---------------------------------------------------------------------------------------------- the parts on the board
# Footprints are courtyards: the part with its solder pads and the room an iron needs. Two courtyards may touch.
S0805 = (1.9, 3.7, 0.6)       # a hand-solder 0805: across, along (pad to pad), high
S1206 = (2.3, 4.9, 1.6)       # a 10 or 22 uF capacitor, hand-solder 1206
SOT23 = (3.6, 4.4, 1.3)       # SOT-23, SOT-23-5 and -6 with their legs' pads
DO41 = (3.0, 12.4, 2.7)       # lying, legs 10.16 apart, dia 2 pads
PR02 = (4.2, 17.2, 3.9)       # Vishay PR02 2 W: body dia 3.9 x 10 (12 over its caps), legs 15 apart
DO201 = (5.4, 18.0, 5.3)      # 1N5822 lying: body dia 5.3 x 9.5, legs 15.24 apart, dia 2.6 pads


def _p(name, bx0, by0, size=S0805, along='y', shape='smd'):
    """A part whose long side runs along the board ('y') or across it ('x')."""
    s, l, h = size
    return (name, bx0, bx0 + (s if along == 'y' else l), by0, by0 + (l if along == 'y' else s), h, shape)


def _port_block(n, bx0, by0):
    """A port's parts that stay by the ESP, in an 8.1 x 17.2 block: the 6.8 ohm 2 W resistor, the switch and the
    four small parts round it."""
    out = [_p('P%d R 6.8R 2W' % n, bx0, by0, PR02, shape='axial'), _p('P%d switch AO3401A' % n, bx0 + 4.3, by0, SOT23, shape='chip')]
    names = ['R gate', 'R pull-up', 'C gate', 'C angle 100n']
    slots = [(bx0 + r, by0 + k) for k in (4.6, 8.4) for r in (4.3, 6.2)]
    return out + [_p('P%d %s' % (n, nm), sx, sy) for nm, (sx, sy) in zip(names, slots)]


JACK_SIDE = ['C IN1 10n', 'C IN2 10n', 'C EN 100n', 'R IN1 220', 'R IN2 220', 'R angle 1k']     # the parts that sit by a port's jack


def comps(c=None):
    """Every small part on the board: (name, bx0, bx1, by0, by1, height, shape). Connectors, the ESP, the contacts and
    the cell are built in build() from their own numbers; their footprints are in keepouts(). Ports 2 and 3's parts
    are left off the one-port board."""
    c = c or C
    out = []
    e0, e1 = c['esp_by'], c['esp_by'] + c['esp_l']
    # --- port 1's static capacitors and series resistors, right behind its jack
    out += [_p('P1 %s' % nm, 1.0 + 3.9 * (k % 3), 15.9 + 2.1 * (k // 3), along='x') for k, nm in enumerate(JACK_SIDE)]
    # --- between the ESP's two sockets (soldered before the sockets): the charger in the middle, 4 mm from either
    # socket, its copper on the board's underside; the regulator; the sense dividers
    u1 = _p('U1 charger BQ21040', 7.9, e0 + 0.6, SOT23, shape='chip')
    u2 = _p('U2 regulator RT9080', 7.9, e0 + 15.4, SOT23, shape='chip')
    c10 = _p('C 10u (regulator in)', 4.1, e0 + 15.4, S1206)
    c22 = _p('C 22u (regulator out)', 11.7, e0 + 15.4, S1206)
    out += [u1, u2, c10, c22]
    taken = [p[1:5] for p in (u1, u2, c10, c22)]
    names = ['R ISET 1k', 'C charger in 1u', None, None, 'C charger out 1u', 'R TS 1.0k', 'R TS 237k', None,     # round the charger
             'R USB sense 390', 'R USB sense 620', 'R USB sense 10k', 'R solar sense a', 'R solar sense b', 'R charge light',
             'R cell sense 1M a', 'R cell sense 1M b', 'C cell sense 100n', 'Charge light', None, None,
             'R EN pull-up', 'C EN']
    slots = []
    for k in range(7):
        for r in range(6):
            sx, sy = 4.1 + 1.9 * r, e0 + 0.6 + 3.7 * k
            if not any(sx < t[1] - 1e-6 and sx + S0805[0] > t[0] + 1e-6 and sy < t[3] - 1e-6 and sy + S0805[1] > t[2] + 1e-6 for t in taken):
                slots.append((sx, sy))
    assert len(slots) >= len(names), 'no room between the sockets for %d parts' % len(names)
    out += [_p(nm, sx, sy) for nm, (sx, sy) in zip(names, slots) if nm]
    # --- beside the ESP, under the groove: the three input diodes and the place for a fourth
    for nm, b0, y0 in (('D USB 1N5817', 19.2, 16.5), ('D solar 1 1N4001', 23.4, 16.5), ('D solar 2 1N4001', 23.4, 29.3), ('D solar 3 (place)', 19.2, 29.3)):
        out.append(_p(nm, b0, y0, DO41, shape='axial'))
    # --- by the USB-C socket: its two 5.1 k resistors
    out += [_p('R CC1 5.1k', 31.9, 0.5, along='x'), _p('R CC2 5.1k', 31.9, 2.7, along='x')]
    # --- past the ESP: the port fuses standing along the room-side edge, one block per port
    ft, fl, fh = c['fuse']
    for n, (b0, y0) in enumerate(((3.8, e1 + 0.6), (11.9, e1 + 0.6), (3.8, e1 + 18.0)), 1):
        if n == 1 or c['ports'] > 1:
            fy = e1 + 1.0 + (n - 1) * (fl + 0.6)
            out.append(('P%d fuse MF-R110' % n, 0.4, 0.4 + ft, fy, fy + fl, fh, 'box'))
            out += _port_block(n, b0, y0)
    # --- ports 2 and 3's static capacitors and series resistors: on the end section, between its two jacks
    if c['ports'] > 1:
        s0 = c['main_len'] + c['neck'][2] + 0.5
        for n, b0 in ((2, 15.6), (3, 27.6)):
            out += [_p('P%d %s' % (n, nm), b0 + 1.9 * (k % 2), s0 + 3.8 * (k // 2)) for k, nm in enumerate(JACK_SIDE)]
    # --- the battery line, at the + contact's end: fuse, backwards-cell diode, 470 uF; the header for a cell with a
    # lead; the temperature sensor by the cell, well away from the charger and the input diodes
    cl, ct_, ch = c['fuse_cell']
    out += [('F cell fuse MF-RG400', 12.2, 12.2 + ct_, 72.9, 72.9 + cl, ch, 'box'),
            _p('D backwards cell 1N5822', 21.2, 62.7, DO201, shape='axial'),
            ('C 470uF', 3.9, 11.9, 82.3, 90.3, 11.5, 'radial'),
            ('JST-XH header', 12.2, 18.4, 64.2, 72.2, 7.0, 'box'),              # clear of the groove: its plug stands 10 high
            ('Temperature sensor NTC', 24.6, 26.6, 58.0, 62.5, 6.0, 'box')]           # its bead is bent over to touch the cell
    return out


def keepouts(c=None):
    """Footprints of the big parts and the lid's posts on the board: (name, bx0, bx1, by0, by1)."""
    c = c or C
    out = []
    px = c['pcb_x']
    for p, y, xf, xr, s in jacks(c):
        a, b = sorted((xf, xr))
        out.append(('RJ12 %d' % p, y - c['pcb_y'] - c['rj_w'] / 2, y - c['pcb_y'] + c['rj_w'] / 2, a - px - (0.0 if s < 0 else 0.6), b - px + (0.6 if s < 0 else 0.0)))
    ux, uw, ul, uh = c['usb']
    out.append(('USB-C socket', ux - uw / 2 - 0.3, ux + uw / 2 + 0.3, c['usb_in'] - px, c['usb_in'] - px + ul + 0.9))
    sx, sw, sl, sh = c['sol']
    f0 = c['sol_in'] - px
    out.append(('Solar jack', sx - sw / 2, sx + sw / 2, f0, f0 + sl + 0.4))
    out.append(('Solar jack pin 3', sx - 2.8 - 1.0, sx - 2.8 + 1.0, f0 + 8.3 - 1.0, f0 + 8.3 + 1.0))       # 2.8 off the axis, toward the room side
    b_, bw, bl, bh = c['btn']
    lead = c['btn_tip'] + c['btn_reach'] - px
    out.append(('Reset button', b_ - c['btn_frame'] / 2, b_ + c['btn_frame'] / 2, c['btn_tip'] - px, lead + bl + 1.0))
    yb = c['bat_y'] - c['pcb_y']
    e_ = c['ct_by0'] + c['ct_span']
    out.append(('Cell contact - (590)', yb - c['ct_w'] / 2, yb + c['ct_w'] / 2, c['ct_by0'] - c['ct_base'], c['ct_by0'] + 0.2))
    out.append(('Cell contact + (596)', yb - c['ct_w'] / 2, yb + c['ct_w'] / 2, e_ - 0.2, e_ + c['ct_base']))
    for r in c['esp_rows']:
        out.append(('ESP socket %.0f' % r, r - 1.27, r + 1.27, c['esp_by'] + 0.3, c['esp_by'] + c['esp_l'] - 0.3))
    hs = list(c['holes']) + ([c['hole_tab']] if c['ports'] > 1 else [])
    for k, (hx, hy) in enumerate(hs):
        out.append(('Post %d' % (k + 1), hx - c['post_d'] / 2, hx + c['post_d'] / 2, hy - c['post_d'] / 2, hy + c['post_d'] / 2))
    return out


def on_board(bx0, bx1, by0, by1, c=None, edge=0.3):
    """True if the rectangle is on the board, `edge` clear of its outline."""
    c = c or C
    n0, n1 = c['notch']

    def inside(x, y):
        if 0 <= y <= c['main_len']:
            return 0 <= x <= (c['pcb_body'] if n0 < y < n1 else c['pcb_w'])
        if c['ports'] > 1 and y <= c['main_len'] + c['neck'][2]:
            return c['neck'][0] <= x <= c['neck'][1]
        return c['ports'] > 1 and y <= c['pcb_len'] and 0 <= x <= c['pcb_w']
    pts = [(x, y) for x in (bx0 - edge, (bx0 + bx1) / 2, bx1 + edge) for y in (by0 - edge, (by0 + by1) / 2, by1 + edge)]
    return all(inside(x, y) for x, y in pts)


def _hit(a, b, gap=0.0):
    """Do two footprints (name, bx0, bx1, by0, by1, ...) overlap? A lid post and a 470 uF are round."""
    ra, rb = a[0].startswith(('Post', 'C 470uF')), b[0].startswith(('Post', 'C 470uF'))
    if ra and not rb:
        a, b, ra, rb = b, a, rb, ra
    if rb:
        qx, qy, r = (b[1] + b[2]) / 2, (b[3] + b[4]) / 2, (b[2] - b[1]) / 2
        if ra:
            return math.hypot(qx - (a[1] + a[2]) / 2, qy - (a[3] + a[4]) / 2) < r + (a[2] - a[1]) / 2 + gap - 1e-9
        return math.hypot(qx - min(max(qx, a[1]), a[2]), qy - min(max(qy, a[3]), a[4])) < r + gap - 1e-9
    return a[1] < b[2] + gap - 1e-9 and a[2] > b[1] - gap + 1e-9 and a[3] < b[4] + gap - 1e-9 and a[4] > b[3] - gap + 1e-9


def layout_problems(c=None):
    """What is wrong with the parts' places, without Fusion: off the board, on top of each other, or too tall for the
    room above them. An empty list means the mock-up can be built."""
    c = c or C
    bad = []
    cs = comps(c)
    ks = keepouts(c)
    e0, e1 = c['esp_by'], c['esp_by'] + c['esp_l']
    er0, er1 = c['esp_bx'] - c['esp_w'] / 2, c['esp_bx'] + c['esp_w'] / 2
    pw, ph, pl = c['esp_plug']
    plug_low = c['esp_z0'] + c['esp_t'] + 1.6 - ph / 2 - c['zt']             # underside of a cable plugged into the ESP
    for i, a in enumerate(cs):
        nm, x0, x1, y0, y1, h, _ = a
        if not on_board(x0, x1, y0, y1, c):
            bad.append('%s is off the board' % nm)
        bad += ['%s overlaps %s' % (nm, b[0]) for b in cs[i + 1:] if _hit(a, b)]
        bad += ['%s is under %s' % (nm, k[0]) for k in ks if _hit(a, k)]
        room = min(room_under_lid(c['pcb_y'] + x, c) for x in (x0, (x0 + x1) / 2, x1)) - 0.5
        if x0 < er1 and x1 > er0 and y0 < e1 and y1 > e0:
            room = min(room, c['sock_h'] + c['spacer'] - 0.5)                 # under the ESP
        if x0 < c['esp_bx'] + pw / 2 + 0.2 and x1 > c['esp_bx'] - pw / 2 - 0.2 and e1 <= y1 and y0 < e1 + pl + 0.7:
            room = min(room, plug_low - 0.5)                                  # under a cable in the ESP's USB-C
        if h > room:
            bad.append('%s is %.1f high, room %.1f' % (nm, h, room))
    for i, a in enumerate(ks):                                                # the big parts against each other
        for b in ks[i + 1:]:
            if a[0][:10] != b[0][:10] and _hit(a, b):
                bad.append('%s overlaps %s' % (a[0], b[0]))
    return bad


def facts(c=None):
    """The numbers the fit depends on, worked out without Fusion (also used by the tests)."""
    c = c or C
    zt, zl = c['zt'], c['zl']
    f = {}
    f['box'] = (round(c['L'], 1), round(c['out_hi'] - c['room_out'], 1), c['height'])
    f['board_len'] = round(c['pcb_len'], 1)
    f['parts_on_board'] = len(comps(c))
    f['floor_above_rail'] = c['floor_z']
    f['rod_corners_to_groove'] = round(FIT.ROD_Z - FIT.ROD_CORNER_R - c['groove_floor'], 2)
    f['cell_top_to_lid'] = round(zl - (c['bat_zc'] + c['bat_d'] / 2), 2)
    f['cell_to_groove_channel'] = round(
        math.hypot(c['bat_y'] - c['groove_y'], c['bat_zc'] - c['g_zc']) - c['bat_d'] / 2 - (c['groove_r'] + c['groove_t']), 2)
    f['cell_to_board_edge'] = round((c['bat_y'] - c['bat_d'] / 2) - (c['pcb_y'] + c['pcb_body']), 2)
    f['cell_axis_above_board'] = round(c['bat_zc'] - zt, 2)
    f['button_above_cell_axis'] = round(zt + c['ct_btn_z'] - c['bat_zc'], 2)
    f['leaf_above_cell_axis'] = tuple(round(zt + z - c['bat_zc'], 2) for z in c['leaf_z'])
    f['leaf_squeeze'] = {ln: round(leaf_squeeze(ln, c), 2) for ln in (c['bat_lmin'], c['bat_l'], c['bat_lmax'])}
    f['leaf_reach'] = c['leaf_reach']
    f['cell_ends_inside_notch'] = (round(c['bat_x1'] - c['bat_lmax'] - (c['pcb_x'] + c['notch'][0]), 2),
                                   round((c['pcb_x'] + c['notch'][1]) - c['bat_x1'], 2))
    f['contact_top_to_lid'] = round(room_under_lid(c['bat_y'], c) - c['ct_fold'], 2)
    f['contact_legs_to_floor'] = round(c['pcb_gap'] - (3.8 - c['pcb_t']), 2)              # the legs are 3.8 long
    f['lid_under_groove'] = c['groove_t']
    tip = c['sock_h'] + c['spacer'] + c['esp_t'] + c['esp_tip']
    f['esp_tips_to_lid'] = round(min(room_under_lid(K(r, 0, c)[1] + d, c) - tip for r in c['esp_rows'] for d in (-0.4, 0.4)), 2)
    f['jack_top_to_seam'] = round(c['zs'] - (zt + c['rj_h']), 2)
    f['jack_to_groove_channel'] = round(min(z_under(y + s * c['rj_w'] / 2, c['groove_t'], c) - (zt + c['rj_h']) for _, y, _, _, _ in jacks(c) for s in (-1, 1)), 2)
    f['fronts_behind_wall_face'] = {'RJ12': c['rj_recess'], 'solar': c['sol_in'], 'USB-C': c['usb_in'], 'button': c['btn_tip']}
    ys = {'jack 1': jacks(c)[0][1], 'button': K(c['btn'][0], 0, c)[1], 'solar': K(c['sol'][0], 0, c)[1], 'USB-C': K(c['usb'][0], 0, c)[1]}
    hw = {'jack 1': c['rj_w'] / 2 + c['jack_clear'], 'button': c['btn_hole_r'], 'solar': c['sol'][1] / 2 + c['sol_clear'], 'USB-C': c['usb'][1] / 2 + c['usb_clear']}
    order = sorted(ys, key=ys.get)
    f['end_a_webs'] = {'%s | %s' % (a, b): round(ys[b] - hw[b] - ys[a] - hw[a], 2) for a, b in zip(order, order[1:])}
    f['solar_plug_max_dia'] = round(2 * min(ys['USB-C'] - 6.2 - ys['solar'], ys['solar'] - ys['button'] - c['btn_hole_r']) - 0.4, 1)   # beside a USB-C plug 12.4 wide
    f['usb_board_edge_behind_mouth'] = round(c['pcb_x'] - c['usb_in'], 2)
    f['groove'] = (c['groove_y'], round(c['groove_floor'], 2), c['groove_r'], c['groove_t'])
    return f


def outline_pts(c=None):
    """The box's cross-section (Y, Z), with its four 45 deg bevels: for the tilt-in check."""
    c = c or C
    lo, hi, z0, z1, bb, bt = c['room_out'], c['out_hi'], c['floor_z'], c['top'], c['bevel_bot'], c['bevel_top']
    return [(lo + bb, z0), (hi - bb, z0), (hi, z0 + bb), (hi, z1 - bt), (hi - bt, z1), (lo + bt, z1), (lo, z1 - bt), (lo, z0 + bb)]


def tilt_pieces(c=None):
    """The box's cross-section and its pads' (taken as hard), centered on the rail: for Controller/tilt_in.py."""
    c = c or C
    m = c['groove_y']
    pcs = [[(y - m, z) for y, z in outline_pts(c)]]
    for y in sorted(set(p[1] for p in pads(c))):
        pcs.append([(y - m - c['pad_d'] / 2, 0.0), (y - m + c['pad_d'] / 2, 0.0), (y - m + c['pad_d'] / 2, c['pad_t'] + 0.1), (y - m - c['pad_d'] / 2, c['pad_t'] + 0.1)])
    return pcs


def build(bx, cyl, cone, uni, cut, rbox, obox, c=None):
    """{group: [(name, body)]}; the same helper functions as Controller.build."""
    c = c or C
    ilo, ihi, fz, zl, zb, zt, zs = c['iw_lo'], c['iw_hi'], c['fz'], c['zl'], c['zb'], c['zt'], c['zs']
    olo, ohi, L, ia, in_b = c['room_out'], c['out_hi'], c['L'], c['ia'], c['in_b']
    gy = c['groove_y']
    ri = c['corner_r'] - c['wall']
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
        """A rounded slot along X: half width hw, half height hh, centered (y, zc)."""
        r = min(hw, hh)
        a = bx(x0, x1, y - hw + r, y + hw - r, zc - hh, zc + hh)
        for yy in (y - hw + r, y + hw - r):
            a = uni(a, cyl((x0, yy, zc), (x1, yy, zc), r))
        return a

    jw = c['rj_w'] / 2 + c['jack_clear']
    jz0 = zt - c['jack_clear_bot']
    wl, wf = c['win_lip'], c['win_flare']
    HOLES = holes(c)
    by, bc, rc = c['bat_y'], c['bat_zc'], c['bat_d'] / 2 + 0.2
    bat_xc = c['bat_x0'] + c['bat_l'] / 2
    cx0, cx1 = c['bat_x1'] - c['bat_lmax'] - 0.6, c['bat_x1'] + 0.3          # the cell's place, longest cell
    ux, uw, ul, uh = c['usb']
    _, uy = K(ux, 0, c)
    _, sy = K(c['sol'][0], 0, c)
    sw, sl, sh = c['sol'][1:]
    _, ry = K(c['btn'][0], 0, c)
    x0 = c['pcb_x']

    # ================================================================ tray
    tray = cut(rbox(0, L, olo, ohi, c['floor_z'], zs, c['corner_r']), rbox(ia, in_b, ilo, ihi, fz, zs + 1, ri))
    w_ = c['bevel_fill']
    for yw, s in ((ilo, 1), (ihi, -1)):
        tray = uni(tray, slice_off(bx(ia - 0.01, in_b + 0.01, yw - s * 0.01, yw + s * w_, F0, fz + w_), (yw + s * w_, fz), (s, 1)))
    for xa, xb in ((-1, ia + 0.01), (in_b - 0.01, L + 1)):                 # the lid's groove channel hangs 0.8 below the seam: a notch in each end wall
        tray = cut(tray, groove(c['groove_t'] + 0.05, xa, xb))
    for hx, hy in HOLES:                                                   # bosses under the board's holes
        tray = uni(tray, cyl((hx, hy, F0), (hx, hy, zb), c['boss_d'] / 2))
    # ledges under the board's edges, where it has no screw near: by each jack and under the two back corners
    rests = [(30.0, 36.0, ilo), (76.0, 82.0, ilo), (9.5, 13.5, ihi), (x0 + c['main_len'] - 3.6, x0 + c['main_len'] - 0.4, ihi)]
    if c['ports'] > 1:
        rests += [(L - 11.0, L - 5.0, ilo), (L - 11.0, L - 5.0, ihi)]
    for xa, xb, yw in rests:
        s = 1 if yw == ilo else -1
        tray = uni(tray, bx(xa, xb, yw - s * 0.01, yw + s * 1.4, F0, zb))
    # every jack sits in a slot open to the tray's rim (the lid's rim closes it), so the board's ends can come down
    for p, y, xf, xr, s in jacks(c):
        xa, xb = (-1, ia + ri + 0.2) if s < 0 else (in_b - ri - 0.2, L + 1)
        tray = cut(tray, bx(xa, xb, y - jw, y + jw, jz0, zs + 1))
        xa, xb = (wl, ia + ri + 0.2) if s < 0 else (in_b - ri - 0.2, L - wl)      # the sill is lower behind its outer lip
        tray = cut(tray, bx(xa, xb, y - jw, y + jw, jz0 - wf, zs + 1))
    # end wall A: the USB-C socket's rounded window, the solar jack's window, the pin hole to the reset button
    uc = c['usb_clear']
    tray = cut(tray, stadium(-1, ia + 0.01, uy, zt + uh / 2, uw / 2 + uc, uh / 2 + uc),
               stadium(wl, ia + 0.01, uy, zt + uh / 2, uw / 2 + uc + 0.2, uh / 2 + uc + wf))
    sc = c['sol_clear']
    tray = cut(tray, bx(-1, ia + 0.01, sy - sw / 2 - sc, sy + sw / 2 + sc, zt - sc, zt + sh + sc),
               bx(wl, ia + 0.01, sy - sw / 2 - sc - 0.2, sy + sw / 2 + sc + 0.2, zt - sc - wf, zt + sh + sc + wf))
    tray = cut(tray, cyl((-1, ry, zt + c['btn_axis']), (ia + 0.01, ry, zt + c['btn_axis']), c['btn_hole_r']))
    # the cell: two saddles under it (in the board's notch), back horns into the wall
    ytrim = c['cradle_y0'] + c['cradle_t']
    chz = math.sqrt(rc * rc - (by - ytrim) ** 2)
    # the cell's tray: a trough the whole length of the cell, up to 2 mm under its axis, like a battery holder. Its
    # first 4 mm at end A stay under the board's height, so the board's notch can slide over it on the way in.
    ta, tb = cx0 + c['cradle_end'], cx1 - c['cradle_end']
    trough = cut(bx(ta, tb, c['cradle_y0'], ihi + 0.5, F0, bc - 2.0),
                 cyl((ta - 1, by, bc), (tb + 1, by, bc), rc),
                 bx(ta - 1, tb + 1, c['cradle_y0'] - 1, ytrim, bc - chz, bc + 1),
                 bx(ta - 1, ta + c['cradle_low'], c['cradle_y0'] - 1, ihi + 1, zb - 0.3, bc + 1))
    # + and - sunk into its floor (0.5 deep at the middle line), a button outline at the + end
    m, mw, mz = c['mark'] / 2, c['mark_w'] / 2, fz - 0.3                  # 0.8 deep on the middle line; 0.9 of floor left
    xp, xm = tb - 9.0, ta + c['cradle_low'] + 6.0
    trough = cut(trough, bx(xp - m, xp + m, by - mw, by + mw, mz, bc), bx(xp - mw, xp + mw, by - m, by + m, mz, bc),
                 bx(xm - mw, xm + mw, by - m, by + m, mz, bc),
                 bx(tb - 2.6, tb + 1, by - 2.6, by + 2.6, mz, bc))
    tray = uni(tray, trough)
    for sx, sy_ in HOLES:                                                  # screws come up from below
        tray = cut(tray, cyl((sx, sy_, c['floor_z'] - 1), (sx, sy_, zb + 1), FIT.M3_R),
                   cone((sx, sy_, c['floor_z'] - 0.01), FIT.CSINK_CTRL_R, (sx, sy_, c['floor_z'] + FIT.CSINK_CTRL_H), FIT.CSINK_CTRL_R_TOP))
    # a finger notch in the back wall at the cell's middle, to lift the cell out
    tray = cut(tray, cyl((bat_xc, ihi - 0.5, zs), (bat_xc, ohi + 1, zs), c['pull_r']))
    tray = beveled(tray)
    out['outline'] = beveled(rbox(0, L, olo, ohi, c['floor_z'], c['top'], c['corner_r']))
    out['Tray'] = [('Tray', tray)]

    # ================================================================ lid
    lid = cut(rbox(0, L, olo, ohi, zs, c['top'], c['corner_r']), rbox(ia, in_b, ilo, ihi, zs - 1, zl, ri))
    lf = c['lid_fill']
    for yw, s in ((ilo, 1), (ihi, -1)):                                    # a 45 deg fill in the two long top corners: the bevel outside does not thin them
        lid = uni(lid, slice_off(bx(ia - 0.01, in_b + 0.01, yw - s * 0.01, yw + s * lf, zl - lf, zl + 0.01), (yw + s * lf, zl), (s, -1)))
    # the locating lip: 1.2 thick, 0.2 inside the tray's walls, from the lid's ceiling to 1.5 below the seam; cut away
    # wherever a jack, the ESP or the cell is beside the wall
    lip = cut(rbox(ia + 0.2, in_b - 0.2, ilo + 0.2, ihi - 0.2, zs - c['lip_h'], zl + 0.01, ri - 0.2),
              rbox(ia + 0.2 + c['lip_t'], in_b - 0.2 - c['lip_t'], ilo + 0.2 + c['lip_t'], ihi - 0.2 - c['lip_t'], zs - c['lip_h'] - 1, zl + 1, max(ri - 0.2 - c['lip_t'], 0.3)))
    for p, y, xf, xr, s in jacks(c):
        a, b_ = sorted((xf, xr))
        lip = cut(lip, bx(a - 3, b_ + 3, y - jw - 0.4, y + jw + 0.4, zb, zs + 0.3))
    ex0, ex1 = x0 + c['esp_by'], x0 + c['esp_by'] + c['esp_l']
    _, eyc = K(c['esp_bx'], 0, c)
    lip = cut(lip, bx(ex0 - 1.0, ex1 + 1.0, ilo - 1, eyc + c['esp_w'] / 2 + 0.6, zb, c['esp_z0'] + c['esp_t'] + c['esp_tip'] + 0.5))
    lip = cut(lip, cyl((cx0 - 1.5, by, bc), (cx1 + 1.5, by, bc), rc + 0.3))
    lip = cut(lip, bx(-1, ia + 3.0, uy - uw / 2 - 2, uy + uw / 2 + 2, zb, zs + 0.3), bx(-1, ia + 3.0, sy - sw / 2 - 2, sy + sw / 2 + 2, zb, zs + 0.3))
    lip = cut(lip, bx(bat_xc - c['pull_r'] - 1, bat_xc + c['pull_r'] + 1, ihi - 3, ohi + 1, zb, zl + 1))
    for nm, a0, a1, b0, b1, h, shape in comps(c):                           # and beside anything tall that stands at the board's edge
        if h > c['rj_h'] - c['lip_h'] and (a0 < 2.0 or a1 > c['pcb_w'] - 2.0):
            xa, ya = K(a0, b0, c)
            xb, yb_ = K(a1, b1, c)
            lip = cut(lip, bx(xa - 0.6, xb + 0.6, ya - 3.0, yb_ + 0.5, zb, zl + 1))
    lid = uni(lid, lip)
    # the groove's channel, 1.1 thick all round the groove: it hangs 0.8 below the seam along the middle
    lid = uni(lid, cut(groove(c['groove_t'], 0, L), bx(-1, L + 1, -30, 30, c['top'], c['top'] + 30)))
    # the tab that fills the tray's finger notch
    lid = uni(lid, cut(cyl((bat_xc, ihi + 0.2, zs), (bat_xc, ohi, zs), c['pull_r'] - 0.25), bx(bat_xc - 10, bat_xc + 10, ihi - 1, ohi + 1, zs, zs + 10)))
    pr = c['post_d'] / 2
    for px, py in HOLES:                                                   # posts with inserts clamp the board
        lid = uni(lid, cyl((px, py, zt), (px, py, zl + 0.01), pr))
        lid = cut(lid, cyl((px, py, zt - 0.01), (px, py, zt + FIT.INSERT_LEN), FIT.INSERT_R),
                  cone((px, py, zt - 0.01), FIT.INSERT_R + 0.4, (px, py, zt + 0.4), FIT.INSERT_R),
                  cyl((px, py, zt), (px, py, c['floor_z'] + c['screw_l'] + 0.8), FIT.M3_R))
    # the lid's half of the cell's tray: the same trough upside down, the whole length of the cell, down to the seam
    ylt = c['cradle_lid_y0'] + c['cradle_t']
    lhz = math.sqrt(rc * rc - (by - ylt) ** 2)
    lid = uni(lid, cut(bx(ta, tb, c['cradle_lid_y0'], ihi + 0.01, zs + 0.2, zl + 0.01),
                       cyl((ta - 1, by, bc), (tb + 1, by, bc), rc),
                       bx(ta - 1, tb + 1, c['cradle_lid_y0'] - 1, ylt, bc - 1, bc + lhz),
                       bx(bat_xc - c['pull_r'] - 0.5, bat_xc + c['pull_r'] + 0.5, ihi - 2.5, ihi + 1, zs - 1, zs + c['pull_r'] + 0.5)))
    lid = cut(lid, groove(0, -1, L + 1))
    lid = beveled(lid)
    out['Lid'] = [('Lid', lid)]

    # ================================================================ pads under the floor
    out['Pads'] = [('Foam pad %d' % (k + 1), cyl((px, py, 0), (px, py, c['pad_t']), c['pad_d'] / 2)) for k, (px, py) in enumerate(pads(c))]

    # ================================================================ the board (mock-up) and its parts
    y0, yb, y1 = c['pcb_y'], c['pcb_y'] + c['pcb_body'], c['pcb_y'] + c['pcb_w']
    n0, n1 = x0 + c['notch'][0], x0 + c['notch'][1]
    xe = x0 + c['main_len']
    r_ = c['pcb_r']
    board = cut(rbox(x0, xe, y0, y1, zb, zt, r_), bx(n0, n1, yb, y1 + 1, zb - 1, zt + 1))
    if c['ports'] > 1:
        nk0, nk1, nl = c['neck']
        board = uni(board, bx(xe - r_, xe + nl + r_, y0 + nk0, y0 + nk1, zb, zt), rbox(xe + nl, xe + nl + c['tab_len'], y0, y1, zb, zt, r_))
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
    # USB-C socket: a rounded shell with its rounded mouth
    ua = c['usb_in']
    usb = cut(stadium(ua, ua + ul, uy, zt + uh / 2, uw / 2, uh / 2),
              stadium(ua - 1, ua + 4.5, uy, zt + uh / 2, 8.34 / 2, 2.56 / 2))
    usb = uni(usb, bx(ua + 1.2, ua + 5.6, uy - 3.3, uy + 3.3, zt + uh / 2 - 0.35, zt + uh / 2 + 0.35))       # its tongue
    for dx in (2.6, 6.4):                                                   # its four shell stakes, through the board
        for dy in (-4.32, 4.32):
            usb = uni(usb, bx(ua + dx - 0.4, ua + dx + 0.4, uy + dy - 0.15, uy + dy + 0.15, zt - 1.0, zt + 1.0))
    P.append(('USB-C socket', usb))
    # solar jack: its block, the lower rear part, the round socket in its face
    sa = c['sol_in']
    sol = uni(bx(sa, sa + 7.4, sy - sw / 2, sy + sw / 2, zt, zt + sh), bx(sa + 7.39, sa + sl, sy - sw / 2, sy + sw / 2, zt, zt + 5.5))
    sol = cut(sol, cyl((sa - 1, sy, zt + c['sol_axis']), (sa + 6.2, sy, zt + c['sol_axis']), 2.1))
    sol = uni(sol, cyl((sa + 0.8, sy, zt + c['sol_axis']), (sa + 6.2, sy, zt + c['sol_axis']), 0.65))
    P.append(('Solar jack', sol))
    # reset button: body behind its front leads, actuator out through the wall
    bw, bl, bh = c['btn'][1:]
    tip = c['btn_tip']
    lead = tip + c['btn_reach']
    P.append(('Reset button', uni(bx(lead, lead + bl, ry - bw / 2, ry + bw / 2, zt, zt + bh),
                                  cyl((tip, ry, zt + c['btn_axis']), (lead, ry, zt + c['btn_axis']), c['btn_d'] / 2))))
    # ESP32-C6 on sockets: socket strips, spacers, board, pin tips
    for r in c['esp_rows']:
        _, yr = K(r, 0, c)
        P.append(('ESP socket %.0f' % r, bx(ex0 + 0.3, ex1 - 0.3, yr - 1.27, yr + 1.27, zt, zt + c['sock_h'])))
        P.append(('ESP spacer %.0f' % r, bx(ex0 + 0.3, ex1 - 0.3, yr - 1.27, yr + 1.27, zt + c['sock_h'], c['esp_z0'])))
        P.append(('ESP pin tips %.0f' % r, bx(ex0 + 1.2, ex1 - 1.2, yr - 0.4, yr + 0.4, c['esp_z0'] + c['esp_t'], c['esp_z0'] + c['esp_t'] + c['esp_tip'])))
    P.append(('ESP32-C6 board', bx(ex0, ex1, eyc - c['esp_w'] / 2, eyc + c['esp_w'] / 2, c['esp_z0'], c['esp_z0'] + c['esp_t'])))
    # every small part
    for nm, a0, a1, b0, b1, h, shape in comps(c):
        xa, ya = K(a0, b0, c)
        xb, yb_ = K(a1, b1, c)
        if shape == 'axial':                                                # a round body lying along the board, a lead out of each end
            yc, r = (ya + yb_) / 2, h / 2
            ln = (xb - xa)
            body = uni(cyl((xa + ln * 0.22, yc, zt + r + 0.2), (xb - ln * 0.22, yc, zt + r + 0.2), r),
                       cyl((xa + 1.1, yc, zt + r + 0.2), (xb - 1.1, yc, zt + r + 0.2), 0.4))
            for xx in (xa + 1.1, xb - 1.1):
                body = uni(body, cyl((xx, yc, zt), (xx, yc, zt + r + 0.2), 0.4))
        elif shape == 'radial':
            body = cyl(((xa + xb) / 2, (ya + yb_) / 2, zt + 0.3), ((xa + xb) / 2, (ya + yb_) / 2, zt + 0.3 + h), (xb - xa) / 2)
        elif shape == 'chip':                                               # body with its legs' pads either side
            body = uni(bx(xa + 0.75, xb - 0.75, ya + 1.15, yb_ - 1.15, zt + 0.1, zt + h), bx(xa + 0.95, xb - 0.95, ya + 0.3, yb_ - 0.3, zt, zt + 0.3))
        elif shape == 'smd':                                                # the chip inside its courtyard, on its two pads
            ix, iy = (0.85, 0.3) if (xb - xa) > (yb_ - ya) else (0.3, 0.85)
            body = uni(bx(xa + ix, xb - ix, ya + iy, yb_ - iy, zt + 0.05, zt + h), bx(xa + ix / 3, xb - ix / 3, ya + iy / 3, yb_ - iy / 3, zt, zt + 0.1))
        else:
            body = bx(xa, xb, ya, yb_, zt, zt + h)
        P.append((nm, body))
    # the cell at its nominal length, its + end on the button at end B
    P.append(('18650 cell', cyl((c['bat_x0'], by, bc), (c['bat_x0'] + c['bat_l'], by, bc), c['bat_d'] / 2)))
    # the contacts, from the catalog drawing: plate on the L line, base behind it, two legs; the 596's button; the
    # 590's leaf drawn pressed back by the nominal cell (its bend sits lower the harder it is pressed)
    for k, cxh in enumerate(c['ct_x']):
        s = 1 if k == 0 else -1                                             # toward the cell
        top = c['ct_fold'] if k == 0 else c['ct_h']
        base_end = cxh - s * c['ct_base']
        body = uni(bx(cxh - c['ct_t'] / 2, cxh + c['ct_t'] / 2, by - c['ct_w'] / 2, by + c['ct_w'] / 2, zt, zt + top),
                   bx(*sorted((cxh, base_end)), by - c['ct_w'] / 2, by + c['ct_w'] / 2, zt, zt + c['ct_t']))
        for lx, ly in legs(cxh, s):
            body = uni(body, bx(lx - 0.4, lx + 0.4, ly - 0.4, ly + 0.4, zb - 2.2, zt + 0.1))
        if k == 1:
            body = uni(body, cyl((cxh - c['ct_t'] / 2 - c['ct_btn_proud'], by, zt + c['ct_btn_z']), (cxh, by, zt + c['ct_btn_z']), c['ct_btn_d'] / 2))
            P.append(('Cell contact + (596)', body))
        else:
            sq = leaf_squeeze(c['bat_l'], c)
            zc = zt + c['leaf_z'][0] + (c['leaf_z'][1] - c['leaf_z'][0]) * max(min(sq / 3.0, 1.0), 0.0)
            tipx = cxh + c['ct_t'] / 2 + (c['leaf_reach'] - max(sq, 0.0))    # where the leaf's bend is now
            body = uni(body, bx(cxh, tipx, by - c['leaf_w'] / 2, by + c['leaf_w'] / 2, zc - 0.4, zc + 0.4))
            P.append(('Cell contact - (590)', body))
    out['Parts'] = P
    out['Screws'] = [('M3x%.0f %d' % (c['screw_l'], k), uni(cone((x, y, c['floor_z']), 2.95, (x, y, c['floor_z'] + 1.6), 1.45),
                                                          cyl((x, y, c['floor_z'] + 1.55), (x, y, c['floor_z'] + c['screw_l']), 1.45)))
                     for k, (x, y) in enumerate(HOLES)]
    # plugs: the charge cable's USB-C plug (12.4 x 6.5 overmold, stops 1.85 before the socket's mouth), the solar plug
    # (dia 8 body, dia 3.5 barrel), an RJ12 plug in port 1, and a cable in the ESP's own USB-C (lid off: flashing)
    pw, ph, pl = c['esp_plug']
    ez = c['esp_z0'] + c['esp_t'] + 1.6
    y1j = jacks(c)[0][1]
    out['Plugs'] = [('USB-C plug', uni(stadium(-22, ua - 1.85, uy, zt + uh / 2, 6.2, 3.25),
                                       stadium(ua - 1.85, ua + 4.3, uy, zt + uh / 2, 4.12, 1.2))),
                    ('Solar plug', uni(cyl((-24, sy, zt + c['sol_axis']), (sa - 0.3, sy, zt + c['sol_axis']), 4.0),
                                       cyl((sa - 0.3, sy, zt + c['sol_axis']), (sa + 6.0, sy, zt + c['sol_axis']), 1.75))),
                    ('RJ12 plug', bx(-14, c['rj_recess'] + 9.0, y1j - c['rj_mouth_w'] / 2 + 0.15, y1j + c['rj_mouth_w'] / 2 - 0.15,
                                     zt + c['rj_mouth'][0] + 0.15, zt + c['rj_mouth'][1] - 0.15)),
                    ('ESP flashing plug', bx(ex1 + 0.5, ex1 + 0.5 + pl, eyc - pw / 2, eyc + pw / 2, ez - ph / 2, ez + ph / 2))]
    return out
