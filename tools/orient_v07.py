"""Rotate the v0.7 test-rig STLs into their print orientations (support-free) and drop them onto Z=0.

  python3 tools/orient_v07.py        # writes hardware/mechanical/stl/v0.7/print/*.stl
"""
import importlib.util
import os
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location('o4', os.path.join(REPO, 'tools/orient_v04.py'))
o4 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(o4)
SRC = os.path.join(REPO, 'hardware/mechanical/stl/v0.7')
OUT = os.path.join(SRC, 'print')
ID, FLIP, X_UP, X_DOWN = o4.ID, o4.FLIP, o4.X_UP, o4.X_DOWN

ORIENT = {   # only the parts that changed from v0.6 (ring cup, planets, sun piece, worm wheel, lid: reuse)
    'gear_r1': (X_DOWN, '27T down, 15T up'),
    'cluster_p1': (X_DOWN, '20T down'),
    'cluster_p2': (X_DOWN, '21T down'),
    'motor_pinion': (X_DOWN, 'flat'),
    'carrier': (X_DOWN, 'disc down, hub up (dowel holes now go right through)'),
    'bearing_plate': (X_DOWN, 'flat face down, bosses up'),
    'motor_plate': (X_DOWN, 'motor face down, tube and standoffs up'),
}

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for name, (rot, how) in ORIENT.items():
        tris, size = o4.orient(o4.read(os.path.join(SRC, name + '.stl')), rot)
        o4.write(os.path.join(OUT, name + '.stl'), tris)
        print('%-15s %5.1f x %5.1f x %5.1f mm  %s' % (name, size[0], size[1], size[2], how))
