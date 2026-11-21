"""Rotate the v0.9 STLs into their print orientations (support-free) and drop them onto Z=0.

  python3 tools/orient_v08.py        # writes hardware/mechanical/stl/v0.9/print/*.stl
"""
import importlib.util
import os
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location('o4', os.path.join(REPO, 'tools/orient_v04.py'))
o4 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(o4)
SRC = os.path.join(REPO, 'hardware/mechanical/stl/v0.9')
OUT = os.path.join(SRC, 'print')
ID, FLIP, X_UP, X_DOWN = o4.ID, o4.FLIP, o4.X_UP, o4.X_DOWN
Y_DOWN = lambda x, y, z: (x, z, -y)         # 90° about X: +Y goes down onto the bed

ORIENT = {
    # housing
    'case_right': (X_UP, 'main half: back face down'),
    'case_left': (X_DOWN, 'lid: outer face down'),
    'bearing_shell': (X_DOWN, 'gear-side face down, cup bore up'),
    'motor_shell': (X_DOWN, 'motor face down, gear room up'),
    'tray': (ID, 'floor down, open top up'),
    'tray_lid': (FLIP, 'top face down, columns up; SUPPORT under the gear shelf'),
    'worm': (ID, 'standing on its thread end (brim), loop up'),
    # sensor
    'sensor_sleeve': (X_DOWN, 'gear face down on the bed, lugs up'),
    'magnet_gear': (FLIP, 'gear face down, magnet hub up'),
    # drive
    'worm_wheel': (FLIP, 'plain barrel end down, hex up'),
    'ring_cup': (X_UP, 'floor down, open end up'),
    'carrier': (X_DOWN, 'disc down, hub up'),
    'planet': (X_DOWN, 'flat (print 4)'),
    'sun_27t': (X_DOWN, '27T down, sun up'),
    'cluster': (X_UP, '20T down, 9T up'),
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
