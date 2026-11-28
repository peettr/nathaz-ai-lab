"""Paired peak summaries for expanded deterministic 5% event sample."""
import csv,pathlib,collections,numpy as np,json
P=pathlib.Path(__file__).resolve().parent
peaks=collections.defaultdict(dict)
for r in csv.DictReader(open(P/'paired_peaks_5pct.csv')):peaks[(r['catalog'],r['event'],r['site'])][r['variant']]=float(r['peak_ms'])
vs=['base','Pc_only','RMW_only','both'];ps=[]
for (catalog,event,site),rec in peaks.items():
 if len(rec)!=4:continue
 ps.append(dict(catalog=catalog,event=event,site=site,**rec))
with open(P/'paired_wide_5pct.csv','x') as f:
 w=csv.DictWriter(f,fieldnames=['catalog','event','site']+vs);w.writeheader();w.writerows(ps)
def q(values):
 a=np.array(values,dtype=float);return dict(n=len(a),p50=float(np.quantile(a,.5)) if len(a) else None,p90=float(np.quantile(a,.9)) if len(a) else None,p99=float(np.quantile(a,.99)) if len(a) else None)
ss=[]
for catalog in ('RAFT','STORM'):
 for site in ['ALL']+sorted(set(r['site'] for r in ps)):
  g=[r for r in ps if r['catalog']==catalog and (site=='ALL' or r['site']==site)];posit=[r for r in g if r['base']>5]
  threshold=float(np.quantile([r['base'] for r in posit],.9)) if len(posit)>0 else float('inf')
  top=[r for r in posit if r['base']>=threshold]
  for variant in vs:
   z=q([r[variant] for r in posit]);d=q([100*(r[variant]/r['base']-1) for r in posit]) if variant!='base' else q([])
   t=q([100*(r[variant]/r['base']-1) for r in top]) if variant!='base' else q([])
   ss.append(dict(catalog=catalog,site=site,variant=variant,n_events=len(g),n_baseline_gt5=len(posit),n_baseline_top10=len(top),peak_p50=z['p50'],peak_p90=z['p90'],peak_p99=z['p99'],pct_delta_p50=d['p50'],pct_delta_p90=d['p90'],pct_delta_p99=d['p99'],top10_delta_p50=t['p50']))
with open(P/'peak_summary_5pct.csv','x') as f:
 w=csv.DictWriter(f,fieldnames=ss[0].keys());w.writeheader();w.writerows(ss)
print(json.dumps(dict(raw_events=dict(collections.Counter(r['catalog'] for r in ps)),positive=dict(collections.Counter(r['catalog'] for r in ps if r['base']>5))),indent=2))
