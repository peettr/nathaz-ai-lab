#!/usr/bin/env python3
"""Read immutable B0c raw results; select the preregistered last five steps."""
import csv, json, statistics
from collections import defaultdict
from pathlib import Path
root=Path(__file__).resolve().parent
source={'1':root/'b0c_single_raw_1755233.csv','48':root/'b0c_mpi48_raw_1755234.csv'}
times={'44.013','44.0135','44.014','44.0145','44.015'}
by=defaultdict(list); selected=[]; excluded={}
for cores,path in source.items():
    with path.open() as f: raw=list(csv.DictReader(f))
    assert len(raw)==240,(path,len(raw))
    excluded[cores]=sorted({r['time'] for r in raw if r['time'] not in times})
    assert excluded[cores]==['44.0125'],excluded
    for row in raw:
        if row['time'] not in times: continue
        assert row['segment']=='later' and row['cores']==cores,row
        key=(cores,row['time'],int(row['corr']),row['tier'])
        by[key].append(row); selected.append(row)
assert len(selected)==400 and len(by)==80,(len(selected),len(by))
metrics=defaultdict(list); rep1=defaultdict(list); warm=defaultdict(list)
for key,rows in by.items():
    assert sorted(int(r['rep']) for r in rows)==[1,2,3,4,5],key
    init=[float(r['initial_residual']) for r in rows]
    assert max(init)-min(init)<=1e-10*max(1,max(map(abs,init))),(key,init)
    for r in rows:
        final=float(r['final_residual'])
        target=1e-8 if r['tier']=='Tb' else (1e-6 if int(r['corr'])==4 else max(1e-6,0.05*float(r['initial_residual'])))
        assert final<=target*(1+1e-9),(key,final,target)
        assert float(r['wall_seconds'])>=0 and int(r['iterations'])>=0
    wall={int(r['rep']):float(r['wall_seconds']) for r in rows}
    k=(key[0],key[3]); metrics[k].append(statistics.median(wall.values()))
    rep1[k].append(wall[1]);warm[k].append(statistics.median(wall[i] for i in (2,3,4,5)))
assert all(len(metrics[n,t])==20 for n in ('1','48') for t in ('Ta','Tb'))
selected.sort(key=lambda r:(int(r['cores']),float(r['time']),int(r['corr']),r['tier'],int(r['rep'])))
with (root/'b0_repeat.csv').open('x',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(selected[0]));writer.writeheader();writer.writerows(selected)
summary={'source':'B0c CRC CFD replay; immutable raw single/mpi48 CSV, last five steps only; not identical to exported matrices','rows':len(selected),'systems_per_core_tier':20,'excluded_extra_time':excluded,'method':'per-system median of five solve times, then inclusive quartiles across 20 systems','test':{}}
for n in ('1','48'):
    summary['test'][n]={}
    for tier in ('Ta','Tb'):
        vals=metrics[n,tier]; q=statistics.quantiles(vals,n=4,method='inclusive')
        summary['test'][n][tier]={'median_seconds':statistics.median(vals),'q1_seconds':q[0],'q3_seconds':q[2],'iqr_seconds':q[2]-q[0],'rep1_median_seconds':statistics.median(rep1[n,tier]),'rep2_to_5_median_seconds':statistics.median(warm[n,tier]),'cache_note':'rep1 might already reuse GAMG agglomeration from trajectory; not proven cold'}
(root/'b0_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,indent=2,ensure_ascii=False))
