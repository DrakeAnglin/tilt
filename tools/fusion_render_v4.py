"""Fresh TiltPartsV4 build, STL export to hardware/mechanical/stl/v0.4 and renders to docs/renders/v04-*.png.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_render_v4.py --timeout 900
"""
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
mod = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/TiltPartsV4/TiltPartsV4.py'))


def is_generated(doc):
    try:
        d = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
        return d is not None and any(d.allComponents.item(i).name.startswith(('TP ', 'T4 '))
                                     for i in range(d.allComponents.count))
    except Exception:
        return False


old_docs = [app.documents.item(i) for i in range(app.documents.count) if is_generated(app.documents.item(i))]
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for doc in old_docs:
    doc.close(False)
report = mod.build(design, os.path.join(REPO, 'hardware/mechanical/stl/v0.4'))
vp = app.activeViewport
root = design.rootComponent
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
for i in range(root.occurrences.count):
    c = root.occurrences.item(i).component
    for j in range(c.bRepBodies.count):
        b = c.bRepBodies.item(j)
        b.opacity = 0.25 if b.name.startswith('Rail') else 1.0


def vis(show=None, hide=()):
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        n = o.component.name
        o.isLightBulbOn = (show is None or any(s in n for s in show)) and not any(h in n for h in hide)


def rail(on):
    for i in range(root.occurrences.count):
        c = root.occurrences.item(i).component
        for j in range(c.bRepBodies.count):
            b = c.bRepBodies.item(j)
            if b.name.startswith('Rail'):
                b.isLightBulbOn = on


def shot(name, orient, ortho=True):
    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.OrthographicCameraType if ortho else adsk.core.CameraTypes.PerspectiveCameraType
    cam.viewOrientation = getattr(adsk.core.ViewOrientations, orient)
    cam.isFitView = True
    vp.camera = cam
    vp.fit()
    p = os.path.join(out, name)
    vp.saveAsImageFile(p, 1600, 1000)
    return p


DRIVE = ('Worm', 'Motor pinion', 'REF')       # 'Worm' also shows the worm wheel
res = []
vis(hide=('Case left',)); rail(True); res.append(shot('v04-assembly-end.png', 'RightViewOrientation'))
vis(hide=('Case left',)); rail(False); res.append(shot('v04-assembly-iso.png', 'IsoTopRightViewOrientation', False))
vis(); rail(False); res.append(shot('v04-closed-iso.png', 'IsoTopLeftViewOrientation', False))
vis(show=DRIVE); rail(False); res.append(shot('v04-drivetrain-iso.png', 'IsoTopLeftViewOrientation', False))
res.append(shot('v04-drivetrain-end.png', 'RightViewOrientation'))
vis(show=('Case right',)); res.append(shot('v04-case-right.png', 'IsoTopLeftViewOrientation', False))
vis(show=('Case left',)); res.append(shot('v04-case-left.png', 'IsoTopRightViewOrientation', False))
vis(show=('Worm',), hide=('wheel',)); res.append(shot('v04-worm.png', 'IsoTopRightViewOrientation', False))
vis(show=('Worm wheel',)); res.append(shot('v04-wheel.png', 'IsoTopRightViewOrientation', False))
vis(); rail(True)
result = {'build': report.split('\n'), 'renders': res}
