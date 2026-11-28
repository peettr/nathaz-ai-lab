"""Cross-check diagnostic H08 base against immutable first-round per-event peaks."""
import pathlib,csv,numpy as np,json,collections
P=pathlib.Path(__file__).resolve().parent;OLD=P.parent/'evidence_v3/results_v3'
site=[r['site'] for r in csv.DictReader(open(P/'sites_min.csv'))]; assert len(site)==19
keys={(r['catalog'].lower(),int(r['event'])) for r in csv.DictReader(open(P/'paired_peaks.csv')) if r['variant']=='base'}
old={};seen=set()
for cat in ('raft','storm'):
 for file in sorted(OLD.glob(cat+'_*.npz')):
  d=np.load(file)
  for k,values in zip(d['ids'],d['peaks']):
   key=(cat,int(k))
   if key in keys:
    if key in seen:raise ValueError('duplicate '+str(key))
    old[key]=values[0];seen.add(key)
rr=[]
for r in csv.DictReader(open(P/'paired_peaks.csv')):
 if r['variant']!='base':continue
 key=(r['catalog'].lower(),int(r['event']))
 if key not in old:continue
 j=site.index(r['site']);ref=float(old[key][j]);val=float(r['peak_ms']);rr.append(dict(catalog=r['catalog'],event=r['event'],site=r['site'],new=val,old=ref,abs_delta=abs(val-ref)))
with open(P/'baseline_validation.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=rr[0].keys());w.writeheader();w.writerows(rr)
print(json.dumps(dict(keys=len(keys),found=len(old),station_rows=len(rr),max_abs_delta=max(r['abs_delta'] for r in rr),p99_abs_delta=float(np.quantile([r['abs_delta'] for r in rr],.99))),indent=2))
