# -*- coding: utf-8 -*-
"""Read-only API preflight inside Ansys Meshing/Mechanical editor.
Run via SendCommand(Language='Python') or inside the scripting console.
"""
print("[CodexMesh] Inspecting scripting environment, NO changes will be made")
try:
    m = ExtAPI.DataModel.Project.Model.Mesh
    for name in ["GenerateMesh", "AddSizing", "AddInflation", "ElementSize", "MeshMetric"]:
        print("[CodexMesh] Mesh.%s: %s" % (name, hasattr(m, name)))
    try:
        for ns in ExtAPI.DataModel.Project.Model.NamedSelections.Children:
            print("[CodexMesh] NamedSelection: %s" % ns.Name)
    except Exception as err:
        print("[CodexMesh] Cannot enumerate named selections: %s" % err)
except Exception as err:
    print("[CodexMesh] API not found: %s" % err)
    raise
