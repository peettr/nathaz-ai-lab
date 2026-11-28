#!/usr/bin/env python3
"""Read-only candidate sampling on an already generated OpenFOAM 0/C."""
import json, pathlib, random, re
root = pathlib.Path('/groups/kareem/[用户]/L26_21_DAFOAM_20261114_G1_mesh_v5/cases_review_v5')
for grade in ('coarse', 'medium'):
    s = (root/grade/'0/C').read_text()
    assert re.search(r'\bformat\s+ascii\s*;', s[:4096])
    m = re.search(r'\binternalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(', s)
    assert m, grade
    n = int(m[1]); tail = s[m.end():]
    end = re.search(r'(?m)^\s*\)\s*;\s*$', tail)
    assert end, grade
    coords = re.findall(r'(?m)^\s*\(\s*([-+\deE.]+)\s+([-+\deE.]+)\s+([-+\deE.]+)\s*\)\s*$', tail[:end.start()])
    assert len(coords) == n, (grade, len(coords), n)
    ids = [i for i,(x,y,z) in enumerate(coords) if -24 <= float(x) <= 24 and -24 <= float(y) <= 24 and 0 <= float(z) <= 24]
    chosen = sorted(random.Random(2621).sample(ids,5))
    print(json.dumps(dict(grade=grade, mesh_cells=n, seed=2621, candidate_count=len(ids), cell_ids=chosen)))
