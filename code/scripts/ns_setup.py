# -*- coding: utf-8 -*-
# L26.5 wrapper payload (NOT part of the package): create NS_FLUID (body) and NS_WALL (prism faces),
# which the package README step 3/7 says the user creates by hand in Meshing.
import os
LOG = r"__RUN__/wrapper_ns.txt"
def w(s):
    f = open(LOG, "a"); f.write(str(s) + "\n"); f.close()
try:
    model = ExtAPI.DataModel.Project.Model
    bodies = []
    for a in ExtAPI.DataModel.GeoData.Assemblies:
        for p in a.Parts:
            for b in p.Bodies:
                bodies.append(b)
    w("bodies=%d" % len(bodies))
    body = bodies[0]
    faces = list(body.Faces)
    cs = [list(f.Centroid) for f in faces]
    lo = [min(c[i] for c in cs) for i in range(3)]
    hi = [max(c[i] for c in cs) for i in range(3)]
    tol = 1e-6 * max(hi[i] - lo[i] for i in range(3))
    wall = [f for f, c in zip(faces, cs)
            if all(abs(c[i] - lo[i]) > tol and abs(c[i] - hi[i]) > tol for i in range(3))]
    w("faces=%d wall=%d bbox lo=%s hi=%s" % (len(faces), len(wall), lo, hi))
    def mk(name, ids):
        sel = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
        sel.Ids = ids
        ns = model.AddNamedSelection()
        ns.Location = sel
        ns.Name = name
        w("NS %s ids=%s" % (name, ids))
    mk("NS_FLUID", [body.Id])
    mk("NS_WALL", [f.Id for f in wall])
    mk("NS_REFINE", [f.Id for f in wall])
except Exception as e:
    w("NS ERROR: %r" % (e,))
    raise
