"""Check each observed model case against all three baseline raw-valid counts."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('model',type=Path,nargs='+');a=p.parse_args()
b={k:json.loads((a.root/f'v6s2_{k}_direction_verified_1015.json' if k!='B0' else a.root/'v6s2_B0_summary_1015.json').read_text()) for k in ('B0','B1','B2')}
out={'baseline_disagreements':[],'model_disagreements':{},'unavailable_models':[]}
for part in ('val','test'):
    for case,row in b['B0'][part].items():
        ns={k:b[k][part][case]['n'] for k in b}
        if len(set(ns.values()))!=1:out['baseline_disagreements'].append({'split':part,'case':case,'n':ns})
for f in a.model:
    if not f.exists():out['unavailable_models'].append(str(f));continue
    model=json.loads(f.read_text());bad=[]
    for part in ('val','test'):
        assert set(model[part])==set(b['B0'][part])
        for case,row in model[part].items():
            n=row['n']; ref=b['B0'][part][case]['n']
            if n!=ref:bad.append({'split':part,'case':case,'model_n':n,'baseline_n':ref})
    out['model_disagreements'][str(f)]=bad
print(json.dumps(out,indent=2))
if out['baseline_disagreements'] or any(out['model_disagreements'].values()):raise SystemExit(2)
