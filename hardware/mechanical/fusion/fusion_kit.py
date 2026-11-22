"""Small Fusion helpers shared by the build drivers in tools/ (load with load_script)."""

import adsk.core
import adsk.fusion

ATTR_GROUP = 'tilt'          # design attribute that marks a document made by one of our drivers
ATTR_NAME = 'doc'


def _tag_of(doc):
    des = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    if des is None:
        return None, None
    a = des.attributes.itemByName(ATTR_GROUP, ATTR_NAME)
    return des, (a.value if a else None)


def fresh_document(app, tag, old_prefixes=(), hybrid=False):
    """Open a new direct-design document tagged `tag` and close every older one with the same tag. Documents from
    before the tag (no attribute) are matched by a component name starting with one of old_prefixes.
    hybrid=True also sets the hybrid design intent (part and assembly in one document)."""
    old = []
    for i in range(app.documents.count):
        d = app.documents.item(i)
        try:
            des, t = _tag_of(d)
            if des is None:
                continue
            if t == tag or (t is None and old_prefixes and any(
                    des.allComponents.item(k).name.startswith(tuple(old_prefixes)) for k in range(des.allComponents.count))):
                old.append(d)
        except Exception:
            pass
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    if hybrid:
        design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    design.attributes.add(ATTR_GROUP, ATTR_NAME, tag)
    for d in old:
        d.close(False)
    return design


def hide_helpers(design):
    """Turn off sketches, construction planes and the origin / joint folders in every component."""
    for k in range(design.allComponents.count):
        cc = design.allComponents.item(k)
        for attr in ('isSketchFolderLightBulbOn', 'isConstructionFolderLightBulbOn', 'isOriginFolderLightBulbOn',
                     'isJointsFolderLightBulbOn'):
            try:
                setattr(cc, attr, False)
            except Exception:
                pass
        for s in range(cc.sketches.count):
            cc.sketches.item(s).isLightBulbOn = False
        for s in range(cc.constructionPlanes.count):
            cc.constructionPlanes.item(s).isLightBulbOn = False
