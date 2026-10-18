"""Summaries for input distributions and paired H08 site-event peaks; no return levels."""
import csv,pathlib,collections,numpy as np,json
P=pathlib.Path(__file__).resolve().parent
obs=list(csv.DictReader(open(P/'obs_inputs.csv')));cat=list(csv.DictReader(open(P/'inputs_land.csv')))
def q(values):
 v=np.array([float(x) for x in values if x not in ('',None)],dtype=float);v=v[np.isfinite(v)]
 return dict(n=len(v),p50=float(np.quantile(v,.5)) if len(v) else None,p90=float(np.quantile(v,.9)) if len(v) else None,p99=float(np.quantile(v,.99)) if len(v) else None)
def cls(v):return 'TS' if v<64 else 'Cat1-2' if v<96 else 'Cat3+'
for r in obs:
 r['catalog']='HURDAT2+EBTRK';r['vmax_kt']=r['vmax'];r['pc_hpa']=r['pc'];r['dp1010_hpa']=str(max(0,1010-float(r['pc']))) if r['pc'] else '';r['rmw_nmi']=r['rmw'];r['land']='land' if r['land_km'] and float(r['land_km'])<0 else ('sea' if r['land_km'] else 'missing')
for r in cat+obs:r['intensity']=cls(float(r['vmax_kt']))
summary=[]
for catalog in ('RAFT','STORM','HURDAT2+EBTRK'):
 for intensity in ('ALL','TS','Cat1-2','Cat3+'):
  for land in ('ALL','sea','land'):
   g=[r for r in cat+obs if r['catalog']==catalog and (intensity=='ALL' or r['intensity']==intensity) and (land=='ALL' or r['land']==land)]
   for col in ('vmax_kt','pc_hpa','dp1010_hpa','rmw_nmi'):
    summary.append(dict(catalog=catalog,intensity=intensity,land=land,variable=col,**q([r[col] for r in g])))
with open(P/'input_summary.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=summary[0].keys());w.writeheader();w.writerows(summary)
peaks=collections.defaultdict(dict)
for r in csv.DictReader(open(P/'paired_peaks.csv')):peaks[(r['catalog'],r['event'],r['site'])][r['variant']]=float(r['peak_ms'])
vs=['base','Pc_only','RMW_only','both'];ps=[]
for (catalog,event,site),rec in peaks.items():
 if len(rec)!=4:continue
 ps.append(dict(catalog=catalog,event=event,site=site,**rec))
with open(P/'paired_wide.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=['catalog','event','site']+vs);w.writeheader();w.writerows(ps)
ss=[]
for catalog in ('RAFT','STORM'):
 for site in ['ALL']+sorted(set(r['site'] for r in ps)):
  g=[r for r in ps if r['catalog']==catalog and (site=='ALL' or r['site']==site)];posit=[r for r in g if r['base']>5]
  for variant in vs:
   sq=q([r[variant] for r in posit]);d=q([100*(r[variant]/r['base']-1) for r in posit]) if variant!='base' else q([])
   ss.append(dict(catalog=catalog,site=site,variant=variant,n_events=len(g),n_baseline_gt5=len(posit),peak_p50=sq['p50'],peak_p90=sq['p90'],peak_p99=sq['p99'],pct_delta_p50=d['p50'],pct_delta_p90=d['p90'],pct_delta_p99=d['p99']))
with open(P/'peak_summary.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=ss[0].keys());w.writeheader();w.writerows(ss)
print(json.dumps(dict(raw_counts=collections.Counter(r['catalog'] for r in cat),samples=collections.Counter(r['catalog'] for r in ps),positive=collections.Counter(r['catalog'] for r in ps if r['base']>5)),indent=2))
