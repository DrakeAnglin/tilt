"""Fresh build (+ STL export) and clean renders, no interference display. Run via FusionBridge."""

import math
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
try:
    OVERRIDES
except NameError:
    OVERRIDES = {}
try:
    EXPORT
except NameError:
    EXPORT = False
try:
    SWEEP_STEPS
except NameError:
    SWEEP_STEPS = 16

mod = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltParts/TiltParts.py'))
mod.P.update(OVERRIDES)


def is_generated(doc):
    try:
        d = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
        return d is not None and any(d.allComponents.item(i).name.startswith(mod.PREFIX)
                                     for i in range(d.allComponents.count))
    except Exception:
        return False


# fresh document every run (rebuilding in one design slows Fusion down), closing only our own generated docs
old_docs = [app.documents.item(i) for i in range(app.documents.count) if is_generated(app.documents.item(i))]
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for doc in old_docs:
    doc.close(False)
report = mod.build(design, os.path.join(REPO, 'hardware/mechanical/stl'))
import os
vp = app.activeViewport; root = design.rootComponent
out = os.path.join(REPO, 'docs/renders')
ui.activeSelections.clear()
try:
    design.activateRootComponent()
except Exception:
    pass
for k in range(design.allComponents.count):
    c = design.allComponents.item(k)
    try:
        c.isSketchFolderLightBulbOn = False
        c.isConstructionFolderLightBulbOn = False
    except Exception:
        pass
try:
    vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
except Exception:
    pass
try:
    for k in range(root.customGraphicsGroups.count - 1, -1, -1):
        root.customGraphicsGroups.item(k).deleteMe()
except Exception:
    pass
for i in range(root.occurrences.count):
    c = root.occurrences.item(i).component
    for j in range(c.bRepBodies.count):
        b = c.bRepBodies.item(j)
        b.opacity = 0.25 if b.name.startswith('Rail') else 1.0
    try:
        root.occurrences.item(i).appearance = None
    except Exception:
        pass
def vis(show=None, hide=()):
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i); n = o.component.name
        o.isLightBulbOn = (show is None or any(s in n for s in show)) and not any(h in n for h in hide)
def rail(on):
    for i in range(root.occurrences.count):
        c = root.occurrences.item(i).component
        for j in range(c.bRepBodies.count):
            b = c.bRepBodies.item(j)
            if b.name.startswith('Rail'): b.isLightBulbOn = on
def shot(name, orient, ortho=True):
    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.OrthographicCameraType if ortho else adsk.core.CameraTypes.PerspectiveCameraType
    cam.viewOrientation = getattr(adsk.core.ViewOrientations, orient); cam.isFitView = True; vp.camera = cam; vp.fit()
    p = os.path.join(out, name); vp.saveAsImageFile(p, 1600, 1000); return p
res = []
vis(hide=('Case left',)); rail(True); res.append(shot('v03-assembly-end.png', 'RightViewOrientation'))
res.append(shot('v03-assembly-iso.png', 'IsoTopRightViewOrientation', False))
vis(); rail(False); res.append(shot('v03-closed-iso.png', 'IsoTopLeftViewOrientation', False))
vis(show=('Adapter', 'Motor pinion', 'REF')); rail(False); res.append(shot('v03-drivetrain-iso.png', 'IsoTopRightViewOrientation', False))
vis(show=('Case right',)); res.append(shot('v03-case-right.png', 'IsoTopLeftViewOrientation', False))
vis(show=('Case left', 'REF', 'Sensor gear')); rail(False); res.append(shot('v03-sensor.png', 'IsoTopLeftViewOrientation', False))
vis(show=('Sensor gear', 'Case right', 'REF')); rail(False); res.append(shot('v03-sensor-open.png', 'IsoTopLeftViewOrientation', False))
vis(show=('Adapter',)); rail(False); res.append(shot('v03-adapter.png', 'IsoTopRightViewOrientation', False))
res.append(shot('v03-adapter-front.png', 'FrontViewOrientation'))
vis(); rail(True)
result = {'build': report.split('\n'), 'renders': res}
