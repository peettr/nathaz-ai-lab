# -*- coding: utf-8 -*-
# L26.5 run4 probe (wrapper, NOT package): where is Orthogonal Quality exposed; what mesh settings were applied.
LOG = r"__RUN__/probe_r4.txt"
f = open(LOG, "w")
def w(s):
    f.write(str(s) + "\n"); f.flush()
m = ExtAPI.DataModel.Project.Model.Mesh
for p in ["ElementSize", "ElementOrder", "PhysicsPreference", "SolverPreference", "UseAdaptiveSizing", "Resolution",
          "SpanAngleCenter", "Nodes", "Elements", "MeshMetric"]:
    try: w("Mesh.%s = %s" % (p, getattr(m, p)))
    except Exception as e: w("Mesh.%s ERR %r" % (p, e))
try:
    for a in ExtAPI.DataModel.GeoData.Assemblies:
        for pt in a.Parts:
            for b in pt.Bodies:
                w("body %s volume=%s units=%s" % (b.Id, b.Volume, ExtAPI.DataModel.GeoData.Unit if hasattr(ExtAPI.DataModel.GeoData, "Unit") else "?"))
except Exception as e: w("geo ERR %r" % (e,))
try:
    w("MeshMetricType members: " + ",".join([n for n in dir(MeshMetricType) if not n.startswith("_")]))
except Exception as e: w("dir ERR %r" % (e,))
found = []
try:
    import System
    for asm in System.AppDomain.CurrentDomain.GetAssemblies():
        try:
            for t in asm.GetTypes():
                if t.IsEnum and "OrthogonalQuality" in list(System.Enum.GetNames(t)):
                    found.append(t.FullName)
        except Exception:
            pass
except Exception as e: w("reflect ERR %r" % (e,))
w("enums with OrthogonalQuality: %s" % found)
for name in found:
    try:
        import System
        t = None
        for asm in System.AppDomain.CurrentDomain.GetAssemblies():
            t = asm.GetType(name)
            if t: break
        val = System.Enum.Parse(t, "OrthogonalQuality")
        try:
            m.MeshMetric = val
            w("via %s: min=%s max=%s avg=%s" % (name, m.Minimum, m.Maximum, m.Average))
        except Exception as e:
            w("via %s set ERR %r" % (name, e))
    except Exception as e:
        w("parse %s ERR %r" % (name, e))
# fallback: export Fluent mesh for an independent quality check
for label, call in [("Mesh.ExportMesh", lambda: m.ExportMesh(r"__RUN__/l265_full.msh")),
                    ("Model.Mesh.Export", lambda: m.Export(r"__RUN__/l265_full.msh"))]:
    try:
        call(); w("%s OK" % label); break
    except Exception as e:
        w("%s ERR %r" % (label, e))
f.close()
