from pathlib import Path
from hashlib import sha256
import json
R=Path('/content/luw_citystab_v1')
d={}
for name in ['head','off']:
 root=R/name/'case/RESULTS'
 d[name]={str(p.relative_to(root)):[p.stat().st_size,sha256(p.read_bytes()).hexdigest()] for p in root.rglob('*') if p.is_file()}
(R/'compare2.json').write_text(json.dumps(d,indent=2))
print(json.dumps(d,indent=2));print('equal',d['head']==d['off'])
