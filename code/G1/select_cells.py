#!/usr/bin/env python3
"""Select five cell IDs per mesh from the ASCII 0/C field, once before solving."""
import json,random,re,sys
from pathlib import Path
case=Path(sys.argv[1]); grade=case.name
p=case/'0/C';s=p.read_text();assert re.search(r'\bformat\s+ascii\s*;',s[:4096]); m=re.search(r'\binternalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(',s);assert m
n=int(m[1]);tail=s[m.end():]; end=re.search(r'(?m)^\s*\)\s*;\s*$',tail); assert end, 'missing list terminator'; coords=re.findall(r'(?m)^\s*\(\s*([-+\deE.]+)\s+([-+\deE.]+)\s+([-+\deE.]+)\s*\)\s*$',tail[:end.start()]);assert len(coords)==n,(len(coords),n)
# Within 2H of the building footprint in horizontal distance and 0<=z<=3H.
# Geometry [-8,8]^2 x [0,8]; rectangle expanded by 2H=16m.
ids=[i for i,(x,y,z) in enumerate(coords) if -24<=float(x)<=24 and -24<=float(y)<=24 and 0<=float(z)<=24]
seed=2621; rng=random.Random(seed); assert len(ids)>=5
chosen=sorted(rng.sample(ids,5));out={'seed':seed,'grade':grade,'mesh_cells':n,'candidate_count':len(ids),'rule':'cell centres x,y in [-24,24] m and z in [0,24] m; 2H expansion of building footprint','cell_ids':chosen}
q=case/'sample_cells.json';assert not q.exists();q.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
