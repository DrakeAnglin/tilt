root = design.rootComponent
bodies = adsk.core.ObjectCollection.create()
names = {}
for i in range(root.occurrences.count):
    o = root.occurrences.item(i)
    if 'Spline test' in o.component.name:
        continue
    for j in range(o.bRepBodies.count):
        b = o.bRepBodies.item(j)
        if b.name == 'Barrel':
            continue
        bodies.add(b)
inp = design.createInterferenceInput(bodies)
inp.areCoincidentFacesIncluded = False
res = design.analyzeInterference(inp)
out = []
for k in range(res.count):
    r = res.item(k)
    vol = r.interferenceBody.volume * 1000 if r.interferenceBody else 0
    out.append('%s  <->  %s : %.2f mm3' % (r.entityOne.name, r.entityTwo.name, vol))
result = out or ['no interference']
