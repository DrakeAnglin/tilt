"""Build the solar housing's Bambu Studio project: the tray and the end cap on one plate, packed close together.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_solar.py --timeout 600   # first: the STLs
  python3 tools/bambu_solar.py            # writes hardware/mechanical/stl/solar/solar_housing_H2D.3mf (wires right)
  python3 tools/bambu_solar.py --left     # writes solar_housing_wires_left_H2D.3mf

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
TWEAKS = {'filament_colour': ['#FFFFFF'], 'enable_support': '0', 'curr_bed_type': 'Textured PEI Plate'}


def main(left=False):
    tag = '_wires_left' if left else ''
    stls = [os.path.join(STL, 'solar_%s%s.stl' % (p, tag)) for p in ('tray', 'cap')]
    for s in stls:
        if not os.path.exists(s):
            sys.exit('%s is missing: run tools/fusion_solar.py first' % os.path.relpath(s, REPO))
    out = os.path.join(STL, 'solar_housing%s_H2D.3mf' % tag)
    tmp = tempfile.mkdtemp()
    files = []
    for n, (kind, name) in enumerate(PRESETS):
        d = flatten(kind, name)
        d.pop('inherits', None)
        d.update({'from': 'system', 'instantiation': 'true', 'name': name})
        path = os.path.join(tmp, '%s%d.json' % (kind, n))
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


if __name__ == '__main__':
    main(left='--left' in sys.argv)
