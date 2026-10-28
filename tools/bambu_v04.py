"""Build the v0.4 Bambu Studio project from the oriented STLs (tools/orient_v04.py) for the owner's H2D.

  python3 tools/bambu_v04.py        # writes hardware/mechanical/stl/v0.4/tilter_v04_H2D_white_PLA.3mf

- System presets (H2D 0.4 nozzle, 0.12 mm Fine, Bambu PLA Basic) are flattened first: the Bambu CLI does not
  resolve preset inheritance, so un-flattened presets silently fall back to defaults (e.g. 0.2 mm layers).
- Project tweaks: white filament, 4 walls, 40 % infill, 8 mm outer brim (the one-piece worm stands 54 mm tall),
  tree supports from the build plate only.
- Parts are laid out square to the bed at fixed spots (the CLI's auto-arrange spins parts about Z).
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRINT = os.path.join(REPO, 'hardware/mechanical/stl/v0.4/print')
OUT = os.path.join(REPO, 'hardware/mechanical/stl/v0.4/tilter_v04_H2D_white_PLA.3mf')
SYSTEM = os.path.expanduser('~/Library/Application Support/BambuStudio/system/BBL')
CLI = '/Applications/BambuStudio.app/Contents/MacOS/BambuStudio'

PRESETS = (('machine', 'Bambu Lab H2D 0.4 nozzle'), ('process', '0.12mm Fine @BBL H2D'),
           ('filament', 'Bambu PLA Basic @BBL H2D'))
TWEAKS = {'filament_colour': ['#FFFFFF'], 'wall_loops': '4', 'sparse_infill_density': '40%',
          'brim_type': 'outer_only', 'brim_width': '8',
          # owner asked for supports: tree supports from the build plate only (never inside the case's gear pockets
          # and bearing bores, where support marks would land on running surfaces); 30° so the 45° gear and thread
          # flanks aren't supported
          'enable_support': '1', 'support_type': 'tree(auto)', 'support_on_build_plate_only': '1',
          'support_threshold_angle': '30'}
# part -> centre on the bed (mm); H2D plate is 350 x 320. Brims are 8 mm, so parts sit >= 20 mm apart.
LAYOUT = {'case_left': (110, 160), 'case_right': (172, 160), 'worm': (218, 140), 'worm_wheel': (218, 182),
          'motor_pinion': (250, 140), 'sensor_gear': (254, 182)}


def flatten(kind, name):
    d = json.load(open(os.path.join(SYSTEM, kind, name + '.json')))
    if d.get('inherits'):
        base = flatten(kind, d['inherits'])
        base.update(d)
        d = base
    return d


def main():
    tmp = tempfile.mkdtemp()
    files = []
    for kind, name in PRESETS:
        d = flatten(kind, name)
        d.pop('inherits', None)
        d.update({'from': 'system', 'instantiation': 'true', 'name': name})
        path = os.path.join(tmp, kind + '.json')
        json.dump(d, open(path, 'w'), indent=1)
        files.append(path)
    raw = os.path.join(tmp, 'raw.3mf')
    stls = [os.path.join(PRINT, n + '.stl') for n in LAYOUT]
    subprocess.run([CLI, '--debug', '1', '--load-settings', files[0] + ';' + files[1], '--load-filaments', files[2],
                    '--arrange', '1', '--orient', '0', '--export-3mf', raw] + stls,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    src = zipfile.ZipFile(raw)
    # object id -> part name (the project's object list is not in load order)
    part_of = dict(re.findall(r'<object id="(\d+)">\s*<metadata key="name" value="([^"]+)\.stl"',
                              src.read('Metadata/model_settings.config').decode()))
    model = src.read('3D/3dmodel.model').decode()

    def square(m):
        x, y = LAYOUT[part_of[m.group(2)]]
        z = m.group(3).split()[11]
        return '%stransform="1 0 0 0 1 0 0 0 1 %g %g %s"' % (m.group(1), x, y, z)   # no spin about Z
    model = re.sub(r'(<item objectid="(\d+)"[^>]*?)transform="([^"]+)"', square, model)
    order = [part_of[i] for i in re.findall(r'<item objectid="(\d+)"', model)]
    settings = json.loads(src.read('Metadata/project_settings.config'))
    settings.update(TWEAKS)
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename == '3D/3dmodel.model':
                dst.writestr(info, model)
            elif info.filename == 'Metadata/project_settings.config':
                dst.writestr(info, json.dumps(settings, indent=4))
            elif not info.filename.endswith('.png'):         # plate thumbnails are stale after the re-layout
                dst.writestr(info, src.read(info.filename))
    shutil.rmtree(tmp)
    print('wrote', os.path.relpath(OUT, REPO), 'with', ', '.join(order))


if __name__ == '__main__':
    main()
