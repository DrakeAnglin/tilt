"""Rotate the v0.5 tilter STLs into their print orientations (support-free) and drop them onto Z=0.

  python3 tools/orient_v05.py        # writes hardware/mechanical/stl/v0.5/print/*.stl

Uses tools/orient_v04.py's reader / writer. Cases, module, arm and plate are exported in the assembly frame
(X along the rod); the gears and the clutch shaft in their own frames (z = their axis).
"""
import glob
import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location('o4', os.path.join(REPO, 'tools/orient_v04.py'))
o4 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(o4)
SRC = os.path.join(REPO, 'hardware/mechanical/stl/v0.5')
OUT = os.path.join(SRC, 'print')
ID, FLIP, X_UP, X_DOWN = o4.ID, o4.FLIP, o4.X_UP, o4.X_DOWN

ORIENT = {
    'case_left': (X_DOWN, 'lid: outer face down'),
    'case_right': (X_UP, 'main half: back face down, pins up'),
    'sensor_module': (X_DOWN, 'end wall down, open face up'),
    'worm': (ID, 'standing on its thread end, loop up (brim)'),
    'worm_wheel': (ID, 'barrel end down'),
    'sensor_gear': (ID, 'gear face down, magnet pocket up'),
    'clutch_shaft': (ID, 'standing on the 7T face (pin hole down), shaft up'),
    'clutch_12t': (ID, 'flat'),
    'clutch_pinion': (FLIP, 'teeth down, hub up'),
    'clutch_idler': (ID, 'flat (print 2)'),
    'clutch_arm': (X_DOWN, 'flat, motor-side face down'),
    'clutch_plate': (X_DOWN, 'pocket down, stop post up'),
}

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(SRC, '*.stl'))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name not in ORIENT:
            continue
        rot, how = ORIENT[name]
        tris, size = o4.orient(o4.read(path), rot)
        o4.write(os.path.join(OUT, name + '.stl'), tris)
        print('%-15s %5.1f x %5.1f x %5.1f mm  %s' % (name, size[0], size[1], size[2], how))
    # the second idler: its own file so the project gets two objects
    import shutil
    shutil.copy(os.path.join(OUT, 'clutch_idler.stl'), os.path.join(OUT, 'clutch_idler_2.stl'))
