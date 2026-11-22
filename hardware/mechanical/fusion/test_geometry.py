"""Checks on the pure geometry (no Fusion needed):  python3 -m unittest hardware/mechanical/fusion/test_geometry.py"""

import importlib.util
import math
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path):
    spec = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(path))[0], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GG = _load(os.path.join(_HERE, 'Tilter', 'gear_geom.py'))
FIT = GG.FIT
g = GG.G


class GearTrain(unittest.TestCase):
    def test_ratio_is_20(self):
        ratio = (g['z20'] / g['z9']) * (g['z27'] / g['z9b']) * (1 + g['zr'] / g['zs'])
        self.assertAlmostEqual(ratio, 20.0, places=9)

    def test_planets_fit(self):
        self.assertEqual(g['zr'], g['zs'] + 2 * g['zp'])                       # sun, planets and ring share one center
        self.assertEqual((g['zr'] + g['zs']) % g['n_planets'], 0)             # equal spacing: (ring + sun) / planets whole
        self.assertAlmostEqual(GG.R_ORBIT, GG.GR['rp'] - GG.GP['rp'], places=9)
        # profile shifts cancel, so the plain pitch-circle center distances hold
        self.assertAlmostEqual(GG.GS['x'] + GG.GP['x'], 0.0)
        self.assertAlmostEqual(GG.GR['x'] - GG.GP['x'], 0.0)

    def test_planets_clear_each_other(self):
        pcs = GG.planet_centers()
        for i in range(len(pcs)):
            for j in range(i + 1, len(pcs)):
                self.assertGreater(math.dist(pcs[i], pcs[j]), 2 * GG.GP['ra'] + 0.5)

    def test_cluster_and_motor_on_their_centers(self):
        self.assertAlmostEqual(math.dist(GG.ROD, GG.CL), GG.G27['rp'] + GG.G9B['rp'], places=9)
        self.assertAlmostEqual(math.dist(GG.CL, GG.MO), GG.G20['rp'] + GG.G9['rp'], places=9)

    def test_stations_run_toward_minus_x(self):
        order = ['floor0', 'floor1', 'disc0', 'disc1', 'pl0', 'pl1', 'wall0', 'wall1', 'd0', 'd1', 'a0', 'a1',
                 'plate0', 'plate1']
        xs = [GG.X[k] for k in order]
        self.assertEqual(xs, sorted(xs, reverse=True))


class RodBores(unittest.TestCase):
    def test_square_bores_fit_the_rod(self):
        self.assertGreater(FIT.ROD_BORE, FIT.ROD)                                 # every square bore

    def test_round_bores_clear_a_turning_rod(self):
        for r in (FIT.ROD_HOLE_R, g['sun_bore'], g['nose_r'], g['wheel_bore_hub'], GG.P['barrel_r']):
            self.assertGreater(r, FIT.ROD_CORNER_R)

    def test_sleeve_runs_inside_the_sun(self):
        self.assertGreater(g['sun_bore'], g['nose_r'])
        self.assertGreater(g['nose_r'], FIT.ROD_BORE * math.sqrt(2) / 2)   # wall round the square bore

    def test_carrier_hub_inside_the_wheel(self):
        self.assertGreater(g['wheel_bore_hub'], g['hub_r'])
        self.assertGreater(g['hub_r'], FIT.ROD_BORE * math.sqrt(2) / 2)


class Worm(unittest.TestCase):
    def test_self_locking(self):
        self.assertLess(GG.worm_dims()['lead_deg'], 6.0)

    def test_layout(self):
        L = GG.layout()
        self.assertAlmostEqual(GG.norm(L['d']), 1.0)
        self.assertAlmostEqual(GG.dot(L['d'], L['n']), 0.0)
        self.assertAlmostEqual(math.dist(L['p0'], L['rod_c']), L['wheel']['cd'])
        self.assertLess(L['wheel']['rf'], L['wheel']['R'])
        self.assertLess(L['wheel']['R'], L['wheel']['ra'])

    def test_wheel_section(self):
        wh = GG.wheel_dims()
        pts = GG.wheel_section(0.0)
        self.assertEqual(len(pts), wh['z'] * GG.P['wheel_pts'])
        rs = [math.hypot(*q) for q in pts]
        self.assertGreater(min(rs), wh['rf'] - 0.31)
        self.assertLessEqual(max(rs), wh['ra'] + 1e-9)
        self.assertGreater(max(rs) - min(rs), 1.0)                            # it has teeth

    def test_case_pockets(self):
        cav = GG.worm_case_cavities(GG.layout())
        self.assertEqual(len({c.label for c in cav}), len(cav))
        wheel = cav[0]
        self.assertTrue(wheel.contains((0.0, 0.0, GG.P['rod_z'])))
        self.assertFalse(wheel.contains((0.0, 30.0, GG.P['rod_z'])))


class Fits(unittest.TestCase):
    def test_holes_bigger_than_what_goes_in(self):
        self.assertGreater(2 * FIT.M3_R, 3.0)
        self.assertGreater(FIT.CSINK_R, FIT.M3_R)
        self.assertGreater(FIT.CSINK_CTRL_R, FIT.M3_R)
        self.assertGreater(2 * FIT.M1_6_R, 1.6)
        self.assertGreater(FIT.M1_6_HEAD_R, FIT.M1_6_R)
        self.assertGreater(FIT.PEG_CLEAR, 0)
        self.assertGreater(FIT.PEG_DEPTH_EXTRA, 0)

    def test_inserts(self):
        self.assertGreater(FIT.INSERT_R, FIT.M3_R)
        for n in (FIT.INSERT_LEN, FIT.INSERT_LEN_TILTER):
            self.assertGreaterEqual(n, FIT.INSERT_LEN_MIN)                     # the inserts need 6.7 at least
            self.assertLess(n, 8.0)

    def test_rod_inside_the_rail(self):
        self.assertLess(FIT.ROD_Z + FIT.ROD_CORNER_R, FIT.RAIL_H - FIT.LIP_H)


if __name__ == '__main__':
    unittest.main()
