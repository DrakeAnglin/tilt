"""Build the v0.6 planetary test rig Bambu Studio project: every new printed part on one plate, two materials.

  python3 tools/orient_v06.py && python3 tools/bambu_v06.py   # writes hardware/mechanical/stl/v0.6/tilter_v06_H2D_PLA_PETG.3mf

Filament 1 = PLA, filament 2 = PETG. Every pair of parts that rubs or meshes is PLA against PETG (see PETG below).
Same presets and method as tools/bambu_v05.py (H2D 0.4 nozzle, 0.12 mm Fine, 4 walls, 40 % infill).
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRINT = os.path.join(REPO, 'hardware/mechanical/stl/v0.6/print')
OUT = os.path.join(REPO, 'hardware/mechanical/stl/v0.6/tilter_v06_H2D_PLA_PETG.3mf')
SYSTEM = os.path.expanduser('~/Library/Application Support/BambuStudio/system/BBL')
CLI = '/Applications/BambuStudio.app/Contents/MacOS/BambuStudio'

PRESETS = (('machine', 'Bambu Lab H2D 0.4 nozzle'), ('process', '0.12mm Fine @BBL H2D'),
           ('filament', 'Bambu PLA Basic @BBL H2D'), ('filament', 'Bambu PETG Basic @BBL H2D 0.4 nozzle'))
# PETG is shown light gray in the slicer only so the two materials can be told apart; load white PETG.
TWEAKS = {'filament_colour': ['#FFFFFF', '#B8B8B8'], 'wall_loops': '4', 'sparse_infill_density': '40%',
          'brim_type': 'auto_brim',
          # PLA on one nozzle, PETG on the other; textured PEI suits both
          'filament_map': ['1', '2'], 'curr_bed_type': 'Textured PEI Plate',
          'enable_support': '1', 'support_type': 'tree(auto)', 'support_on_build_plate_only': '1',
          'support_threshold_angle': '30'}
# Rubbing pairs, each PLA on PETG: worm (PLA, already printed) / worm wheel; wheel / case; carrier hub / wheel;
# planets / ring cup, sun and carrier; sun journal / bearing plate; 27T / cluster; cluster / motor pinion.
PETG = {'worm_wheel', 'planet', 'planet_2', 'planet_3', 'planet_4', 'cluster', 'bearing_plate'}
# part -> center on the bed (mm); H2D plate is 350 x 320. PLA on the left, PETG on the right.
LAYOUT = {'case_left': (95, 160), 'motor_plate': (140, 160), 'ring_cup': (95, 215), 'sun_27t': (135, 215),
          'carrier': (95, 105), 'motor_pinion': (130, 105),
          'bearing_plate': (215, 160), 'worm_wheel': (260, 160), 'cluster': (215, 215),
          'planet': (250, 215), 'planet_2': (268, 215), 'planet_3': (250, 233), 'planet_4': (268, 233)}


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
    for n, (kind, name) in enumerate(PRESETS):
        d = flatten(kind, name)
        d.pop('inherits', None)
        d.update({'from': 'system', 'instantiation': 'true', 'name': name})
        path = os.path.join(tmp, '%s%d.json' % (kind, n))
        json.dump(d, open(path, 'w'), indent=1)
        files.append(path)
    raw = os.path.join(tmp, 'raw.3mf')
    stls = [os.path.join(PRINT, n + '.stl') for n in LAYOUT]
    subprocess.run([CLI, '--debug', '1', '--load-settings', files[0] + ';' + files[1], '--load-filaments', files[2] + ';' + files[3],
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
    cfg = src.read('Metadata/model_settings.config').decode()

    def material(m):
        return m.group(1) + ('2' if m.group(2) in PETG else '1') + '"/>'
    cfg = re.sub(r'(<metadata key="name" value="([^"]+)\.stl"/>\s*<metadata key="extruder" value=")\d+"/>', material, cfg, )
    settings = json.loads(src.read('Metadata/project_settings.config'))
    settings.update(TWEAKS)
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename == '3D/3dmodel.model':
                dst.writestr(info, model)
            elif info.filename == 'Metadata/model_settings.config':
                dst.writestr(info, cfg)
            elif info.filename == 'Metadata/project_settings.config':
                dst.writestr(info, json.dumps(settings, indent=4))
            elif not info.filename.endswith('.png'):         # plate thumbnails are stale after the re-layout
                dst.writestr(info, src.read(info.filename))
    shutil.rmtree(tmp)
    print('wrote', os.path.relpath(OUT, REPO))
    print('PLA :', ', '.join(p for p in order if p not in PETG))
    print('PETG:', ', '.join(p for p in order if p in PETG))


if __name__ == '__main__':
    main()
