#!/usr/bin/env python3
"""Join B0b replay results with read-only D0/D1b export residual metadata."""
import csv, statistics, json
from pathlib import Path
root=Path(__file__).parent

def read(name):
    with (root/name).open(newline='') as f:
        return list(csv.DictReader(f))

t0={}
for r in read('q1_residuals_v2.csv'):
    step,corr=map(int,r['system'].split('-')[1:])
    t0[(round(step*.0005,7),corr)]=(float(r['openfoam_initial']),int(r['iterations']))
later={}
meta=json.loads((root/'b0b_later_export_meta_readonly.json').read_text())
for r in read('q1_residuals_D1.csv'):
    if r['segment']=='later':
        m=meta[r['system'].split('/')[-1]]
        assert abs(float(m['initial_residual'])-float(r['openfoam_initial'])) < 1e-12
        later[(round(float(r['time']),7),int(r['correction']))]=(float(r['openfoam_initial']),int(m['iterations']))
assert len(t0)==len(later)==20
rows=[]; compare=[]
for tier,n in [('ta',1),('tb',1),('ta',48),('tb',48)]:
    data=read(f'b0b_{tier}_n{n}_v3.csv')
    assert len(data)==140,(tier,n,len(data))
    selected=[r for r in data if r['segment']=='t0' or (r['segment']=='later' and float(r['time'])>44.0125)]
    assert len(selected)==40,(tier,n,len(selected))
    for r in selected:
        key=(round(float(r['time']),7),int(r['corr']))
        exp_initial,exp_iter=(t0 if r['segment']=='t0' else later)[key]
        initial=float(r['initial_residual'])
        rows.append(dict(segment=r['segment'],time=r['time'],corr=r['corr'],tier=tier,cores=n,
                         initial_residual=r['initial_residual'],final_residual=r['final_residual'],
                         iterations=r['iterations'],wall_seconds=r['wall_seconds'],
                         data_source='CRC B0b native OpenFOAM GAMG replay (D0/D1b-derived cases)'))
        compare.append(dict(segment=r['segment'],time=r['time'],corr=r['corr'],tier=tier,cores=n,
                            replay_initial=initial,export_initial=exp_initial,
                            replay_iterations=int(r['iterations']),export_iterations=exp_iter,
                            initial_ratio=(initial/exp_initial if exp_initial else None),
                            data_source='CRC B0b replay vs D0 t0 or D1b later exported meta'))
assert len(rows)==len(compare)==160
assert len({(r['segment'],r['time'],r['corr'],r['tier'],r['cores']) for r in rows})==160
for name,items in [('b0_timing.csv',rows),('b0_vs_export.csv',compare)]:
    out=root/name
    assert not out.exists(),out
    with out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=items[0]);w.writeheader();w.writerows(items)
for tier in ('ta','tb'):
    for n in (1,48):
        subset=[r for r in rows if r['segment']=='later' and r['tier']==tier and r['cores']==n]
        print(tier,n,'later median wall',statistics.median(float(r['wall_seconds']) for r in subset),
              'range',min(float(r['wall_seconds']) for r in subset),max(float(r['wall_seconds']) for r in subset))
print('rows',len(rows))
