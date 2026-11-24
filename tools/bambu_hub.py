"""Build the hub box's two-color Bambu Studio project: the box (filament 1) with the mark, the three slats and "tilt",
as a second part of the same object (filament 2), and the pause already set.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_hub.py --timeout 900   # first: box + inlay
  python3 tools/bambu_hub.py        # writes hardware/mechanical/stl/hub/hub_box_multicolor.3mf

H2D 0.4 nozzle, 0.20 mm Standard, no supports. For one color, print hub_box.stl by itself (the mark is a groove).
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bambu import CLI, flatten  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('hub', os.path.join(REPO, 'hardware/mechanical/fusion/Hub/Hub.py'))
HUB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(HUB)
H = HUB.H
BOX = os.path.join(REPO, 'hardware/mechanical/stl/hub/hub_box.stl')
MARK = os.path.join(tempfile.gettempdir(), 'tilt_hub_box_mark.stl')      # written by tools/fusion_hub.py
OUT = os.path.join(REPO, 'hardware/mechanical/stl/hub/hub_box_multicolor.3mf')
PRESETS = (('machine', 'Bambu Lab H2D 0.4 nozzle'), ('process', '0.20mm Standard @BBL H2D'),
           ('filament', 'Bambu PLA Basic @BBL H2D'), ('filament', 'Bambu PLA Basic @BBL H2D'))
# filament 1 = the box (white), filament 2 = the mark (the app icon's teal); one on each nozzle
TWEAKS = {'filament_colour': ['#FFFFFF', '#1F6F8B'], 'filament_map': ['1', '2'], 'enable_support': '0',
          'curr_bed_type': 'Textured PEI Plate'}
BED = (175.0, 160.0)                # middle of the H2D's bed


def pause_xml():
    """A pause after the last layer of the walls, before the roof (Hub.py's pause height). Type 1 = pause in Bambu
    Studio's list (0 color change, 2 tool change)."""
    return ('<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_layer>\n<plate>\n<plate_info id="1"/>\n'
            '<layer top_z="%.2f" type="1" extruder="1" color="" extra="" gcode="M400 U1"/>\n'
            '<mode value="MultiAsSingle"/>\n</plate>\n</custom_gcodes_per_layer>\n' % H['zp'])


def main():
    if not os.path.exists(MARK) or os.path.getmtime(MARK) < os.path.getmtime(BOX) - 120:
        sys.exit('the inlay is missing or older than hub_box.stl: run tools/fusion_hub.py first')
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
    mark = os.path.join(tmp, 'mark.stl')
    shutil.copy(MARK, mark)
    subprocess.run([CLI, '--debug', '1', '--load-settings', files[0] + ';' + files[1], '--load-filaments', files[2] + ';' + files[3],
                    '--arrange', '1', '--orient', '0', '--export-3mf', raw, BOX, mark],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    src = zipfile.ZipFile(raw)
    cfg = src.read('Metadata/model_settings.config').decode()
    model = src.read('3D/3dmodel.model').decode()
    # the CLI loads two objects; each keeps its file's own coordinates through its component's transform. Make the mark
    # a second part (component) of the box's object, on filament 2, and drop the mark's own object
    objs = re.findall(r'  <object id="(\d+)">.*?  </object>\n', cfg, re.S)
    blocks = {m.group(1): m.group(0) for m in re.finditer(r'  <object id="(\d+)">.*?  </object>\n', cfg, re.S)}
    box_id = next(i for i in objs if 'value="hub_box.stl"' in blocks[i])
    mark_id = next(i for i in objs if i != box_id)
    part = re.search(r'    <part .*?    </part>\n', blocks[mark_id], re.S).group(0)
    part = part.replace('value="mark.stl"', 'value="tilt mark"', 1)
    part = part.replace('<metadata key="matrix"', '<metadata key="extruder" value="2"/>\n      <metadata key="matrix"', 1)
    cfg = cfg.replace(blocks[mark_id], '')
    cfg = cfg.replace(blocks[box_id], blocks[box_id].replace('  </object>\n', part + '  </object>\n')
                      .replace('value="hub_box.stl"', 'value="Tilt Hub box"', 1))
    cfg = re.sub(r'    <model_instance>\s*<metadata key="object_id" value="%s"/>.*?    </model_instance>\n' % mark_id, '', cfg, flags=re.S)
    comp = re.search(r'<object id="%s"[^>]*>\s*<components>\s*(<component [^>]*/>)' % mark_id, model, re.S).group(1)
    model = re.sub(r'  <object id="%s".*?  </object>\n' % mark_id, '', model, flags=re.S)
    model = re.sub(r'(<object id="%s"[^>]*>\s*<components>\s*<component [^>]*/>\n)' % box_id, r'\1    ' + comp.replace('\\', '\\\\') + '\n', model, flags=re.S)
    model = re.sub(r'  <item objectid="%s"[^>]*/>\n' % mark_id, '', model)
    # the box square in the middle of the bed (the object's origin is the box file's origin)
    model = re.sub(r'(<item objectid="%s"[^>]*?)transform="[^"]+"' % box_id,
                   r'\1transform="1 0 0 0 1 0 0 0 1 %g %g 0"' % (BED[0] - H['L'] / 2, BED[1]), model)
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
            elif not info.filename.endswith('.png'):         # the thumbnails show two loose objects
                dst.writestr(info, src.read(info.filename))
        dst.writestr('Metadata/custom_gcode_per_layer.xml', pause_xml())
    shutil.rmtree(tmp)
    print('wrote', os.path.relpath(OUT, REPO), '- pause at %.1f mm (after layer %d)' % (H['zp'], H['pause_layer']))


if __name__ == '__main__':
    main()
