"""Rotate the v0.6 test-rig STLs into their print orientations (support-free) and drop them onto Z=0.

  python3 tools/orient_v06.py        # writes hardware/mechanical/stl/v0.6/print/*.stl
"""
import importlib.util
import os
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location('o4', os.path.join(REPO, 'tools/orient_v04.py'))
o4 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(o4)
SRC = os.path.join(REPO, 'hardware/mechanical/stl/v0.6')
OUT = os.path.join(SRC, 'print')
ID, FLIP, X_UP, X_DOWN = o4.ID, o4.FLIP, o4.X_UP, o4.X_DOWN

ORIENT = {
    'case_left': (X_DOWN, 'lid: outer face down'),
    'worm_wheel': (FLIP, 'plain barrel end down, hex up'),
    'ring_cup': (X_UP, 'floor down, open end up'),
    'carrier': (X_DOWN, 'disc down (dowel holes on the bed), hub up'),
    'planet': (X_DOWN, 'flat (print 4)'),
    'sun_27t': (X_DOWN, '27T down, sun up'),
    'cluster': (X_DOWN, '20T down'),
    'motor_pinion': (X_DOWN, 'flat'),
    'bearing_plate': (X_DOWN, 'flat face down, bosses up'),
    'motor_plate': (X_DOWN, 'motor face down, standoffs up'),
}

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for name, (rot, how) in ORIENT.items():
        tris, size = o4.orient(o4.read(os.path.join(SRC, name + '.stl')), rot)
        o4.write(os.path.join(OUT, name + '.stl'), tris)
        print('%-15s %5.1f x %5.1f x %5.1f mm  %s' % (name, size[0], size[1], size[2], how))
    for k in (2, 3, 4):
        shutil.copy(os.path.join(OUT, 'planet.stl'), os.path.join(OUT, 'planet_%d.stl' % k))
