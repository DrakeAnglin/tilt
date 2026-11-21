"""Faster motor-train test gears for tilter v0.8: drop-in swaps for P1 (cluster by the motor) and R1 (gear on the tube).

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_tilter_v8_fastgears.py --timeout 900

Same axles, same pockets, same stations; the pinion, P2 and the sun piece stay. Only the P1-small / R1-big mesh changes
(tooth sum stays 36 at module 1, so the centre distance stays 18 mm):
  stock  9T / 27T  -> 88:1
  set A 12T / 24T  -> 59:1   (1.5 x the speed, 2/3 of the torque)      one dot on each gear
  set B 15T / 21T  -> 41:1   (2.1 x the speed, under half the torque)  two dots on each gear
v0.6 ran 21:1 and stalled on the medium blind, so 41:1 is the bold one. STLs: hardware/mechanical/stl/v0.8/fast_gears/.
"""
import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
T8 = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltPartsV8/TiltPartsV8.py'))
OUT = os.path.join(REPO, 'hardware/mechanical/stl/v0.8/fast_gears')
g, X, CL, ROD, MO, T4 = T8.g, T8.X, T8.CL, T8.ROD, T8.MO, T8.T4

app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
design.designType = adsk.fusion.DesignTypes.DirectDesignType
root = design.rootComponent
S = T8.Shop(root)
tbm = S.tbm
ph = T8.phases()
psi1 = math.atan2(CL[1] - ROD[1], CL[0] - ROD[0])
SETS = {'A': (12, 24, 1), 'B': (15, 21, 2)}          # small on P1, big on R1, dots
stock = T8.make_parts(S)
fixed = {k: stock[k] for k in ('Sun + 27T', 'P2 21T/9T', 'Motor pinion 9T')}
fixed['Motor shell'] = T8.motor_shell(S)
fixed['Bearing shell'] = T8.bearing_shell(S)


def dots(body, c, r, x_face, n):                      # n small dimples on a face, to tell the sets apart
    for k in range(n):
        a = 2 * math.pi * k / 6
        cc = (c[0] + r * math.cos(a), c[1] + r * math.sin(a))
        S.D(body, S.cyl(cc, 0.55, x_face + 0.5, x_face - 0.5))


new, gears, report = {}, {}, {}
for tag, (zs, zb, nd) in SETS.items():
    gs, gb = T8.gear(zs, g['m2'], g['shift2']), T8.gear(zb, g['m2'], -g['shift2'])
    ps, pb = psi1 + math.pi + math.pi / zs, psi1
    p1 = S.U(S.gear(gs, CL, ps, X['c0'], X['d0'] - 0.01), S.gear(T8.G20, CL, ph['g20'], X['d0'], X['d1']))
    S.D(p1, S.cyl(CL, g['axle_bore'], X['c0'] + 1, X['d1'] - 1))
    dots(p1, CL, (g['axle_bore'] + gs['rf']) / 2, X['c0'], nd)
    r1 = S.U(S.gear(T8.G15, ROD, ph['g15'], X['b0'], X['c0'] - 0.01), S.gear(gb, ROD, pb, X['c0'], X['c1']))
    S.D(r1, S.cyl(ROD, g['tube_r'] + g['tube_clear'], X['b0'] + 1, X['c1'] - 1))
    dots(r1, ROD, (g['tube_r'] + g['tube_clear'] + T8.G15['rf']) / 2, X['b0'], nd)
    n1, n2 = 'P1 20T-%dT set %s' % (zs, tag), 'R1 %dT-15T set %s' % (zb, tag)
    new[n1], new[n2] = p1, r1
    gears[tag] = (n1, n2, zs, zb)
    ratio = (g['z20'] / g['z9']) * (zb / zs) * (g['z21'] / g['z15']) * (g['z27'] / g['z9b']) * (1 + g['zr'] / g['zs'])
    hits = []
    for nm, b in ((n1, p1), (n2, r1)):                # standing still, against everything that stays
        for fn, fb in fixed.items():
            v, where = T8._vol(tbm, b, fb)
            if v > 0.02:
                hits.append('%s / %s: %.2f mm3 at %s' % (nm, fn, v, where))
    v, where = T8._vol(tbm, p1, r1)
    if v > 0.02:
        hits.append('%s / %s: %.2f mm3 at %s' % (n1, n2, v, where))
    worst = 0.0                                       # turning: two tooth pitches of the small gear, fine steps
    for i in range(41):
        t = (2 * math.pi / zs) * 2.0 * i / 40
        a, b = T8._rot(tbm, p1, t, CL), T8._rot(tbm, r1, -t * zs / zb, ROD)
        worst = max(worst, T8._vol(tbm, a, b)[0])
        t2 = -t * zs / zb                             # R1's 15T against P2's 21T, and P1's 20T against the pinion
        worst = max(worst, T8._vol(tbm, b, T8._rot(tbm, fixed['P2 21T/9T'], -t2 * g['z15'] / g['z21'], CL))[0])
        worst = max(worst, T8._vol(tbm, a, T8._rot(tbm, fixed['Motor pinion 9T'], -t * g['z20'] / g['z9'], MO))[0])
    report[tag] = dict(ratio=round(ratio, 1), speed_x=round(88.0 / ratio, 2), small_tip_r=round(gs['ra'], 2), big_tip_r=round(gb['ra'], 2),
                       pocket_r_at_P1=round(T8.G20['ra'] + 0.66, 2), standing_hits=hits, turning_worst_mm3=round(worst, 3))
S.done()
os.makedirs(OUT, exist_ok=True)
em = design.exportManager
files = []
for nm, b in new.items():
    occ, comp = T4.new_component(root, nm)
    T4.add_bodies(comp, [(nm, b)])
    fn = nm.split(' ')[0].lower() + '_set' + nm[-1].lower() + '.stl'
    opt = em.createSTLExportOptions(comp, os.path.join(OUT, fn))
    opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    em.execute(opt)
    files.append(fn)
import json
print(json.dumps(dict(report=report, files=files), indent=1))
