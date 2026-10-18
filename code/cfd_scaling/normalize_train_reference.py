"""Post-hoc reference-scale sensitivity, using only each seed/N's training examples.
The common scalar is a statistical train-pool mean, NOT a physical inflow velocity.
The same scalar divides every held-out case at a given seed/N. No test truth
enters the reference; R2 and pairwise RMSE improvements are scale-invariant.
"""
import json
from pathlib import Path
import numpy as np
p=Path(__file__).parent
D=np.load(p/'urbantales_160_v3.npz'); S=json.loads((p/'group_split.json').read_text()); M=json.loads((p/'metrics_v3.json').read_text())
idx={c:i for i,c in enumerate(D['case'])}
y=D['speed'].astype(np.float32); mask=D['mask']
counts=mask.sum(axis=(1,2)); sums=np.where(mask,y,0).sum(axis=(1,2),dtype=np.float64)
assert len(idx)==538 and len(M['runs'])==12
out={'reference':'training fluid-pixel pooled Uped mean, per seed and N; statistical, not physical speed','runs':[]}
for run in M['runs']:
    seed,n=run['seed'],run['N']
    ids=[idx[c] for c in S['seeds'][str(seed)][str(n)]]
    den=float(sums[ids].sum()); num=int(counts[ids].sum())
    ref=den/num
    assert ref>0 and num>0
    entry={'seed':seed,'N':n,'train_reference':ref,'train_fluid_pixels':num,'methods':{}}
    for name,method in run['methods'].items():
        raw=method['summary']['rmse']
        entry['methods'][name]={'original_rmse':raw,'rmse_divided_by_train_reference':raw/ref,
            'ideal_rmse_divided_by_train_reference':method['summary']['ideal_rmse']/ref,
            'real_rmse_divided_by_train_reference':method['summary']['real_rmse']/ref,
            'median_r2_unchanged':method['summary']['median_r2']}
    out['runs'].append(entry)
(p/'normalization_diagnostic.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
for n in (50,100,200,400):
    v=[r for r in out['runs'] if r['N']==n]
    print(n,'train_ref',round(np.mean([r['train_reference'] for r in v]),5),'range',tuple(round(x,5) for x in [min(r['train_reference'] for r in v),max(r['train_reference'] for r in v)]))
    for method in ('B1','UNet'):
        print(' ',method,'RMSE raw',round(np.mean([r['methods'][method]['original_rmse'] for r in v]),5),'divided',round(np.mean([r['methods'][method]['rmse_divided_by_train_reference'] for r in v]),5))
