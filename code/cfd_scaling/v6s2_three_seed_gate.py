"""Frozen three-seed gate: each seed separately, no test-selected checkpoint."""
import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('seed42',type=Path);p.add_argument('seed73',type=Path,nargs='?');a=p.parse_args()
old=json.loads((a.root/'v6_group_summary_1015_122715.json').read_text())
def ideal(name):return name.startswith(('VA','VS','US0625_'))
def row(name,val,tests):
    sub=[r['r2'] if isinstance(r,dict) else r for c,r in tests.items() if ideal(c)]
    assert len(sub)==40,(name,len(sub))
    r={'seed':name,'val_median_r2':val,'ideal40_median_r2':float(np.median(sub))}
    r['pass']=bool(r['val_median_r2']>=.5 and r['ideal40_median_r2']>=.7)
    return r
rows=[row(17,old['val_median_r2'],old['holdout_per_case_r2'])]
for seed,f in ((42,a.seed42),(73,a.seed73)):
    if f is None or not f.is_file():rows.append({'seed':seed,'status':'not completed'});continue
    s=json.loads(f.read_text());rows.append(row(seed,s['val_r2_median'],s['test']))
print(json.dumps({'gate':rows,'all_pass':all(r.get('pass',False) for r in rows)},indent=2))
if any(r.get('pass') is False for r in rows):raise SystemExit(2)
