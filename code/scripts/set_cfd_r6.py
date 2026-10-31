# -*- coding: utf-8 -*-
# L26.5 run6 wrapper (NOT package): switch mesh physics to CFD / solver Fluent before running package 03.
LOG = r"__RUN__/wrapper_cfd.txt"
f = open(LOG, "w")
m = ExtAPI.DataModel.Project.Model.Mesh
for setter in [lambda: setattr(m, "PhysicsPreference", MeshPhysicsPreferenceType.CFD),
               lambda: setattr(m, "SolverPreference", MeshSolverPreferenceType.Fluent)]:
    try: setter()
    except Exception as e: f.write("set ERR %r\n" % (e,))
for p in ["PhysicsPreference", "SolverPreference", "ElementOrder"]:
    try: f.write("%s = %s\n" % (p, getattr(m, p)))
    except Exception as e: f.write("%s ERR %r\n" % (p, e))
f.close()
