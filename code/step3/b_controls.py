"""Recheck frozen SAE held-out correlations, storm bootstrap and whole-dictionary null."""
import json,time
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr,rankdata
R=Path('/content/l2612-step3'); R.mkdir(exist_ok=True)
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
out={'source':'NOAA IBTrACS v04r01 NA/WP; frozen step2 features.npy, 2021 one storm/one time','seeds':[2612,2712,2812],'legacy':{},'expanded':{}}
for p in ('wind_kt','pres_hpa'):
 legacy_null=null(p,200,2760+(p=='pres_hpa'))
 legacy=[]
 for row in old['candidates'][p]:
  j=row['feature'];ci=bootstrap(p,j,1000,2612+j)
  legacy.append({'feature':j,'ci':ci,'rho':rho(features[te,j],np.array([r[p] if r[p] is not None else np.nan for r in records])[te])})
 assert np.allclose([legacy_null['maximum'],legacy_null['q95']],[old['null'][p]['max_200'],old['null'][p]['q95_200']],rtol=1e-10,atol=1e-10)
 for row,orig in zip(legacy,old['candidates'][p]):
  assert np.allclose(row['ci'],orig['test_ci95'],rtol=1e-10,atol=1e-10),(p,row,orig)
  assert np.isclose(row['rho'],orig['test_rho'],rtol=1e-10,atol=1e-10)
 out['legacy'][p]={'null':legacy_null,'candidates':legacy,'exact_match':True}
 print('legacy matched',p,flush=True)
 out['expanded'][p]=[]
 for seed in out['seeds']:
  n=null(p,1000,seed);cand=[]
  for row in old['candidates'][p]:
   j=row['feature'];ci=bootstrap(p,j,5000,seed+j);lo=0 if ci[0]<=0<=ci[1] else min(abs(ci[0]),abs(ci[1]));mag=abs(row['test_rho'])
   cand.append({'feature':j,'ci':ci,'lower_abs':lo,'test_rho':row['test_rho'],'main':bool(mag>=.5 and lo>n['maximum']),'q95_read':bool(mag>=.5 and lo>n['q95'])})
  out['expanded'][p].append({'seed':seed,'null':n,'candidates':cand})
  (R/'b_results.json').write_text(json.dumps(out,indent=2,allow_nan=False));print('expanded',p,seed,flush=True)
(R/'b.done').write_text('ok\n')
