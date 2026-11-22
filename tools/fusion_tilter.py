"""Tilter: fresh document, build, checks, STLs to hardware/mechanical/stl/tilter.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_tilter.py --timeout 1800

The result's `ok` is False (and `failures` says why) when any check fails.
"""
import json
import os

# REPO is set by fusion.py exec
KIT = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/fusion_kit.py'))
T9 = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/Tilter/Tilter.py'))
STL = os.path.join(REPO, 'hardware/mechanical/stl/tilter')

design = KIT.fresh_document(app, 'tilter', old_prefixes=('T9 ', 'T8 ', 'T7 ', 'T6 ', 'T5 ', 'T4 ', 'TP '), hybrid=True)
result = T9.build(design, STL)
KIT.hide_helpers(design)
try:
    app.activeViewport.fit()
except Exception:
    pass
print(json.dumps(result, indent=1))
