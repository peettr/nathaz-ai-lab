"""Postprocess independently written smoke JSONL; exit 41 on failed gate."""
import json, sys
import numpy as np
from pathlib import Path
root=Path(__file__).resolve().parent
# On CRC script is in armA root, outputs are in run_01d.
run=root/'run_01d'
a=[json.loads(s) for s in (run/'smoke_01d.jsonl').read_text().splitlines() if s.startswith('{')]
b=[json.loads(s) for s in (run/'ad32_01d.jsonl').read_text().splitlines() if s.startswith('{')]
results=[]
for site in ('near','far'):
    rows=[r for r in a if r.get('stage')=='smoke' and r['site']==site]
    plateau=[r for r in a if r.get('stage')=='plateau' and r['site']==site]
    ad32=[r for r in b if r.get('stage')=='ad32' and r['site']==site]
    assert len(rows)==3 and len(plateau)==1 and len(ad32)==1
    x=np.array(rows[0]['ad']); y=np.array(ad32[0]['ad'])
    cosine=float(np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y))) if np.linalg.norm(x)*np.linalg.norm(y) else None
    selected=plateau[0]['selected_fraction']
    rec=next((r for r in rows if r['fraction']==selected),None)
    passed=bool(plateau[0]['pass'] and rec and cosine is not None)
    results.append({'site':site,'selected_fraction':selected,'float32_vs_float64_cosine':cosine,'gate':passed})
print(json.dumps({'stage':'gate_01d','results':results,'pass':all(r['gate'] for r in results)}),flush=True)
sys.exit(0 if all(r['gate'] for r in results) else 41)
