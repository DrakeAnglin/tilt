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



class ControllerBox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.T = _load(os.path.join(_HERE, 'Controller', 'tilt_in.py'))
        cls.C = cls.T.C

    def test_tilts_into_the_rail_without_prying(self):
        self.assertLessEqual(self.T.min_spread(self.T.section(), STEP=0.5, ASTEP=2.0), 0.5)

    def test_wall_behind_the_bottom_bevel(self):
        c = self.C
        self.assertGreaterEqual((c['wall'] + c['floor'] + c['bevel_fill'] - c['bevel_bot']) / math.sqrt(2), 1.5)

    def test_rod_clears_the_groove(self):
        c = self.C
        self.assertGreaterEqual(FIT.ROD_Z - FIT.ROD_CORNER_R - c['groove_floor'], 1.75)     # room for the feet
        # no bumpers: wherever the box sits across the rail, the rod must stay off the groove's sides
        play = (FIT.RAIL_W - (c['out_hi'] - c['room_out'])) / 2
        self.assertLess(play, c['groove_r'] - FIT.ROD_CORNER_R)
        self.assertAlmostEqual(c['groove_y'], (c['room_out'] + c['out_hi']) / 2)

    def test_groove_channel_clears_the_esp_pin_tips(self):
        c, M = self.C, self.T.M
        tips = c['esp_z0'] + c['esp_t'] + c['esp_tip']
        y_in = M.K(19.74 + 0.32, 0)[1]                       # groove-side edge of the pin row nearest the groove
        self.assertGreaterEqual(M.z_under(y_in, c['groove_t']) - tips, 0.2)

    def test_solar_plug_fits_its_opening(self):
        _, w, h = self.C['solar']
        self.assertGreaterEqual(w, 4.5 + 1.0)       # JST-ZH 2-pin housing: 4.5 x 3.5
        self.assertGreaterEqual(h, 3.5 + 1.0)


V3 = _load(os.path.join(_HERE, 'ControllerV3', 'ControllerV3.py'))
V2 = _load(os.path.join(_HERE, 'Controller', 'Controller.py'))


class ControllerV3Fit(unittest.TestCase):
    """The v3 fit study's numbers (no Fusion): the same section and groove as the v2.2 box, and the cell's fit."""

    def test_section_and_groove_are_the_v22_box(self):
        c, o = V3.params(3), V2.C
        for k in ('room_out', 'back_in', 'top', 'wall', 'floor', 'lid', 'bevel_bot', 'bevel_top', 'groove_r', 'groove_t'):
            self.assertEqual(c[k], o[k], k)
        self.assertAlmostEqual(c['groove_floor'], o['groove_floor'])
        self.assertAlmostEqual(c['groove_y'], o['groove_y'])
        self.assertAlmostEqual(c['bat_zc'], o['bat_zc'])          # the cell lies where it lies in the v2.2 box
        self.assertAlmostEqual(c['bat_y'], o['bat_y'])

    def test_lengths(self):
        self.assertAlmostEqual(V3.params(3)['L'], 134.8, places=1)
        self.assertAlmostEqual(V3.params(1)['L'], 114.8, places=1)
        self.assertLess(V3.params(3)['L'], V2.C['L'])

    def test_cell_and_contacts(self):
        for ports in (1, 3):
            c = V3.params(ports)
            f = V3.facts(c)
            self.assertGreaterEqual(f['cell_top_to_lid'], 0.3)
            self.assertGreaterEqual(f['cell_to_groove_channel'], 3.0)
            self.assertGreaterEqual(f['cell_to_board_edge'], 1.0)
            self.assertLessEqual(abs(f['button_above_cell_axis']), 1.5)     # the button lands on a dia 5 button top
            for sq in f['leaf_squeeze'].values():                           # the leaf is pressed, and not solid
                self.assertGreaterEqual(sq, 0.8)
                self.assertLessEqual(sq, 3.4)
            self.assertTrue(all(v > 0 for v in f['cell_ends_inside_notch']))
            self.assertAlmostEqual(c['ct_x'][1] - c['ct_x'][0], c['bat_l'] + 2.3)   # Keystone's L for a 596 / 590 pair

    def test_room_under_the_lid(self):
        for ports in (1, 3):
            f = V3.facts(V3.params(ports))
            for k in ('esp_tips_to_lid', 'jack_top_to_lid', 'cap_top_to_lid', 'contact_top_to_lid'):
                self.assertGreater(f[k], 0.5, k)

    def test_jacks_and_holes(self):
        self.assertEqual(len(V3.jacks(V3.params(1))), 1)
        self.assertEqual(len(V3.jacks(V3.params(3))), 3)
        self.assertEqual(len(V3.holes(V3.params(1))), 3)
        self.assertEqual(len(V3.holes(V3.params(3))), 4)
        self.assertEqual(len(V3.outline_pts()), 8)


if __name__ == '__main__':
    unittest.main()
