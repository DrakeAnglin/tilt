"""Fresh ControllerV1 build in its own document + renders to docs/renders/ctrl-v1-*.png.

  python3 hardware/mechanical/fusion/fusion.py exec tools/fusion_controller_v1.py --timeout 600
"""
import os

REPO = os.path.expanduser('~/Documents/automated-blinds/blinds')
mod = load_script(os.path.join(REPO, 'hardware/mechanical/fusion/ControllerV1/ControllerV1.py'))


def is_generated(doc):
    try:
        d = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
        return d is not None and any(d.allComponents.item(i).name.startswith(mod.PREFIX)
                                     for i in range(d.allComponents.count))
    except Exception:
        return False


old_docs = [app.documents.item(i) for i in range(app.documents.count) if is_generated(app.documents.item(i))]
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designType = adsk.fusion.DesignTypes.DirectDesignType
for doc in old_docs:
    doc.close(False)
report = mod.build(design)

vp = app.activeViewport
root = design.rootComponent
out = os.path.join(REPO, 'docs/renders')
try:
    vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
except Exception:
    pass


def vis(hide=()):
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        o.isLightBulbOn = not any(h in o.component.name for h in hide)


def rail(mode):
    """mode: 'hide', 'ghost' or 'show'."""
    for i in range(root.occurrences.count):
        c = root.occurrences.item(i).component
        if c.name.endswith('Rail'):
            for j in range(c.bRepBodies.count):
                b = c.bRepBodies.item(j)
                b.isLightBulbOn = mode != 'hide'
                b.opacity = 0.3 if mode == 'ghost' and not b.name.startswith('Tilt') else 1.0


def shot(name, orient, ortho=False):
    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.OrthographicCameraType if ortho else adsk.core.CameraTypes.PerspectiveCameraType
    cam.viewOrientation = getattr(adsk.core.ViewOrientations, orient)
    cam.isFitView = True
    vp.camera = cam
    vp.fit()
    p = os.path.join(out, name)
    vp.saveAsImageFile(p, 1600, 1000)
    return p


res = []
vis(); rail('ghost'); res.append(shot('ctrl-v1-in-rail.png', 'IsoTopRightViewOrientation'))
vis(); rail('show'); res.append(shot('ctrl-v1-end.png', 'RightViewOrientation', True))
vis(hide=('Case lid',)); rail('hide'); res.append(shot('ctrl-v1-open.png', 'IsoTopRightViewOrientation'))
res.append(shot('ctrl-v1-open-left.png', 'IsoTopLeftViewOrientation'))
vis(hide=('Case lid', 'Case tray', 'Plugs')); rail('hide'); res.append(shot('ctrl-v1-boards-top.png', 'TopViewOrientation', True))
res.append(shot('ctrl-v1-boards-side.png', 'FrontViewOrientation', True))
vis(); rail('hide'); res.append(shot('ctrl-v1-closed.png', 'IsoTopLeftViewOrientation'))
vis(); rail('ghost')
report['renders'] = res
result = report
