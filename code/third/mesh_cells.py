#!/usr/bin/env python3
import json,re,sys
from pathlib import Path
s=Path(sys.argv[1]).read_text(); assert 'Mesh OK' in s
m=re.search(r'^\s*cells:\s*(\d+)',s,re.M); assert m,s[-1000:]
n=int(m.group(1)); assert 0<n<100000
Path(sys.argv[2]).write_text(json.dumps({'mesh_cells':n})+'\n')
print('MESH_CELLS',n)
