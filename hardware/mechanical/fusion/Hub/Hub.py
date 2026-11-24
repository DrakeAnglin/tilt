"""The Tilt Hub box: one printed piece, closed all round. The ESP32-C6 SuperMini (no pins) with a USB-C male-to-male
adapter plugged into it is dropped in at a pause part-way up the print, and the printer then prints the roof over it.

  * It prints pinhole face down. The ESP goes in PARTS SIDE DOWN: its flat, bare back faces the roof.
  * The adapter's body sits in a close pocket in the nose. A thin lip in front of it, closed all round the plug, and
    a low stop behind it take the pull and the push of plugging in, so the ESP's own USB-C socket carries no load.
  * The parts go in nose first: tilted, the plug slides out through the lip's hole, then the back drops down. The
    stop is a low bar so the body's back corner swings over it (checked by the Fusion driver's slide-in test); once
    the roof is on, the body cannot lift over it.
  * The ESP lies on two rails that reach up to its face along the pad rows, behind the web.
  * Two pinholes in the bed face, one under BOOT and one under RST, each in a tube that guides a paper clip.
  * No supports: the roof bridges across the box, one layer over the adapter and about 0.7 over the ESP's back.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_hub.py --timeout 600

Coordinates (mm): X from the back face toward the plug, Y across (centered), Z up from the print bed.
"""

import math

H = dict(
    # ESP32-C6 SuperMini, MEASURED by the owner (2026-11-23): board 26.14 x 18.28; socket top 4.3 above the board's
    # underside (the tallest thing on it; a USB-C socket is 3.26 tall, so the board is 1.04); nothing underneath.
    # Buttons: body starts 8.1 from the USB-C edge and is 2.5 long, center 5.3 in from the long edge, one each side.
    # BOOT is on the right with the USB-C toward you, looking at the parts side (-Y here: the board lies parts down), RST on the left. The socket passes the board's edge by 1.4
    esp_l=26.14, esp_w=18.28, esp_t=1.04, usb_over=1.4, usb_w=9.1, usb_h=3.26, usb_len=7.4,
    btn_x=8.1 + 2.5 / 2, btn_y={'BOOT': -(18.28 / 2 - 5.3), 'RST': 18.28 / 2 - 5.3}, btn_size=(2.5, 3.0, 2.0),   # (along X, along Y, height)
    # USB-C male-to-male adapter (Amazon B0HFHVN7B6), MEASURED by the owner (2026-11-23): body 14.3 x 12.25 x 6.41
    # (top slightly rounded), plugs 6.75 past the body and centered in it both ways
    adp_l=14.3, adp_w=12.25, adp_h=6.41,          # its body
    plug_w=8.4, plug_t=2.6, plug_len=6.75,        # each plug, past the body (cross-section: the USB-C standard)
    # Pushed home in the ESP: the board's USB-C edge to the adapter body's back face. Two measurements disagree by
    # 0.3: board's back edge to the body's front 44.1 (gives 3.66), board's USB-C edge to the body's front 18.25
    # (gives 3.95). 3.8 is the middle; esp_front and esp_back below cover both. The adapter's body sits between the
    # web and the lip and sets where the ESP lies, so this play is not rattle
    edge_to_body=3.8,
    # the box
    wall=1.6, floor_min=1.0, roof=1.2, lip=0.6, layer=0.2,
    corner_r=2.5, nose_r=2.0, edge=0.6,
    blend_r=4.0,                                  # the sides sweep into the nose: two arcs of this radius, no corners
    pin_sink=0.4,                                 # small countersink round each pinhole on the bed face
    web_step=0.8,                                 # the stop behind the adapter's body: a bar this high on the floor
    rail_w=2.0,                                   # the ESP's two rails (under its pad rows)
    # Fits: snug, but the parts must still drop in by themselves at the pause (a part that sticks gets hit by the
    # nozzle). Pockets print about 0.05 a side small on the owner's printer, so 0.15 here is about 0.1 real
    esp_side=0.15, esp_back=0.3, esp_front=0.3,   # play round the board
    adp_side=0.15, adp_end=0.2,                   # play round the adapter's body (the ends: room to swing in, see web_step)
    top_min=0.2,                                  # least room between the adapter's top and the pause height (one layer)
    slot=0.2, slot_z=0.3,                         # play round the plug in the lip's hole: each side, above and below
    # The mark on the bed face: the app icon's three slats (app/Tilt/make_icon.swift: strokes 72 wide, +-215 along,
    # +-78 across, 230 apart) and "tilt" beside them, engraved. Sized for a 0.4 nozzle: no groove under 0.8 wide.
    # Looking at the face with the plug to the right, it reads left to right
    mark_depth=0.4, logo_h=8.0, logo_x=26.2, text_x=31.6, text_size=7.2,
    logo_stroke=1.3,                              # slats thicker than the icon's (0.84 at this size): three passes, like the letters
    pin_d=1.8,                                    # pinholes (a paper clip is about 1 mm)
    tube_d=4.4, tube_gap=2.5,                     # guide tube round each pinhole; it ends this far under the board's face
                                                  # (button height not measured: 2.0 assumed)
    rail_gap=0.02,                                # least room between the rails and the board's face
)
h = H
H['x_in'] = h['wall']                                        # pocket's back face
H['esp_x0'] = H['x_in'] + h['esp_back']                      # board's back edge
H['esp_x1'] = H['esp_x0'] + h['esp_l']                       # its USB-C edge
H['usb_x1'] = H['esp_x1'] + h['usb_over']                    # socket mouth
H['adp_x0'] = H['esp_x1'] + h['edge_to_body']                   # adapter body: back face
H['adp_x1'] = H['adp_x0'] + h['adp_l']                       # front face
H['web_x0'] = H['esp_x1'] + h['esp_front']                   # web between board and adapter body
H['web_x1'] = H['adp_x0'] - h['adp_end']
H['lip_x0'] = H['adp_x1'] + h['adp_end']
H['L'] = H['lip_x0'] + h['lip']                              # front face
H['tip'] = H['adp_x1'] + h['plug_len']                       # plug's tip
# PAUSE at zp, after the last layer of the walls and before the first layer of the roof. The floor under the
# adapter's body is made just thick enough that the body's top is exactly top_min (one layer) under zp: the roof's
# first layer is a bridge, it sags a little and comes to rest on the adapter, which then cannot rattle
H['zp'] = math.ceil((h['floor_min'] + h['adp_h'] + h['top_min']) / h['layer'] - 1e-6) * h['layer']
H['fz'] = H['zp'] - h['top_min'] - h['adp_h']                # floor's top: the adapter's body rests on it
H['adp_top'] = h['top_min']
H['zc'] = H['fz'] + h['adp_h'] / 2                           # the plugs' center line
H['esp_face'] = H['zc'] + h['usb_h'] / 2                     # board's parts side, facing down (the socket hangs under it)
H['esp_back'] = H['esp_face'] + h['esp_t']                   # its bare back, facing the roof
# rails: up to the last whole layer under the board's face
H['rail_top'] = math.floor((H['esp_face'] - h['rail_gap']) / h['layer'] + 1e-6) * h['layer']
H['tube_top'] = H['esp_face'] - h['tube_gap']
H['top'] = H['zp'] + h['roof']
H['hw'] = h['esp_w'] / 2 + h['esp_side'] + h['wall']         # half width, main part
H['nose_hw'] = h['adp_w'] / 2 + h['adp_side'] + h['wall']    # half width, nose
H['taper_x'] = H['web_x0'] + 0.9                             # where the sides start to narrow: past the ESP pocket's corner (wall 1.6+)
H['pause_layer'] = round(H['zp'] / h['layer'])
H['btn'] = {n: (H['esp_x1'] - h['btn_x'], y) for n, y in h['btn_y'].items()}


def build(bx, cyl, uni, cut, isect, rbox, obox, cone=None):
    """{group: [(name, body)]}: the box and mock-ups of what goes in it."""
    L, hw, nhw, top, fz, zp = H['L'], H['hw'], H['nose_hw'], H['top'], H['fz'], H['zp']
    def shell():
        """The box's outside shape, solid: main part, sides that sweep in to the nose in an S (45 deg, an arc at each
        end), rounded corners."""
        box = rbox(0, L, -hw, hw, 0, top, h['corner_r'])
        s2 = 0.5 ** 0.5
        tx = H['taper_x']
        qx = tx + (hw - nhw)                           # where the taper meets the nose's side
        R = h['blend_r']
        t = R * math.tan(math.radians(22.5))           # corner to tangent point
        for s in (1, -1):
            # narrow to the nose: everything outside the nose's width past the 45 deg taper
            tool = obox((tx + s2 * 20, s * (hw + s2 * 20), top / 2), (s * s2, -s2, 0), (s2, s * s2, 0), 80, 40, top + 2)
            y0, y1 = sorted((s * nhw, s * (hw + 1)))
            box = cut(box, isect(tool, bx(tx - 1, L + 1, y0, y1, -1, top + 1)))
            # outer arc where the side turns in: take the corner off outside a circle
            y0, y1 = sorted((s * (hw - t * s2), s * (hw + 0.01)))
            box = cut(box, cut(bx(tx - t, tx + t * s2, y0, y1, -1, top + 1), cyl((tx - t, s * (hw - R), -2), (tx - t, s * (hw - R), top + 2), R)))
            # inner arc where the taper meets the nose: fill the corner outside a circle
            y0, y1 = sorted((s * (nhw - 0.2), s * (nhw + t * s2)))
            box = uni(box, cut(bx(qx - R, qx + t, y0, y1, 0, top), cyl((qx + t, s * (nhw + R), -2), (qx + t, s * (nhw + R), top + 2), R)))
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
        box = uni(box, bx(H['x_in'] - 0.2, H['web_x0'] + 0.2, y0, y1, fz - 0.2, H['rail_top']))
    for x, y in H['btn'].values():
        box = uni(box, cyl((x, y, fz - 0.2), (x, y, H['tube_top']), h['tube_d'] / 2))
    # the adapter body's pocket; behind it only a low bar is left of the web (the stop)
    ahw = h['adp_w'] / 2 + h['adp_side']
    box = cut(box, bx(H['web_x1'], H['lip_x0'], -ahw, ahw, fz, zp))
    box = cut(box, bx(H['web_x0'] - 0.01, H['web_x1'] + 0.01, -ahw, ahw, fz + h['web_step'], zp))
    # the plug's hole in the lip, closed all round, with full-round ends like the plug itself
    def stadium(x0, x1, hw_, hz):
        """A USB-C plug's outline along X on the plugs' center line: half width hw_, half thickness hz, round ends."""
        b = bx(x0, x1, -(hw_ - hz), hw_ - hz, H['zc'] - hz, H['zc'] + hz)
        for s in (1, -1):
            b = uni(b, cyl((x0, s * (hw_ - hz), H['zc']), (x1, s * (hw_ - hz), H['zc']), hz))
        return b

    phw, phz = h['plug_w'] / 2 + h['slot'], h['plug_t'] / 2 + h['slot_z']
    box = cut(box, stadium(H['lip_x0'] - 0.01, L + 0.01, phw, phz))
    # pinholes under the buttons, up through the tubes
    for x, y in H['btn'].values():
        box = cut(box, cyl((x, y, -0.01), (x, y, H['tube_top'] + 0.01), h['pin_d'] / 2))
        if cone:
            box = cut(box, cone((x, y, -0.01), h['pin_d'] / 2 + h['pin_sink'] + 0.01, (x, y, h['pin_sink']), h['pin_d'] / 2))

    # the three slats (the driver adds the word beside them), on the icon's centers, strokes logo_stroke wide. 'Mark' is the same shape as a part of its own: it fills
    # the engraving flush, for a two-color print
    k = h['logo_h'] / (2 * 230 + 2 * 78 + 72)

    def slat(i):
        a = (h['logo_x'] - 215 * k, i * 230 * k - 78 * k)
        b = (h['logo_x'] + 215 * k, i * 230 * k + 78 * k)
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        u = ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln, 0)
        t = obox(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, h['mark_depth'] / 2 - 0.01), u, (-u[1], u[0], 0), ln, h['logo_stroke'], h['mark_depth'] + 0.02)
        for q in (a, b):
            t = uni(t, cyl((q[0], q[1], -0.02), (q[0], q[1], h['mark_depth']), h['logo_stroke'] / 2))
        return t

    mark = None
    for i in (-1, 0, 1):
        box = cut(box, slat(i))
        mark = slat(i) if mark is None else uni(mark, slat(i))
    mark = isect(mark, bx(0, L, -hw, hw, 0, h['mark_depth']))

    P = []
    P.append(('ESP32-C6 board', bx(H['esp_x0'], H['esp_x1'], -h['esp_w'] / 2, h['esp_w'] / 2, H['esp_face'], H['esp_back'])))
    P.append(('ESP32-C6 USB-C', bx(H['usb_x1'] - h['usb_len'], H['usb_x1'], -h['usb_w'] / 2, h['usb_w'] / 2,
                                   H['esp_face'] - h['usb_h'], H['esp_face'])))
    bl, bw, bh = h['btn_size']
    for n, (x, y) in H['btn'].items():
        P.append(('ESP32-C6 ' + n, bx(x - bl / 2, x + bl / 2, y - bw / 2, y + bw / 2, H['esp_face'] - bh, H['esp_face'])))
    P.append(('Adapter body', bx(H['adp_x0'], H['adp_x1'], -h['adp_w'] / 2, h['adp_w'] / 2, fz, fz + h['adp_h'])))
    P.append(('Adapter plug', stadium(H['adp_x1'], H['tip'], h['plug_w'] / 2, h['plug_t'] / 2)))
    return {'Box': [('Hub box', box)], 'Mark': [('Hub mark', mark)], 'Parts': P}
