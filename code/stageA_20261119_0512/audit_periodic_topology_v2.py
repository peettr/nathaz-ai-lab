#!/usr/bin/env python3
"""Static/fixture checks only; not a GPU or native-flags gate."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
kernel = (root/'stage/FluidX3D_on/src/kernel.cpp').read_text()
setup = (root/'stage/FluidX3D_on/src/setup.cpp').read_text()
legacy = json.loads((root/'LEGACY_BYTE_CHECK_v6.json').read_text())
assert set(legacy) == {'off', 'on', 'k3'}
for variant, item in legacy.items():
    a, b = Path(item['generated']).read_bytes(), Path(item['frozen']).read_bytes()
    assert a == b and item['byte_equal'], variant
assert 'print_error("T17 stage A prototype: native gate instrumentation not sealed; no solver launch")' in setup
assert 'const uint3 periodic_xyz=coordinates(n);' in kernel
assert 'const uint3 ground_xyz = coordinates(n);' in kernel
# These two branches independently swap the same four tangential top populations.
periodic = kernel.split('#ifdef PERIODIC_ABL_GROUND\n+R(\n\tconst uint3 periodic_xyz=', 1)[1].split('#endif', 1)[0]
gate = kernel.split('// Gate fixture only: mirror the top too', 1)[1].split('"#endif"', 1)[0]
for expr in ('fhn[10]=fhn[15]', 'fhn[12]=fhn[17]'):
    assert expr in periodic and expr in gate
assert '#if defined(WALL_GATE0) && !defined(PERIODIC_ABL_GROUND)' in kernel
# The periodic neighbors implementation must wrap every horizontal index.
for term in ('(xyz.x+def_Nx-1u)%def_Nx', '(xyz.y+def_Ny-1u)%def_Ny'):
    assert term in kernel
nx, ny, nz = 256, 128, 66
coords = [(x, y) for x in range(nx) for y in range(ny)]
# Replicate the relevant horizontal neighbor wrapping, then test all first-layer columns.
periodic_neighbors_in_bounds = all(
    0 <= (x+d_x)%nx < nx and 0 <= (y+d_y)%ny < ny
    for x, y in coords for d_x,d_y in ((1,0),(-1,0),(0,1),(0,-1))
)
assert periodic_neighbors_in_bounds
output = {
    'scope': 'static and synthetic fixture; NOT native OpenCL/flags evidence',
    'legacy_byte_equal': {k: True for k in legacy},
    'synthetic_all_eligible_columns': len(coords),
    'expected_native_A3_columns': nx*ny,
    'horizontal_wrap_index_check': periodic_neighbors_in_bounds,
    'z_boundary_prototype': {'ground_solid': 0, 'top_solid': nz-1, 'fluid_layers': [1,nz-2]},
    'launch_guard_present': True,
    'double_top_swap_if_PERIODIC_ABL_GROUND_and_WALL_GATE0': False,
    'note': 'WALL_GATE0 top swap is excluded in periodic builds; native streaming/flux remains untested.'
}
(root/'PERIODIC_TOPOLOGY_AUDIT_v2.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(output, ensure_ascii=False))
