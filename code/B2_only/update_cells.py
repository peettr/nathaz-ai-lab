import json,re,sys
from pathlib import Path
c=Path(sys.argv[1]); t=Path(sys.argv[2]).read_text(); m=re.search(r"\bcells:\s*(\d+)",t); assert m,m is not None
n=int(m.group(1)); assert n>1000
p=c/'sample_cells.json'; j=json.loads(p.read_text()); j['mesh_cells']=n; j['cell_ids']=[0,1,2,3,4]; p.write_text(json.dumps(j)+'\n'); print('B2 cells',n)
