#!/usr/bin/env python3
"""Generate bounded reduced-domain v10 RANS case from WE-UQ templates and Chicago STL.
Run on CRC compute allocation, never on 工作站. No BRAILS/network fetches.
"""
import ast
import math
import pathlib
import re
import sys
import textwrap

source, case = map(pathlib.Path, sys.argv[1:3])
if case.exists():
    raise SystemExit(f"refusing existing case: {case}")
text = source.read_text(encoding="utf-8-sig")
tree = ast.parse(text)
wanted_functions = {"make_bounds", "write_bmd", "body_U_meanABL", "body_k", "body_omega", "body_nut"}
wanted_constants = {"TEMPLATE", "TP_RANSkwSST", "P_BODY", "SIDE_MAP", "TP_RANSC", "TP_PROFILE", "TP_PLANE", "TP_transportProperty", "TP_surfFeat", "TP_fvSch_RANS", "TP_fvSol_RANS"}
nodes = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
        nodes.append(node)
    elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in wanted_constants for t in node.targets):
        nodes.append(node)
namespace = {"textwrap": textwrap, "Path": pathlib.Path, "math": math, "re": re}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
assert all(n in namespace for n in wanted_constants | wanted_functions)
# The ASCII STL is the actual Step 1a output; no geometry is regenerated or fetched.
tri = case / "constant" / "triSurface"
tri.mkdir(parents=True)
mins = [float("inf")] * 3
maxs = [float("-inf")] * 3
for name in ("ROI", "Surrounding"):
    input_stl = source.parent / f"{name}.stl"
    if not input_stl.is_file():
        raise SystemExit(f"missing {input_stl}")
    (tri / f"{name}.stl").symlink_to(input_stl.resolve())
    with input_stl.open() as handle:
        for line in handle:
            if not line.lstrip().startswith("vertex "):
                continue
            coords = [float(v) for v in line.split()[1:4]]
            for i, v in enumerate(coords):
                mins[i] = min(mins[i], v)
                maxs[i] = max(maxs[i], v)
if not all(math.isfinite(v) for v in mins + maxs):
    raise SystemExit("empty/nonfinite STL")
hmax = maxs[2]
if hmax <= 0:
    raise SystemExit("no positive height")
system = case / "system"
system.mkdir()
zero = case / "0"
zero.mkdir()
# Composite authorized change: 3H inlet/outlet/sides and 4H total height
# (Abu-Zidan 2021, single-building RANS; city applicability is unverified).
# 32 m background spacing is a resource-bound hypothesis, not a literature value.
x0, x1, y0, y1 = namespace["make_bounds"](mins[0], maxs[0], mins[1], maxs[1], hmax, 3., 3., 3., "W")
z1 = 4. * hmax
nx, ny, nz = (math.ceil((b-a)/32.) for a,b in ((x0,x1),(y0,y1),(0.,z1)))
base_cells = nx * ny * nz
if base_cells > 3000000:
    raise SystemExit(f"background mesh {base_cells} cells exceeds quick-trial bound; do not change mesh silently")
namespace["write_bmd"](x0,x1,y0,y1,0.,z1,nx,ny,nz,"slip",system/"blockMeshDict")
# Original script's auto-levels are 5/4 without boxes; mandated one-level reduction = 4/3.
snappy = namespace["TEMPLATE"].format(
    roi_stl="ROI", sur_stl="Surrounding", geometry_entries="", refinement_entries="",
    ncellblvl=5, roi_level=4, sur_level=3, roi_feat_level=4, sur_feat_level=3)
# Source TEMPLATE line 327 hardcodes insidePoint near the origin, outside UTM-domain STL.
# Choose the centre of the inlet-side base cell, away from building extents.
interior = (x0 + (x1-x0)/(2*nx), y0 + (y1-y0)/(2*ny), z1/(2*nz))
snappy = snappy.replace("insidePoint (0.01 0.01 0.01);",
    f"insidePoint ({interior[0]:.6f} {interior[1]:.6f} {interior[2]:.6f});")
(system/"snappyHexMeshDict").write_text(snappy)
(system/"surfaceFeaturesDict").write_text(namespace["TP_surfFeat"])
(case/"constant"/"transportProperties").write_text(namespace["TP_transportProperty"].format(nu=1.5e-5))
(case/"constant"/"turbulenceProperties").write_text(namespace["TP_RANSkwSST"])
side = "slip"
(zero/"U").write_text(namespace["body_U_meanABL"](side,10.,10.,0.1))
(zero/"k").write_text(namespace["body_k"](side,10.,10.,0.1))
(zero/"omega").write_text(namespace["body_omega"](side,10.,10.,0.1))
(zero/"nut").write_text(namespace["body_nut"](side,"smooth",0.1,10.,10.,"smooth","smooth"))
(zero/"p").write_text(namespace["P_BODY"] % (side,side))
(system/"controlDict").write_text(namespace["TP_RANSC"].format(end_T=50,deltaT_sim=1,deltaT_write=10)
 + f'''\nfunctions\n{{\n    #include "Profile1"\n    #include "Plane1"\n}}\n''')
probe = (mins[0] + maxs[0])/2, (mins[1] + maxs[1])/2
# Keep the probe upstream of the first building to avoid sampling inside a solid.
probe = (mins[0]-hmax, probe[1])
points = '\n'.join(f'({probe[0]:.6f} {probe[1]:.6f} {z:.6f})' for z in (10., 30., 60., 100.))
(system/"Profile1").write_text(namespace["TP_PROFILE"].format(
    ProfileName="Profile1", N_profile=10, t_start=0, fields="U", points=points))
(system/"Plane1").write_text(namespace["TP_PLANE"].format(
    PlaneName="Plane1", N_plane=10, t_start=0, t_end=50, fields="U",
    plane_point=f"({probe[0]:.6f} {probe[1]:.6f} 30)", plane_normal="(0 1 0)"))
(system/"fvSolution").write_text(namespace["TP_fvSol_RANS"])
(system/"fvSchemes").write_text(namespace["TP_fvSch_RANS"])
(system/"decomposeParDict").write_text('FoamFile { version 2.0; format ascii; class dictionary; object decomposeParDict; }\nnumberOfSubdomains 48; method scotch;\n')
print(f"case={case} extent={(x0,x1,y0,y1,0,z1)} background_cells={base_cells} hmax={hmax} iterations=50 model=kOmegaSST")
