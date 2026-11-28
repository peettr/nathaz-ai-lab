#!/usr/bin/env python3
"""Freeze C2a candidate IDs from final ASCII OpenFOAM 0/C, not gradients."""
import json
import pathlib
import random
import re
import sys

case = pathlib.Path(sys.argv[1])
s = (case / '0/C').read_text()
assert re.search(r'\bformat\s+ascii\s*;', s[:4096])
m = re.search(r'\binternalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(', s)
assert m
n = int(m[1]); tail = s[m.end():]
end = re.search(r'(?m)^\s*\)\s*;\s*$', tail)
assert end
coords = re.findall(r'(?m)^\s*\(\s*([-+\deE.]+)\s+([-+\deE.]+)\s+([-+\deE.]+)\s*\)\s*$', tail[:end.start()])
assert len(coords) == n, (len(coords), n)
ids = [i for i, (x, y, z) in enumerate(coords)
       if -24 <= float(x) <= 24 and -24 <= float(y) <= 24 and 0 <= float(z) <= 24]
assert len(ids) >= 5
chosen = sorted(random.Random(2621).sample(ids, 5))
print(json.dumps(dict(mesh_cells=n, seed=2621, candidate_count=len(ids), cell_ids=chosen)))
