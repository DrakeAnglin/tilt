"""Tilter v0.9 (short-rod sensor sleeve, one motor stage): fresh document, build, checks, STLs to hardware/mechanical/stl/v0.9.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_tilter_v9.py --timeout 1800
"""
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
T9 = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltPartsV9/TiltPartsV9.py'))
STL = os.path.join(REPO, 'hardware/mechanical/stl/v0.9')

old = []
for i in range(app.documents.count):
    d = app.documents.item(i)
    try:
        des = adsk.fusion.Design.cast(d.products.itemByProductType('DesignProductType'))
        if des and any(des.allComponents.item(k).name.startswith(('T9 ', 'T8 ', 'T7 ', 'T6 ', 'T5 ', 'T4 ', 'TP ')) for k in range(des.allComponents.count)):
            old.append(d)
    except Exception:
        pass
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for d in old:
    d.close(False)
result = T9.build(design, STL)
for k in range(design.allComponents.count):
    cc = design.allComponents.item(k)
    for attr in ('isSketchFolderLightBulbOn', 'isConstructionFolderLightBulbOn', 'isOriginFolderLightBulbOn', 'isJointsFolderLightBulbOn'):
        try:
            setattr(cc, attr, False)
        except Exception:
            pass
    for s_ in range(cc.sketches.count):
        cc.sketches.item(s_).isLightBulbOn = False
    for s_ in range(cc.constructionPlanes.count):
        cc.constructionPlanes.item(s_).isLightBulbOn = False
try:
    app.activeViewport.fit()
except Exception:
    pass

import json
print(json.dumps(result, indent=1))
