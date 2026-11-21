"""Cat4/5 conditional paired diagnostics from sampled H08 peaks."""
import csv,json,pathlib,collections,numpy as np
P=pathlib.Path(__file__).resolve().parent
meta={(r['catalog'],r['event']):float(r['max_vmax_kt']) for r in csv.DictReader(open(P/'diag5_event_meta.csv'))}
rows=list(csv.DictReader(open(P/'paired_wide_5pct.csv')))
out={}
for cat in ('RAFT','STORM'):
 g=[r for r in rows if r['catalog']==cat and meta[(cat,r['event'])]>=114 and float(r['base'])>5]
 for name,subset in [('positive_gt5',g),('baseline_gt25',[r for r in g if float(r['base'])>25])]:
  d=dict(n_station_events=len(subset),n_distinct_events=len(set(r['event'] for r in subset)))
  for v in ('Pc_only','RMW_only','both'):
   x=np.array([100*(float(r[v])/float(r['base'])-1) for r in subset]);d[v]=dict(p10=float(np.quantile(x,.1)),p50=float(np.quantile(x,.5)),p90=float(np.quantile(x,.9)))
  out[cat+'_'+name]=d
(P/'cat45_paired_5pct.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
