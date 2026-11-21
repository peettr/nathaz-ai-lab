# -*- coding: utf-8 -*-
# L26.5 independent readback (NOT part of the package): element/node counts + quality to a text file.
LOG = r"__RUN__/__TAG___readback.txt"
f = open(LOG, "w")
try:
    m = ExtAPI.DataModel.Project.Model.Mesh
    f.write("Nodes=%s Elements=%s\n" % (m.Nodes, m.Elements))
    for metric in ["Skewness", "OrthogonalQuality"]:
        try:
            m.MeshMetric = getattr(MeshMetricType, metric)
            f.write("%s min=%s max=%s avg=%s\n" % (metric, m.Minimum, m.Maximum, m.Average))
        except Exception as e:
            f.write("%s ERROR %r\n" % (metric, e))
    for c in m.Children:
        f.write("control %s %s\n" % (c.Name, type(c).__name__))
except Exception as e:
    f.write("READBACK ERROR %r\n" % (e,))
f.close()
