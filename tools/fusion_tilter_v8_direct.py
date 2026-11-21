"""Fewest-gears test for tilter v0.8: ONE long cluster on the P axle replaces P1, R1 and P2.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_tilter_v8_direct.py --timeout 900

motor 9T -> 20T | 9T (one piece, the whole depth of the gear room) -> the sun piece's 27T.  Ratio 21:1 (stock 88:1):
4.2 x the speed, under a quarter of the torque. This is v0.6's ratio, which stalled on the medium blind.
The motor's 9T pinion and the sun piece stay. The tube stays bare. STL: hardware/mechanical/stl/v0.8/fast_gears/.
"""
import json
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
stock = T8.make_parts(S)
fixed = {k: stock[k] for k in ('Sun + 27T', 'Motor pinion 9T')}
fixed['Motor shell'] = T8.motor_shell(S)
fixed['Bearing shell'] = T8.bearing_shell(S)

c = S.U(S.gear(T8.G9B, CL, ph['g9b'], X['a0'], X['d0'] - 0.01), S.gear(T8.G20, CL, ph['g20'], X['d0'], X['d1']))
S.D(c, S.cyl(CL, g['axle_bore'], X['a0'] + 1, X['d1'] - 1))
hits = []
for fn, fb in fixed.items():
    v, where = T8._vol(tbm, c, fb)
    if v > 0.02:
        hits.append('%s: %.2f mm3 at %s' % (fn, v, where))
worst = 0.0
for i in range(41):
    t = (2 * math.pi / g['z9b']) * 2.0 * i / 40
    a = T8._rot(tbm, c, t, CL)
    worst = max(worst, T8._vol(tbm, a, T8._rot(tbm, fixed['Sun + 27T'], -t * g['z9b'] / g['z27'], ROD))[0])
    worst = max(worst, T8._vol(tbm, a, T8._rot(tbm, fixed['Motor pinion 9T'], -t * g['z20'] / g['z9'], MO))[0])
    worst = max(worst, T8._vol(tbm, a, fixed['Motor shell'])[0], T8._vol(tbm, a, fixed['Bearing shell'])[0])
S.done()
occ, comp = T4.new_component(root, 'Direct cluster 20T-9T')
T4.add_bodies(comp, [('Direct cluster 20T-9T', c)])
os.makedirs(OUT, exist_ok=True)
opt = design.exportManager.createSTLExportOptions(comp, os.path.join(OUT, 'direct_cluster.stl'))
opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
design.exportManager.execute(opt)
ratio = (g['z20'] / g['z9']) * (g['z27'] / g['z9b']) * (1 + g['zr'] / g['zs'])
print(json.dumps(dict(ratio=round(ratio, 1), speed_x=round(88.0 / ratio, 2), length_mm=round(X['a0'] - X['d1'], 1), standing_hits=hits, turning_worst_mm3=round(worst, 3)), indent=1))
