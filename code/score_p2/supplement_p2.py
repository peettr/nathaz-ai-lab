#!/usr/bin/env python3
"""Post-hoc descriptive cross-source supplementary tabulation, no new fitting/verdict."""
import csv,gzip,math,json,collections
from pathlib import Path
p=Path(__file__).resolve().parent;parent=p.parent
training=collections.defaultdict(list)
with gzip.open(parent/'pairs_p2.csv.gz','rt') as f:
 for r in csv.DictReader(f):
  if r['source']=='FOUR_v200_GFS' and r['season'] in ('1','2') and r['obs_6x10min_complete']=='1' and r['obs_gust_3s_ms']:
   training[r['station']].append(float(r['obs_gust_3s_ms']))
def percentile(vals,q):
 a=sorted(vals);h=(len(a)-1)*q;l=int(h);return a[l]*(1-(h-l))+a[min(l+1,len(a)-1)]*(h-l)
th={k:percentile(v,.95) for k,v in training.items()}
metrics={};crit={'E95_3s':('obs_gust_3s_ms',None),'bridge_20.1':('obs_gust_1s_ms',20.1),'bridge_26.8':('obs_gust_1s_ms',26.8),'bridge_31.3':('obs_gust_1s_ms',31.3),'MEWP_12.5':('obs_gust_1s_ms',12.5),'Beaufort_mean_11.1':('obs_mean_ms',11.1)}
with gzip.open(p/'predictions_p2.csv.gz','rt') as f:
 for r in csv.DictReader(f):
  src=r['source'];t=r['terrain'];st=r['station'];o=metrics.setdefault(src,{})
  for name,(field,cut) in crit.items():
   if not r[field]:continue
   c=th[st] if cut is None else cut;y=float(r[field])>=c;record=o.setdefault(name,{'pooled':collections.Counter(),'terrain':{},'station':{}})
   for group,counter in [('pooled',record['pooled']),('terrain',record['terrain'].setdefault(t,collections.Counter())),('station',record['station'].setdefault(st,collections.Counter()))]:
    counter['n']+=1;counter['events']+=int(y)
    for method in ['G0','G1','G2']:
     alarm=r[method+'_alarm']=='True';counter[method+'_hit']+=int(y and alarm);counter[method+'_fa']+=int(not y and alarm);counter[method+'_alerts']+=int(alarm)
def finish(c):
 n=c['n'];e=c['events'];b=n-e;o={'n':n,'events':e}
 for m in ['G0','G1','G2']:
  hit=c[m+'_hit'];fa=c[m+'_fa'];alerts=c[m+'_alerts'];o[m]={'POD':hit/e if e else None,'POFD':fa/b if b else None,'FAR':fa/alerts if alerts else None,'PSS':hit/e-fa/b if e and b else None}
 return o
for src,d in metrics.items():
 for name,x in d.items():
  x['pooled']=finish(x['pooled']);x['terrain']={k:finish(v) for k,v in x['terrain'].items()};x['station_lt10']=[k for k,v in x['station'].items() if v['events']<10];del x['station']
(p/'supplement_descriptive_p2.json').write_text(json.dumps({'status':'post-hoc descriptive only; E95 alerts reused for alternative target; not equivalent event-target warnings','training_3s_p95':th,'by_source':metrics},ensure_ascii=False,indent=2));print(p/'supplement_descriptive_p2.json')
