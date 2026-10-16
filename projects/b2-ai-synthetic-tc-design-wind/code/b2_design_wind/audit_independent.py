#!/usr/bin/env python3
"""Read-only independent numerical audit of the completed B2 v3 batch archive."""
import csv,json,pathlib,numpy as np
B=pathlib.Path(__file__).parent/'evidence_v3';P=B/'products_v3'
rows=list(csv.DictReader((P/'return_levels.csv').open()));sites=[r['site'] for r in rows]
assert len(rows)==19 and len(set(sites))==19
checks={}
for name,nraw,years in [('raft',40000,40000/14.5),('storm',107063,10000)]:
 files=sorted((B/'results_v3').glob(name+'_*.npz'));arrays=[np.load(f) for f in files]
 ids=np.concatenate([a['ids'] for a in arrays]);peaks=np.concatenate([a['peaks'] for a in arrays]);ratios=np.concatenate([a['ratios'] for a in arrays]);assert len(ids)==len(np.unique(ids)) and peaks.shape==(len(ids),3,19) and np.isfinite(peaks).all();assert np.all(peaks>=0) and np.isfinite(ratios[peaks>0]).all()
 meta=json.loads((B/'results_v3'/f'{name}_complete.json').read_text());assert meta['counts']['raw']==nraw and meta['counts']['selected']==len(ids) and meta['counts']['failed']==0 and meta['counts']['invalid']+len(ids)==nraw
 errors=[];missing_ci=[]
 for j,row in enumerate(rows):
  for T in (50,700):
   v=np.sort(peaks[:,0,j][peaks[:,0,j]>0])[::-1];rank=(nraw+1)*years/(T*nraw);assert 1<=rank<=len(v)
   estimate=np.interp(rank,np.arange(1,len(v)+1),v);reported=float(row[f'{name}{T}_ms']);errors.append(abs(estimate-reported))
   lo=float(row[f'{name}{T}_ci90_lo_ms']);hi=float(row[f'{name}{T}_ci90_hi_ms']);assert lo<=hi
   if not lo<=reported<=hi:missing_ci.append((row['site'],T,reported,lo,hi))
 checks[name]={'batches':len(files),'n_selected':len(ids),'raw':nraw,'max_rank_recalculation_abs_ms':max(errors),'ci_does_not_contain_point':missing_ci,'peak_max_ms':float(peaks.max())}
 assert max(errors)<0.00051
checks['site_labels']=sites
(B/'audit_independent.json').write_text(json.dumps(checks,indent=2))
print(json.dumps(checks,indent=2))
