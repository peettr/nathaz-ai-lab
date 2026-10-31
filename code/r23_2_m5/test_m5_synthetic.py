"""Synthetic training-only scorer smoke. Not an M5 scientific result."""
import sys, numpy as np, pandas as pd
sys.path.insert(0,'/content/m5')
import m5_score as s
rng=np.random.default_rng(17)
rows=[]
for site in range(12):
 for fhr in s.FHRS:
  for day in range(50):
   init=pd.Timestamp('2023-10-01',tz='UTC')+pd.Timedelta(days=day)
   raw=float(rng.normal(6,1)); v1=raw+.3
   rows.append((str(site),init,init+pd.Timedelta(hours=fhr),fhr,raw,v1,float(site),s.TERRAIN[site//3],raw+.1*site))
cols=['site','init_utc','valid_end_utc','fhr','raw','v1','dz','terrain','obs']
a=pd.DataFrame(rows,columns=cols)
a['issue_utc']=a.init_utc+pd.Timedelta(hours=4);a['info_cutoff_utc']=a.issue_utc
s.guard(a,4)
b=a.copy();b.valid_end_utc=b.valid_end_utc+pd.Timedelta(days=100);b.init_utc=b.init_utc+pd.Timedelta(days=100);b.issue_utc=b.issue_utc+pd.Timedelta(days=100);b.info_cutoff_utc=b.issue_utc
p,c=s.predict(a,b);assert len(p)==len(b) and len(c)==12*4*5
x=s.bootstrap(p[p.fhr==6],6,4,n_draws=8);assert len(x)>30 and next(v for v in x if v['metric']=='D')['bootstrap_valid']==8
bad=b.copy();bad.loc[0,'info_cutoff_utc']=bad.loc[0,'issue_utc']+pd.Timedelta(seconds=1)
try:s.guard(bad,4)
except ValueError:pass
else:raise AssertionError('guard did not reject future information')
print('SYNTHETIC_SCORE_PASS',len(p),len(x))
