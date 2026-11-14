"""Recheck frozen SAE held-out correlations, storm bootstrap and whole-dictionary null."""
import json,time
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr,rankdata
R=Path('/content/l2612-stepH'); R.mkdir(exist_ok=True)
S=Path('/content/l2612-input')
records=json.loads((S/'cohort_2021.json').read_text()); features=np.load(S/'features.npy'); old=json.loads((S/'correlations.json').read_text())
te=np.array([i for i,r in enumerate(records) if r['year']>=2021]); assert len(te)==46 and features.shape==(len(records),1536)
def rho(x,y):
 ok=np.isfinite(x)&np.isfinite(y)
 if ok.sum()<10 or len(np.unique(x[ok]))<2 or len(np.unique(y[ok]))<2:return None
 return float(spearmanr(x[ok],y[ok]).statistic)
def bootstrap(p,j,count,seed):
 y=np.array([r[p] if r[p] is not None else np.nan for r in records],float);local=te[np.isfinite(y[te])];x=features[:,j];rng=np.random.default_rng(seed);vals=[]
 for _ in range(count):
  d=rng.choice(local,len(local),replace=True);v=rho(x[d],y[d]);
  if v is not None:vals.append(v)
 return np.quantile(vals,[.025,.975]).tolist()
def null(p,count,seed):
 y=np.array([r[p] if r[p] is not None else np.nan for r in records],float);valid=te[np.isfinite(y[te])]
 A=rankdata(features[valid],axis=0);A-=A.mean(axis=0);norm=np.sqrt((A*A).sum(axis=0));norm[norm==0]=np.inf
 v=rankdata(y[valid]);v-=v.mean();den=np.sqrt((v*v).sum());rng=np.random.default_rng(seed)
 maxima=[float(np.max(abs(rng.permutation(v)@A)/(den*norm))) for _ in range(count)]
 return {'maximum':max(maxima),'q95':float(np.quantile(maxima,.95)),'n':len(valid)}
out={'source':'NOAA IBTrACS v04r01 NA/WP; main-stream (/b1/Add_26) SAE features.npy from step2, 2021 one storm/one time','seeds':[2612+100*i for i in range(20)],'expanded':{}}
for p in ('wind_kt','pres_hpa'):
 out['expanded'][p]=[]
 for seed in out['seeds']:
  n=null(p,1000,seed);cand=[]
  for row in old['candidates'][p]:
   j=row['feature'];ci=bootstrap(p,j,5000,seed+j);lo=0 if ci[0]<=0<=ci[1] else min(abs(ci[0]),abs(ci[1]));mag=abs(row['test_rho'])
   cand.append({'feature':j,'ci':ci,'lower_abs':lo,'test_rho':row['test_rho'],'main':bool(mag>=.5 and lo>n['maximum']),'q95_read':bool(mag>=.5 and lo>n['q95'])})
  out['expanded'][p].append({'seed':seed,'null':n,'candidates':cand})
  (R/'b_results.json').write_text(json.dumps(out,indent=2,allow_nan=False));print('expanded',p,seed,flush=True)
(R/'b.done').write_text('ok\n')
