# -*- coding: utf-8 -*-
"""Ansys Meshing editor Python command payload.

Execute with Workbench Mesh.SendCommand(Language='Python', Command=<file text>)
or inside a compatible Mechanical/Meshing Python Scripting console.
Not for ordinary CPython: Ansys Model/ExtAPI objects are required.

Safe defaults: DRY_RUN=True, no mesh controls are created.
The default mesh parameters below are DEMONSTRATIONS, not engineering advice.
"""

# --------- EDIT THESE VALUES AFTER BACKING UP THE PROJECT ---------
DRY_RUN = False
GLOBAL_SIZE_MM = 3.5
ENABLE_LOCAL_SIZING = False
LOCAL_SELECTION = "NS_REFINE"      # pre-existing FACE/BODY named selection
LOCAL_SIZE_MM = 1.0
ENABLE_INFLATION = False
FLUID_BODY_SELECTION = "NS_FLUID"   # pre-existing FLUID BODY named selection
WALL_FACE_SELECTION = "NS_WALL"    # pre-existing WALL FACES named selection
FIRST_LAYER_MM = 0.025            # demo only; must be checked from y+
INFLATION_LAYERS = 10
INFLATION_GROWTH = 1.2
GENERATE_MESH = True
REPORT_QUALITY = True
# --------------------------------------------------------------


def _log(message):
    print("[CodexMesh] " + str(message))


def _named_selection(name):
    matches = [obj for obj in DataModel.GetObjectsByName(name)
               if str(getattr(obj, "Name", "")) == name]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one Named Selection %r; found %s. "
                           "Create/rename it in Meshing first." % (name, len(matches)))
    obj = matches[0]
    if not hasattr(obj, "Location") and not hasattr(obj, "GenerationCriteria"):
        raise RuntimeError("Object %r is not a recognizable Named Selection." % name)
    return obj


def _get_or_create_control(name, creator, expected_attribute):
    found = [o for o in DataModel.GetObjectsByName(name)
             if str(getattr(o, "Name", "")) == name]
    if len(found) > 1:
        raise RuntimeError("Duplicate mesh controls named %s; resolve manually first" % name)
    if found:
        if not hasattr(found[0], expected_attribute):
            raise RuntimeError("Object named %s is not the expected control type" % name)
        return found[0], False
    return creator(), True


def _quantity(mm):
    return Quantity("%g [mm]" % mm)


if GLOBAL_SIZE_MM <= 0:
    raise ValueError("GLOBAL_SIZE_MM must be positive")
if ENABLE_LOCAL_SIZING and (LOCAL_SIZE_MM <= 0):
    raise ValueError("LOCAL_SIZE_MM must be positive")
if ENABLE_INFLATION and (FIRST_LAYER_MM <= 0 or INFLATION_LAYERS < 1 or INFLATION_GROWTH <= 1):
    raise ValueError("Invalid inflation parameters")
if "ExtAPI" not in globals() or "DataModel" not in globals():
    raise RuntimeError("This code must run inside the ANSYS Meshing/Mechanical scripting context")
try:
    mesh = ExtAPI.DataModel.Project.Model.Mesh
except Exception as err:
    raise RuntimeError("Model.Mesh API unavailable in this editor/version: %s" % err)
if not hasattr(mesh, "GenerateMesh"):
    raise RuntimeError("Mesh.GenerateMesh is not exposed in this editor/version")

local_ns = _named_selection(LOCAL_SELECTION) if ENABLE_LOCAL_SIZING else None
fluid_ns = _named_selection(FLUID_BODY_SELECTION) if ENABLE_INFLATION else None
wall_ns = _named_selection(WALL_FACE_SELECTION) if ENABLE_INFLATION else None

_log("Mesh object found; plan validated.")
_log("Global size: %s mm; local sizing: %s; inflation: %s" %
     (GLOBAL_SIZE_MM, ENABLE_LOCAL_SIZING, ENABLE_INFLATION))
_log("DRY_RUN=%s" % DRY_RUN)

if not DRY_RUN:
    # Both ElementSize and AddSizing are documented Mechanical mesh APIs.
    mesh.ElementSize = _quantity(GLOBAL_SIZE_MM)
    if ENABLE_LOCAL_SIZING:
        sizing, created = _get_or_create_control(
            "CODEX_LOCAL_SIZING", mesh.AddSizing, "ElementSize")
        if created:
            sizing.Name = "CODEX_LOCAL_SIZING"
        sizing.ScopingMethod = GeometryDefineByType.Component
        sizing.NamedSelection = local_ns
        sizing.ElementSize = _quantity(LOCAL_SIZE_MM)
        _log("Created local sizing on %s" % LOCAL_SELECTION)

    if ENABLE_INFLATION:
        inflation, created = _get_or_create_control(
            "CODEX_WALL_INFLATION", mesh.AddInflation, "NumberOfLayers")
        if created:
            inflation.Name = "CODEX_WALL_INFLATION"
        inflation.ScopingMethod = GeometryDefineByType.Component
        inflation.NamedSelection = fluid_ns
        inflation.BoundaryNamedSelection = wall_ns
        inflation.NumberOfLayers = INFLATION_LAYERS
        inflation.GrowthRate = INFLATION_GROWTH
        inflation.FirstLayerHeight = _quantity(FIRST_LAYER_MM)
        _log("Inflation set. Current option=%s. VERIFY first-layer option + values in GUI" %
             getattr(inflation, "InflationOption", "unknown"))

    if GENERATE_MESH:
        _log("Generating mesh...")
        mesh.GenerateMesh()
        _log("GenerateMesh command returned. Inspect geometry and statistics.")

    if GENERATE_MESH and REPORT_QUALITY:
        for label, metric in [("Skewness", "Skewness"),
                              ("OrthogonalQuality", "OrthogonalQuality")]:
            try:
                mesh.MeshMetric = getattr(MeshMetricType, metric)
                _log("%s: min=%s max=%s avg=%s" %
                     (label, mesh.Minimum, mesh.Maximum, mesh.Average))
            except Exception as err:
                _log("%s metric unavailable, inspect Quality in UI: %s" % (label, err))
        try:
            _log("Nodes=%s; Elements=%s" % (mesh.Nodes, mesh.Elements))
        except Exception:
            _log("Check node/element counts in Mesh > Statistics")
else:
    _log("Safety preview complete. Set DRY_RUN=False to modify the project.")
