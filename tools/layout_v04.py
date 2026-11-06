"""v0.4 layout study: an all-printed tilter (printed worm + worm wheel on the rod, N20 beside the worm through a spur
pair, wand hooked to the worm's lower end, AS5600 on a gear off the wheel). Searches the end view (looking along the
rod: Y across the rail, room side negative; Z up from the rail floor) for layouts that fit the rail envelope.

  python3 tools/layout_v04.py            # prints the best layouts and writes docs/renders/v04-layout-*.svg

Layout
  wheel     on the rod (0, 24), Zw teeth, module m
  worm      single start (self-locking), pitch dia d1; axis in the YZ plane at angle th below horizontal, BELOW and
            BEHIND the rod, running from the corner notch (wand end, room side, low) up toward the back wall
  spur pair at the worm's upper end: worm gear (zg) on the worm shaft, N20 pinion (zp) on a motor lying parallel to
            the worm, offset along the rod (-X, the lid side, away from the tilt drums)
  sensor    AS5600 magnet on a gear meshing with the wheel, shaft out through the lid (-X) to the board
"""
import math
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# envelope (same as v0.3): rail inside 55.5 wide x 36.5 tall, top lips 4.5 in / 3 deep, open slot between the lips
HW, H, LIP_IN, LIP_H = 27.75, 36.5, 4.5, 3.0
SLOT_TOP = 38.9                       # owner: 2.8 mm above the rail top is free between the lips
FLOOR, WALL = 0.2, 1.2                # case bottom above the rail floor; minimum case wall
ROD = (0.0, 24.0)
ROD_HALF_DIAG = 2.0 * math.sqrt(2)
HUB_R = 6.5                           # wheel hub / bearing barrel around the rod, runs the full case width
MIN_WAND_ANGLE = 10                   # steeper fails (see the header): the wand gets a printed U-joint at the notch
# corner notch (the wand exits here): 12 tall up the room-side wall, 10.5 into the floor (from the outside), X +-6
NOTCH_WALL_TOP = (-HW, 10.0)          # where the notch stops on the inside of the wall
NOTCH_FLOOR_EDGE = (-29.75 + 10.5, 0.0)
WAND_R = 3.0 + 0.5                    # wand shaft radius + clearance
# N20 (no encoder)
MO_LEN, MO_W, MO_H, MO_GAP = 25.0, 12.0, 10.0, 1.5
RPS = 300 / 60.0
TRAVEL_DEG = 260.0                    # measured: ~250-270 deg of rod for full tilt


def worm_layout(m, zw, d1, th_deg, zg, zp, ms, side=1, spur_end=1, motor_dir=-1):
    """side +1: worm below/behind the rod, -1: above/room side (factory). spur_end +1: spur pair at the worm's upper
    end, -1: at its lower end (just above the wand). motor_dir -1: motor runs from the spur pair toward the wand end,
    +1: toward the upper end."""
    th = math.radians(th_deg)
    R, ra_w = zw * m / 2, zw * m / 2 + m
    r1, ra1 = d1 / 2, d1 / 2 + m
    a = R + r1 + 0.2                                           # +0.2: printed mesh (v0.3 test fit was tight)
    n = (side * math.sin(th), -side * math.cos(th))           # rod -> worm axis
    up = (math.cos(th), math.sin(th))                          # along the worm toward the back wall (motor end)
    p0 = (ROD[0] + a * n[0], ROD[1] + a * n[1])
    P = lambda t, s=0.0: (p0[0] + up[0] * t + n[0] * s, p0[1] + up[1] * t + n[1] * s)
    half = math.sqrt(max(ra_w ** 2 - (a - ra1) ** 2, 0)) + 0.5 * m   # thread half-length: covers the wheel's tips
    rg, rp = zg * ms / 2, zp * ms / 2
    cd_s = rg + rp + 0.1
    tg = spur_end * (half + 3.0 + 2.5)                         # bearing, then the 5 mm wide worm gear
    return dict(m=m, zw=zw, d1=d1, th=th_deg, zg=zg, zp=zp, ms=ms, R=R, ra_w=ra_w, r1=r1, ra1=ra1, a=a, n=n, up=up,
                p0=p0, P=P, half=half, rg=rg, rp=rp, ra_g=rg + ms, ra_p=rp + ms, cd_s=cd_s, tg=tg,
                lam=math.degrees(math.atan(m / d1)), side=side, spur_end=spur_end, motor_dir=motor_dir)


def seg_dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / (ax * ax + ay * ay)))
    return math.hypot(p[0] - a[0] - ax * t, p[1] - a[1] - ay * t)


def rect_pts(L, t0, t1, s):
    """Corners of a band along the worm axis from t0 to t1, +-s across it (end view)."""
    return [L['P'](t, k) for t in (t0, t1) for k in (-s, s)]


def inside(pt, margin=WALL):
    y, z = pt
    if z < FLOOR + margin or abs(y) > HW - margin:
        return False
    top = SLOT_TOP - 1.0 if abs(y) < HW - LIP_IN - 1.5 else H - LIP_H - margin   # 1 mm cover in the slot (v0.3 dome)
    return z <= top


def evaluate(L):
    """Returns (ok, report). All checks are in the end view; parts at different X only check what they share."""
    P, n, up = L['P'], L['n'], L['up']
    rep = {}
    # wand line: from the worm's lower end down through the corner notch
    t_exit = None
    t_low = -L['half'] if L['spur_end'] > 0 else L['tg'] - 2.5
    for k in range(400):
        t = t_low - 0.1 * k
        y, z = P(t)
        if z <= 0.0 or y <= -HW:
            t_exit = t
            break
    if t_exit is None:
        return False, 'wand never leaves the rail'
    ye, ze = P(t_exit)
    rep['wand_exit'] = (round(ye, 1), round(ze, 1))
    if not (-HW - 2.0 <= ye <= NOTCH_FLOOR_EDGE[0] - 1.0 and ze <= NOTCH_WALL_TOP[1] - 1.0):
        return False, 'wand misses the notch'
    seg = (P(t_low), P(t_exit - 8))
    rep['wand_clear'] = round(min(seg_dist(NOTCH_WALL_TOP, *seg), seg_dist(NOTCH_FLOOR_EDGE, *seg)) - WAND_R, 2)
    if rep['wand_clear'] < 0:
        return False, 'wand hits a notch edge'
    # worm (OD + 0.5 running room) inside the case, on its whole thread + bearings
    # threads at full OD; the free end beyond them is just a pin journal (r 2.7 + wall), like the factory worm's top pin
    worm = rect_pts(L, -L['half'], L['half'], L['ra1'] + 0.5)
    free_end = -L['spur_end'] * (L['half'] + 3.0)
    worm += [L['P'](free_end, k) for k in (-2.7, 2.7)]
    if not all(inside(p) for p in worm):
        return False, 'worm outside the case'
    # wheel: tips + room under the top
    if not inside((0, ROD[1] + L['ra_w'] + 0.5)):
        return False, 'wheel too tall'
    # worm gear at the upper end (X = 0, same plane as the wheel)
    wg = rect_pts(L, L['tg'] - 2.5, L['tg'] + 2.5, L['ra_g'] + 0.5)
    if not all(inside(p) for p in wg):
        return False, 'worm gear outside the case'
    wg_seg = (P(L['tg'], -L['ra_g']), P(L['tg'], L['ra_g']))
    rep['wormgear_wheel'] = round(min(seg_dist(ROD, P(L['tg'] + s, -L['ra_g']), P(L['tg'] + s, L['ra_g']))
                                      for s in (-2.5, 2.5)) - L['ra_w'] - 0.5, 2)
    if rep['wormgear_wheel'] < 0.5:
        return False, 'worm gear hits the wheel'
    # motor: lies along the worm on the lid side (X = -cd_s), from the gear back toward the wand end
    if L['cd_s'] - MO_W / 2 < L['ra1'] + 0.8:
        return False, 'motor too close to the worm (needs a bigger spur pair)'
    t_m0 = L['tg'] + L['motor_dir'] * (2.5 + MO_GAP)
    t_m1 = t_m0 + L['motor_dir'] * MO_LEN
    mot = rect_pts(L, min(t_m0, t_m1), max(t_m0, t_m1), MO_H / 2 + 0.3)
    if not all(inside(p) for p in mot):
        return False, 'motor outside the case'
    mot_seg = (P(t_m0), P(t_m1))
    rep['motor_rod'] = round(seg_dist(ROD, *mot_seg) - MO_H / 2 - HUB_R, 2)
    if rep['motor_rod'] < 1.0:
        return False, 'motor hits the rod'
    rep['motor_floor'] = round(min(p[1] for p in mot) - FLOOR, 2)
    rep['top_used'] = round(max(ROD[1] + L['ra_w'], max(p[1] for p in wg)), 1)
    # sensor gear: meshes with the wheel; the shaft (r 4.2 incl. the magnet head) runs through the lid past the motor
    zs = max(12, math.ceil(L['zw'] * TRAVEL_DEG / 330.0))    # keep the magnet under one turn
    rs = zs * L['m'] / 2
    best = None
    for k in range(0, 181, 3):
        ang = math.radians(k)
        c = (ROD[0] + (L['R'] + rs + 0.15) * math.cos(ang), ROD[1] + (L['R'] + rs + 0.15) * math.sin(ang))
        if not inside((c[0], c[1] + rs + L['m']), WALL) or not inside((c[0], c[1] - rs - L['m']), WALL) \
                or not inside((c[0] + rs + L['m'], c[1]), WALL) or not inside((c[0] - rs - L['m'], c[1]), WALL):
            continue
        clear_worm = seg_dist(c, P(min(-L['half'] - 3, L['tg'] - 2.5)), P(max(L['half'] + 3, L['tg'] + 2.5))) \
            - max(L['ra1'], L['ra_g']) - rs - L['m'] - 0.5
        clear_motor = seg_dist(c, *mot_seg) - MO_H / 2 - 4.2 - 1.0
        score = min(clear_worm, clear_motor)
        if clear_worm > 0 and clear_motor > 0 and (best is None or score > best[0]):
            best = (score, k, c)
    if best is None:
        return False, 'no room for the sensor gear'
    rep['sensor'] = dict(z=zs, at_deg=best[1], center=(round(best[2][0], 1), round(best[2][1], 1)), clear=round(best[0], 1))
    # performance
    k_s = L['zg'] / L['zp']
    rep['wand_turns'] = round(L['zw'] * TRAVEL_DEG / 360.0, 1)
    rep['motor_s'] = round(rep['wand_turns'] * k_s / RPS, 1)
    rep['lead_deg'] = round(L['lam'], 1)
    rep['spur'] = '%d:%d m%.1f' % (L['zp'], L['zg'], L['ms'])
    return True, rep


def search():
    out = []
    for m in (0.8, 1.0, 1.25):
        for zw in range(12, 27):
            for d1 in (8.0, 9.0, 10.0, 11.0, 12.0):
                if math.degrees(math.atan(m / d1)) > 6.0:      # self-locking with greased printed plastic
                    continue
                for th in range(MIN_WAND_ANGLE, 71, 1):
                  for side in (1, -1):
                    for spur_end in (1, -1):
                      for motor_dir in (1, -1):
                        for ms in (0.8, 1.0):
                          for zp in (10, 11, 12):
                            for zg in range(zp, zp + 7):
                                L = worm_layout(m, zw, d1, th, zg, zp, ms, side, spur_end, motor_dir)
                                ok, rep = evaluate(L)
                                if ok:
                                    out.append((L, rep))
    return out


def score(L, rep):
    """Wand feel close to the factory (11-12 turns), robust teeth, ~3 s travel, margins."""
    s = -abs(rep['wand_turns'] - 11.5) * 1.0
    s += {0.8: 0, 1.0: 2.0, 1.25: 2.5}[L['m']]
    s -= max(0, rep['motor_s'] - 4.0) * 1.5 + max(0, 2.0 - rep['motor_s']) * 1.5
    s += min(rep['wand_clear'], 2.0) + min(rep['motor_rod'], 3.0) * 0.5 + min(rep['wormgear_wheel'], 2.0) * 0.5
    s += min(rep['sensor']['clear'], 3.0) * 0.3
    s -= abs(L['th'] - 60) * 0.08                              # wand hangs like the factory one
    return s


def svg(L, rep, path, title):
    sc, ox, oy = 9.0, 300, 420           # mm -> px; origin (Y=0, Z=0) at (ox, oy)
    X = lambda y: ox + y * sc
    Y = lambda z: oy - z * sc
    P = L['P']
    el = []
    def poly(pts, fill, stroke='#222', op=1.0):
        el.append('<polygon points="%s" fill="%s" fill-opacity="%.2f" stroke="%s" stroke-width="1.2"/>' % (
            ' '.join('%.1f,%.1f' % (X(p[0]), Y(p[1])) for p in pts), fill, op, stroke))
    def circ(c, r, fill, stroke='#222', op=1.0, dash=False):
        el.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="%.2f" stroke="%s" stroke-width="1.2"%s/>' % (
            X(c[0]), Y(c[1]), r * sc, fill, op, stroke, ' stroke-dasharray="4 3"' if dash else ''))
    def band(t0, t1, s, fill, op=1.0):
        poly([P(t0, -s), P(t1, -s), P(t1, s), P(t0, s)], fill, op=op)
    def text(y, z, s, size=13, anchor='start'):
        el.append('<text x="%.1f" y="%.1f" font-family="Helvetica,Arial" font-size="%d" text-anchor="%s" fill="#111">%s</text>' % (
            X(y), Y(z), size, anchor, s))
    # rail (gray) with the corner notch
    rail = [(-HW - 2, H), (-HW, H), (-HW, 10), (-29.75, 10), (-29.75, -2), (-19.25, -2), (-19.25, 0), (HW, 0), (HW, H),
            (HW + 2, H), (HW + 2, -2), (-19.25 + 0.01, -2), (-19.25, -2)]
    poly([(-HW - 2, H), (-HW, H), (-HW, 10), (-HW - 2, 10)], '#9aa0a6')
    poly([(-19.25, 0), (HW, 0), (HW, -2), (-19.25, -2)], '#9aa0a6')
    poly([(HW, -2), (HW + 2, -2), (HW + 2, H), (HW, H)], '#9aa0a6')
    poly([(-HW, H), (-HW + LIP_IN, H), (-HW + LIP_IN, H - 0.8), (-HW, H - 0.8)], '#9aa0a6')
    poly([(HW, H), (HW - LIP_IN, H), (HW - LIP_IN, H - 0.8), (HW, H - 0.8)], '#9aa0a6')
    # case outline (dashed): the press-fit block
    el.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#3949ab" stroke-dasharray="6 4"/>' % (
        X(-HW + 0.05), Y(H - LIP_H), (2 * HW - 0.1) * sc, (H - LIP_H - FLOOR) * sc))
    # motor (behind, lid side) first so the worm draws over it
    t_m0 = L['tg'] + L['motor_dir'] * (2.5 + MO_GAP)
    t_m1 = t_m0 + L['motor_dir'] * MO_LEN
    band(t_m0, t_m1, MO_H / 2, '#b0bec5', 0.9)
    text(*P((t_m0 + t_m1) / 2, MO_H / 2 + 1.5), 'N20 (lid side)', 12, 'middle')
    circ(ROD, HUB_R, 'none', dash=True)
    # wheel + rod
    circ(ROD, L['ra_w'], '#ffb74d', op=0.9)
    circ(ROD, L['R'], 'none', dash=True)
    poly([(ROD[0] - 2, ROD[1] - 2), (ROD[0] + 2, ROD[1] - 2), (ROD[0] + 2, ROD[1] + 2), (ROD[0] - 2, ROD[1] + 2)], '#eceff1')
    # sensor gear
    s = rep['sensor']
    circ(s['center'], s['z'] * L['m'] / 2 + L['m'], '#81c784', op=0.9)
    circ(s['center'], 3.0, '#5d4037')
    # worm, worm gear, wand
    band(-L['half'], L['half'], L['ra1'], '#ffd54f')
    band(L['half'] if L['spur_end'] > 0 else -L['half'], L['tg'] - 2.5 * L['spur_end'], 2.5, '#ffd54f')
    band(L['tg'] - 2.5, L['tg'] + 2.5, L['ra_g'], '#fff176')
    t_low = -L['half'] if L['spur_end'] > 0 else L['tg'] - 2.5
    band(t_low - 30, t_low, 3.0, '#ffe082')
    text(*P(0, L['ra1'] + 2.5), 'worm', 12, 'middle')
    text(*P(L['tg'], L['ra_g'] + 2.0), 'spur', 12, 'middle')
    text(ROD[0], ROD[1] + L['ra_w'] + 1.0, 'wheel %dT' % L['zw'], 12, 'middle')
    text(s['center'][0], s['center'][1] - 1.2, 'sensor', 11, 'middle')
    text(*P(t_low - 22, 6), 'wand', 12)
    # caption
    lines = [title,
             'wheel %dT m%.2g on the rod, worm d%.0f single start (lead %.1f deg, self-locking), worm at %d deg' % (
                 L['zw'], L['m'], L['d1'], rep['lead_deg'], L['th']),
             'spur %s to the N20 (lid side); wand %.1f turns end to end; motor %.1f s end to end (300 RPM N20)' % (
                 rep['spur'], rep['wand_turns'], rep['motor_s']),
             'margins: wand-notch %.1f, motor-rod %.1f, spur-wheel %.1f, motor-floor %.1f, sensor %.1f mm' % (
                 rep['wand_clear'], rep['motor_rod'], rep['wormgear_wheel'], rep['motor_floor'], s['clear'])]
    cap = ''.join('<text x="20" y="%d" font-family="Helvetica,Arial" font-size="%d" fill="#111">%s</text>' % (
        24 + 20 * i, 16 if i == 0 else 13, t) for i, t in enumerate(lines))
    open(path, 'w').write('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="520" viewBox="0 0 640 520">'
                          '<rect width="640" height="520" fill="#ffffff"/>%s<g transform="translate(0,40)">%s</g></svg>'
                          % (cap, ''.join(el)))


if __name__ == '__main__':
    res = search()
    print('%d layouts fit' % len(res))
    res.sort(key=lambda lr: -score(*lr))
    # pick distinct options: best overall, then the best with a different module / tooth count
    picks, seen = [], set()
    for L, rep in res:
        key = (L['side'], L['spur_end'], L['motor_dir'])
        if key in seen:
            continue
        seen.add(key)
        picks.append((L, rep))
        if len(picks) == 3:
            break
    for i, (L, rep) in enumerate(picks):
        print('\nOption %s: m%.2g wheel %dT, worm d%.0f at %d deg (%s the rod), spur %s at the %s end, motor toward the %s' % (
            'ABC'[i], L['m'], L['zw'], L['d1'], L['th'], 'below/behind' if L['side'] > 0 else 'above/room side of',
            rep['spur'], 'upper' if L['spur_end'] > 0 else 'lower', 'upper end' if L['motor_dir'] > 0 else 'wand'))
        for k, v in rep.items():
            print('   %-15s %s' % (k, v))
        svg(L, rep, os.path.join(REPO, 'docs/renders/v04-layout-%s.svg' % 'ABC'[i]), 'v0.4 option %s (end view, looking along the rod)' % 'ABC'[i])
