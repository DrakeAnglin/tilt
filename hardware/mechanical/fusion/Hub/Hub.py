"""The Tilt Hub box: one printed piece, closed all round. The ESP32-C6 SuperMini (no pins) with a USB-C male-to-male
adapter plugged into it is dropped in at a pause part-way up the print, and the printer then prints the roof over it.

  * The adapter's body sits in a close pocket in the nose. A thin lip in front of it and a web behind it take the
    pull and the push of plugging in, so the ESP's own USB-C socket carries no load.
  * The ESP lies on two rails behind the web, held by the adapter's plug.
  * Two pinholes in the roof, one over BOOT and one over RST, for a paper clip.
  * Prints flat as modeled, no supports: the roof bridges across the box.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_hub.py --timeout 600

Coordinates (mm): X from the back face toward the plug, Y across (centered), Z up from the print bed.
"""

import math

H = dict(
    # ESP32-C6 SuperMini, MEASURED by the owner (2026-11-23): board 26.14 x 18.28; socket top 4.3 above the board's
    # underside (the tallest thing on it; a USB-C socket is 3.26 tall, so the board is 1.04); nothing underneath.
    # Buttons: body starts 8.1 from the USB-C edge and is 2.5 long, center 5.3 in from the long edge, one each side.
    # BOOT is on the right with the USB-C toward you (+Y here), RST on the left. The socket passes the board's edge by 1.4
    esp_l=26.14, esp_w=18.28, esp_t=1.04, usb_over=1.4, usb_w=9.1, usb_h=3.26, usb_len=7.4,
    btn_x=8.1 + 2.5 / 2, btn_y={'BOOT': 18.28 / 2 - 5.3, 'RST': -(18.28 / 2 - 5.3)}, btn_size=(2.5, 3.0, 2.0),   # (along X, along Y, height)
    # USB-C male-to-male adapter (Amazon B0HFHVN7B6). ESTIMATED from the listing photo: measure the real one
    adp_l=17.0, adp_w=12.6, adp_h=6.6,            # its body
    plug_w=8.4, plug_t=2.6, plug_len=6.5,         # each plug, past the body
    plug_gap=0.45,                                # body to the ESP's socket mouth when pushed home
    # the box
    wall=1.6, floor=1.0, roof=1.2, lip=0.6, layer=0.2,
    corner_r=2.0, nose_r=1.5, taper=2.75, edge=0.4,
    rail_w=2.0,                                   # the ESP's two rails (under its pad rows)
    # Fits: snug, but the parts must still drop in by themselves at the pause (a part that sticks gets hit by the
    # nozzle). Pockets print about 0.05 a side small on the owner's printer, so 0.15 here is about 0.1 real
    esp_side=0.15, esp_back=0.2, esp_front=0.2,   # play round the board
    adp_side=0.15, adp_end=0.15,                  # play round the adapter's body
    top_min=0.2,                                  # least room between the adapter's top and the pause height (one layer)
    slot=0.2,                                     # play round the plug in the lip
    pin_d=1.8,                                    # pinholes (a paper clip is about 1 mm)
)
h = H
H['x_in'] = h['wall']                                        # pocket's back face
H['esp_x0'] = H['x_in'] + h['esp_back']                      # board's back edge
H['esp_x1'] = H['esp_x0'] + h['esp_l']                       # its USB-C edge
H['usb_x1'] = H['esp_x1'] + h['usb_over']                    # socket mouth
H['adp_x0'] = H['usb_x1'] + h['plug_gap']                    # adapter body: back face
H['adp_x1'] = H['adp_x0'] + h['adp_l']                       # front face
H['web_x0'] = H['esp_x1'] + h['esp_front']                   # web between board and adapter body
H['web_x1'] = H['adp_x0'] - h['adp_end']
H['lip_x0'] = H['adp_x1'] + h['adp_end']
H['L'] = H['lip_x0'] + h['lip']                              # front face
H['tip'] = H['adp_x1'] + h['plug_len']                       # plug's tip
H['fz'] = h['floor']                                         # the adapter's body rests on the floor
H['zc'] = H['fz'] + h['adp_h'] / 2                           # the plugs' center line
H['esp_zt'] = H['zc'] - h['usb_h'] / 2                       # board's top face (the socket sits on it)
H['esp_z0'] = H['esp_zt'] - h['esp_t']
# PAUSE here, after the last layer of the walls and before the first layer of the roof: the first whole layer that is
# top_min or more above the adapter's body (the tallest part). The roof's first layer is a bridge: it sags a little
# and comes to rest on the adapter, which then cannot rattle
H['zp'] = math.ceil((H['fz'] + h['adp_h'] + h['top_min']) / h['layer'] - 1e-6) * h['layer']
H['adp_top'] = H['zp'] - H['fz'] - h['adp_h']                # room above the adapter at the pause
# rails: the last whole layer under the board's underside
H['rail_h'] = math.floor((H['esp_z0'] - H['fz']) / h['layer'] + 1e-6) * h['layer']
H['top'] = H['zp'] + h['roof']
H['hw'] = h['esp_w'] / 2 + h['esp_side'] + h['wall']         # half width, main part
H['nose_hw'] = h['adp_w'] / 2 + h['adp_side'] + h['wall']    # half width, nose
H['taper_x'] = H['web_x0'] - 1.0                             # where the sides start to narrow
H['pause_layer'] = round(H['zp'] / h['layer'])
H['btn'] = {n: (H['esp_x1'] - h['btn_x'], y) for n, y in h['btn_y'].items()}


def build(bx, cyl, uni, cut, isect, rbox, obox):
    """{group: [(name, body)]}: the box and mock-ups of what goes in it."""
    L, hw, nhw, top, fz, zp = H['L'], H['hw'], H['nose_hw'], H['top'], H['fz'], H['zp']
    def shell():
        """The box's outside shape, solid: main part, 45 deg taper, nose with rounded front corners."""
        box = rbox(0, L, -hw, hw, 0, top, h['corner_r'])
        s2 = 0.5 ** 0.5
        tx = H['taper_x']
        for s in (1, -1):
            # narrow to the nose: everything outside the nose's width past the 45 deg taper
            tool = obox((tx + s2 * 20, s * (hw + s2 * 20), top / 2), (s * s2, -s2, 0), (s2, s * s2, 0), 80, 40, top + 2)
            y0, y1 = sorted((s * nhw, s * (hw + 1)))
            box = cut(box, isect(tool, bx(tx - 1, L + 1, y0, y1, -1, top + 1)))
            # round the nose's front corner
            r = h['nose_r']
            cx, cy = L - r, s * (nhw - r)
            y0, y1 = sorted((cy, s * (nhw + 0.01)))
            box = cut(box, bx(cx, L + 0.01, y0, y1, -1, top + 1))
            box = uni(box, cyl((cx, cy, 0), (cx, cy, top), r))
        return box

    box = shell()
    H['outline'] = shell()      # nothing may reach outside it, except the plug (checked by the Fusion driver)
    # ESP pocket, then its two rails
    ehw = h['esp_w'] / 2 + h['esp_side']
    box = cut(box, bx(H['x_in'], H['web_x0'], -ehw, ehw, fz, zp))
    for s in (1, -1):
        y0, y1 = sorted((s * (ehw - h['rail_w']), s * (ehw + 0.2)))
        box = uni(box, bx(H['x_in'] - 0.2, H['web_x0'] + 0.2, y0, y1, fz - 0.2, fz + H['rail_h']))
    # the socket's way through the web, the adapter body's pocket, the plug's slot in the lip
    uhw = h['usb_w'] / 2 + 0.3
    box = cut(box, bx(H['web_x0'] - 0.01, H['web_x1'] + 0.01, -uhw, uhw, H['esp_zt'] - 0.3, zp))
    ahw = h['adp_w'] / 2 + h['adp_side']
    box = cut(box, bx(H['web_x1'], H['lip_x0'], -ahw, ahw, fz, zp))
    phw = h['plug_w'] / 2 + h['slot']
    box = cut(box, bx(H['lip_x0'] - 0.01, L + 0.01, -phw, phw, H['zc'] - h['plug_t'] / 2 - h['slot'], zp))
    # pinholes over the buttons
    for x, y in H['btn'].values():
        box = cut(box, cyl((x, y, zp - 0.01), (x, y, top + 0.01), h['pin_d'] / 2))

    P = []
    P.append(('ESP32-C6 board', bx(H['esp_x0'], H['esp_x1'], -h['esp_w'] / 2, h['esp_w'] / 2, H['esp_z0'], H['esp_zt'])))
    P.append(('ESP32-C6 USB-C', bx(H['usb_x1'] - h['usb_len'], H['usb_x1'], -h['usb_w'] / 2, h['usb_w'] / 2,
                                   H['esp_zt'], H['esp_zt'] + h['usb_h'])))
    bl, bw, bh = h['btn_size']
    for n, (x, y) in H['btn'].items():
        P.append(('ESP32-C6 ' + n, bx(x - bl / 2, x + bl / 2, y - bw / 2, y + bw / 2, H['esp_zt'], H['esp_zt'] + bh)))
    P.append(('Adapter body', bx(H['adp_x0'], H['adp_x1'], -h['adp_w'] / 2, h['adp_w'] / 2, fz, fz + h['adp_h'])))
    P.append(('Adapter plug', bx(H['adp_x1'], H['tip'], -h['plug_w'] / 2, h['plug_w'] / 2,
                                 H['zc'] - h['plug_t'] / 2, H['zc'] + h['plug_t'] / 2)))
    return {'Box': [('Hub box', box)], 'Parts': P}
