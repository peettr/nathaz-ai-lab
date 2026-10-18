"""Verify expanded diagnostic baseline with immutable full-catalog H08 NPZs."""
import pathlib,csv,numpy as np,json
P=pathlib.Path(__file__).resolve().parent;OLD=P.parent/'evidence_v3/results_v3'
site=[r['site'] for r in csv.DictReader(open(P/'sites_min.csv'))]
rows=[r for r in csv.DictReader(open(P/'paired_peaks_5pct.csv')) if r['variant']=='base']
keys={(r['catalog'].lower(),int(r['event'])) for r in rows};old={}
for cat in ('raft','storm'):
 for f in sorted(OLD.glob(cat+'_*.npz')):
  with np.load(f) as d:
   for i,id in enumerate(d['ids']):
    key=(cat,int(id))
    if key in keys:
     if key in old:raise ValueError('duplicate old event '+str(key))
     old[key]=d['peaks'][i,0].copy()
assert len(keys)==len(old),(len(keys),len(old))
diff=[]
for r in rows:
 a=float(r['peak_ms']);b=float(old[(r['catalog'].lower(),int(r['event']))][site.index(r['site'])]);diff.append(abs(a-b))
result=dict(events=len(keys),station_rows=len(rows),max_abs_diff_ms=max(diff),p99_abs_diff_ms=float(np.quantile(diff,.99)))
(P/'baseline_validation_5pct.json').write_text(json.dumps(result,indent=2))
print(result)
