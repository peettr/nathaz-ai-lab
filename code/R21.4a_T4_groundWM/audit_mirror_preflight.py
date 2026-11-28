#!/usr/bin/env python3
"""Preflight for the inherited T3d experimental mirror; no GPU work."""
from pathlib import Path
import json

root = Path(__file__).resolve().parent
src = (root / 'FluidX3D/src/kernel.cpp').read_text()
assert 'const float swapx=fhn[9]; fhn[9]=fhn[16]; fhn[16]=swapx;' in src
assert 'const float swapy=fhn[11]; fhn[11]=fhn[18]; fhn[18]=swapy;' in src
# D3Q19 kernel.cpp c(): 15=(+x,0,-z), 9=(+x,0,+z),
# 16=(-x,0,+z). A particle leaving (+x,-z) from x=s
# must arrive (+x,+z) at x=s+1 after specular reflection.
# The inherited per-cell fhn[9]<->fhn[16] swap instead takes
# the same-cell bounce-back, depositing it at x=s.
source_x = 3
expected = {'incoming_direction': 9, 'arrival_x': source_x + 1}
inherited = {'incoming_direction': 9, 'arrival_x': source_x}
assert expected != inherited
# Conversely a link that hits a building is intentionally NOT covered here;
# this check is only the flat horizontal floor with nonuniform x distribution.
result = {'source_outgoing_direction': 15, 'source_x': source_x,
          'expected_specular': expected, 'inherited_local_swap': inherited,
          'spatial_link_test': 'FAIL', 'gpu_sessions_created': 0}
print(json.dumps(result, indent=2, ensure_ascii=False))
