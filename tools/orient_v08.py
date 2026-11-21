"""Rotate the v0.8 STLs into their print orientations (support-free) and drop them onto Z=0.

  python3 tools/orient_v08.py        # writes hardware/mechanical/stl/v0.8/print/*.stl
"""
import importlib.util
import os
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location('o4', os.path.join(REPO, 'tools/orient_v04.py'))
o4 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(o4)
SRC = os.path.join(REPO, 'hardware/mechanical/stl/v0.8')
OUT = os.path.join(SRC, 'print')
ID, FLIP, X_UP, X_DOWN = o4.ID, o4.FLIP, o4.X_UP, o4.X_DOWN
Y_DOWN = lambda x, y, z: (x, z, -y)         # 90° about X: +Y goes down onto the bed

ORIENT = {
    # housing (all new)
    'case_right': (X_UP, 'main half: back face down'),
    'case_left': (X_DOWN, 'lid: outer face down'),
    'bearing_shell': (X_DOWN, 'gear-side face down, cup bore up'),
    'motor_shell': (X_DOWN, 'motor face down, gear room up'),
    'tray': (ID, 'floor down, open top up'),
    'tray_lid': (FLIP, 'top face down, columns up; SUPPORT under the gear shelf'),
    'rod_gear': (X_UP, 'long sleeve end down'),
    'magnet_gear': (FLIP, 'gear face down, magnet hub up'),
    'sensor_bar': (ID, 'lying flat on its side (rev K)'),
    'worm': (ID, 'standing on its thread end (brim), loop up'),
    # drive (same shapes as v0.7: reuse the printed ones)
    'worm_wheel': (FLIP, 'plain barrel end down, hex up'),
    'ring_cup': (X_UP, 'floor down, open end up'),
    'carrier': (X_DOWN, 'disc down, hub up'),
    'planet': (X_DOWN, 'flat (print 4)'),
    'sun_27t': (X_DOWN, '27T down, sun up'),
    'gear_r1': (X_DOWN, '27T down, 15T up'),
    'cluster_p1': (X_DOWN, '20T down'),
    'cluster_p2': (X_DOWN, '21T down'),
    'motor_pinion': (X_DOWN, 'flat'),
}

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for name, (rot, how) in ORIENT.items():
        tris, size = o4.orient(o4.read(os.path.join(SRC, name + '.stl')), rot)
        o4.write(os.path.join(OUT, name + '.stl'), tris)
        print('%-15s %5.1f x %5.1f x %5.1f mm  %s' % (name, size[0], size[1], size[2], how))
    for k in (2, 3, 4):
        shutil.copy(os.path.join(OUT, 'planet.stl'), os.path.join(OUT, 'planet_%d.stl' % k))
