"""Unconditional station-event peak quantiles including zero exposures."""
import csv,pathlib,numpy as np
P=pathlib.Path(__file__).resolve().parent;rows=list(csv.DictReader(open(P/'paired_wide_5pct.csv')))
site=[r['site'] for r in csv.DictReader(open(P/'sites_min.csv'))]
out=[]
for cat in ('RAFT','STORM'):
 for s in ['ALL']+site:
  g=[r for r in rows if r['catalog']==cat and (s=='ALL' or r['site']==s)]
  for var in ('base','Pc_only','RMW_only','both'):
   x=np.array([float(r[var]) for r in g]);out.append(dict(catalog=cat,site=s,variant=var,n=len(x),zero_fraction=float(np.mean(x==0)),p50=float(np.quantile(x,.5)),p90=float(np.quantile(x,.9)),p99=float(np.quantile(x,.99))))
with open(P/'peak_all_event_5pct.csv','x') as f:
 w=csv.DictWriter(f,fieldnames=out[0].keys());w.writeheader();w.writerows(out)
for r in out:
 if r['site']=='ALL':print(r)
