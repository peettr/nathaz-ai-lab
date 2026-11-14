"""Quantify reference-field sensitivity on previously saved paired 1979–2008 point series."""
from pathlib import Path
import numpy as np,csv
root=Path(__file__).resolve().parent
old=root.parent
names=['KMSP','KDSM','KOMA','KDTW','KPIT','KALB','DFW','AUS']
new=[np.load(root/'reference'/f'cold_{y}.npz') for y in range(1980,2008)]
nt=np.concatenate([d['time'] for d in new]);sp=np.concatenate([np.hypot(d['u'],d['v']) for d in new]);out=[]
for j,site in enumerate(names):
 with np.load(old/f'points_{site}.npz') as d:
  oi=np.searchsorted(d['time'],nt)
  assert len(oi)==len(nt) and np.array_equal(d['time'][oi],nt)
  oldsp=d['era'][oi];ns=sp[:,j]
  era_mx=np.array([ns[(nt.astype('datetime64[Y]').astype(int)+1970)==y].max() for y in range(1980,2008)])
  old_mx=np.array([oldsp[(nt.astype('datetime64[Y]').astype(int)+1970)==y].max() for y in range(1980,2008)])
  out.append(dict(site=site,paired_6h=len(nt),old_1p5_interp_mean=float(oldsp.mean()),new_0p25_conservative_mean=float(ns.mean()),mean_change_pct=100*(ns.mean()/oldsp.mean()-1),cold_sample_max=float(ns.max()),old_cold_sample_max=float(oldsp.max()),max_change_pct=100*(ns.max()/oldsp.max()-1)))
with (root/'reference_sensitivity.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=out[0].keys());w.writeheader();w.writerows(out)
for a in out:print(a['site'],a['mean_change_pct'],a['max_change_pct'])
