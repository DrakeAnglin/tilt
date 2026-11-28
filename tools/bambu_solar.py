"""Build the solar housing's Bambu Studio project: the tray sections and the end cap for a panel count, packed close
together (arranged on as few plates as they fit).

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_solar.py --timeout 600   # first: the STLs
  python3 tools/bambu_solar.py 3          # writes hardware/mechanical/stl/solar/solar_housing_3_H2D.3mf (wires right)
  python3 tools/bambu_solar.py 6 --left   # writes solar_housing_6_wires_left_H2D.3mf

H2D 0.4 nozzle, 0.20 mm Standard, white PLA on textured PEI, no supports (the lips are 45 degrees). Both parts lie as
exported: back on the bed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bambu import CLI, flatten  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STL = os.path.join(REPO, 'hardware/mechanical/stl/solar')
PRESETS = (('machine', 'Bambu Lab H2D 0.4 nozzle'), ('process', '0.20mm Standard @BBL H2D'),
           ('filament', 'Bambu PLA Basic @BBL H2D'))
# the pieces for each panel count (tools/fusion_solar.py PIECES)
PIECES = {1: ['start_1'], 2: ['start_2'], 3: ['start_3'], 4: ['start_2', 'add_2'], 5: ['start_3', 'add_2'],
          6: ['start_3', 'add_3']}
TWEAKS = {'filament_colour': ['#FFFFFF'], 'enable_support': '0', 'curr_bed_type': 'Textured PEI Plate'}


def main(n=3, left=False):
    tag = '_wires_left' if left else ''
    stls = [os.path.join(STL, 'solar_%s%s.stl' % (p, tag)) for p in PIECES[n] + ['cap']]
    for s in stls:
        if not os.path.exists(s):
            sys.exit('%s is missing: run tools/fusion_solar.py first' % os.path.relpath(s, REPO))
    out = os.path.join(STL, 'solar_housing_%d%s_H2D.3mf' % (n, tag))
    tmp = tempfile.mkdtemp()
    files = []
    for k, (kind, name) in enumerate(PRESETS):
        d = flatten(kind, name)
        d.pop('inherits', None)
        d.update({'from': 'system', 'instantiation': 'true', 'name': name})
        path = os.path.join(tmp, '%s%d.json' % (kind, k))
        json.dump(d, open(path, 'w'), indent=1)
        files.append(path)
    raw = os.path.join(tmp, 'raw.3mf')
    subprocess.run([CLI, '--debug', '1', '--load-settings', files[0] + ';' + files[1], '--load-filaments', files[2],
                    '--arrange', '1', '--orient', '0', '--export-3mf', raw] + stls,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    src = zipfile.ZipFile(raw)
    settings = json.loads(src.read('Metadata/project_settings.config'))
    settings.update(TWEAKS)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename == 'Metadata/project_settings.config':
                dst.writestr(info, json.dumps(settings, indent=4))
            else:
                dst.writestr(info, src.read(info.filename))
    shutil.rmtree(tmp)
    print('wrote', os.path.relpath(out, REPO))


def run(argv):
    """The command line: a panel count (default 3) and --left."""
    nums = [int(a) for a in argv if a.isdigit()]
    main(nums[0] if nums else 3, left='--left' in argv)


if __name__ == '__main__':
    run(sys.argv[1:])
