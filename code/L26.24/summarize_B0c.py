#!/usr/bin/env python3
"""Aggregate two B0c output CSVs; fail closed on counts, residuals, repeats."""
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
import sys
root=Path(sys.argv[1]); out=Path(sys.argv[2])
rows=[]; by=defaultdict(list)
for label,cores in [('single',1),('mpi48',48)]:
    p=root/label/'raw.csv'
    with p.open() as f: part=list(csv.DictReader(f))
    assert len(part)==200,(p,len(part))
    for row in part:
        assert int(row['cores'])==cores and row['segment']=='later'
        key=(cores,row['time'],int(row['corr']),row['tier'])
        by[key].append(row)
        initial=float(row['initial_residual']); final=float(row['final_residual'])
        target=1e-8 if row['tier']=='Tb' else (1e-6 if int(row['corr'])==4 else max(1e-6,0.05*initial))
        assert final<=target*(1+1e-9),(key,row)
        rows.append(row)
assert len(by)==80,len(by)
per=defaultdict(list); cold=defaultdict(list); warm=defaultdict(list)
for key,part in by.items():
    assert sorted(int(x['rep']) for x in part)==[1,2,3,4,5]
    initial=[float(x['initial_residual']) for x in part]
    assert max(initial)-min(initial)<=1e-10*max(1,max(abs(x) for x in initial)),(key,initial)
    times={int(x['rep']):float(x['wall_seconds']) for x in part}
    per[(key[0],key[3])].append(statistics.median(times.values()))
    cold[(key[0],key[3])].append(times[1]); warm[(key[0],key[3])].append(statistics.median(times[x] for x in range(2,6)))
assert all(len(per[(n,t)])==20 for n in (1,48) for t in ('Ta','Tb'))
rows.sort(key=lambda x:(int(x['cores']),float(x['time']),int(x['corr']),x['tier'],int(x['rep'])))
with (out/'b0_repeat.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary={'source':'B0c CFD replay on CRC; same pressure matrix within five repetitions, not identical to prior exports','systems_per_core_tier':20,'rows':len(rows),'method':'median of five solve wall seconds per system, then inclusive quartiles across 20 systems','test':{}}
for n in (1,48):
    summary['test'][str(n)]={}
    for t in ('Ta','Tb'):
        vals=per[(n,t)]; q=statistics.quantiles(vals,n=4,method='inclusive')
        summary['test'][str(n)][t]={'median_seconds':statistics.median(vals),'q1_seconds':q[0],'q3_seconds':q[2],'iqr_seconds':q[2]-q[0],'rep1_median_seconds':statistics.median(cold[(n,t)]),'rep2_to_5_median_seconds':statistics.median(warm[(n,t)]),'cache_note':'rep1 may reuse GAMG mesh agglomeration from trajectory; not proven cold'}
(out/'b0_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,indent=2,ensure_ascii=False))
