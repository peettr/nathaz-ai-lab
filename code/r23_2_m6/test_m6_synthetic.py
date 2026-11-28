import importlib.util,sys,json,math
from pathlib import Path
import numpy as np,pandas as pd
root=Path('/content/m6');spec=importlib.util.spec_from_file_location('score',root/'m6_score.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
rows=[]
for i,site in enumerate(s.NAMES):
 for day in range(35):
  for lead in s.LEADS:
   issue=pd.Timestamp('2023-10-01',tz='UTC')+pd.Timedelta(days=day,hours=12)
   init=issue-pd.Timedelta(hours=6);valid=issue+pd.Timedelta(minutes=lead)
   r=3+i/10+day/100;rows.append((site,issue,init,valid,lead,r+.1,r,r+.05,r+.2,float(i),s.LEADS.index(lead)%3,s.STATIC[site]['terrain'],issue))
d=pd.DataFrame(rows,columns=['site','issue_utc','init_utc','valid_end_utc','lead_min','obs','P','R','V1','dz','bucket','terrain','p_observed_utc'])
s.guard(d,4,'train');m=s.fit(d);x=s.attach(d,m)
assert len(x)==len(d) and all(np.isfinite(x.D2))
threshold={site:float(d.loc[d.site==site,'obs'].quantile(.5)) for site in s.NAMES}
x['strong']=x.obs>=x.site.map(threshold);x['event_id']=np.arange(len(x))
s.CFG['bootstrap_days']=2
assert len(s.aggregate(x,10,4))>=20
s.secondary(x,4)
try:
 d2=d.copy();d2.loc[0,'init_utc']=d2.issue_utc.iloc[0];s.guard(d2,4,'train')
 raise AssertionError('future forecast accepted')
except ValueError:pass
try:
 d2=d.copy();d2.loc[0,'p_observed_utc']=d2.issue_utc.iloc[0]+pd.Timedelta(minutes=10);s.guard(d2,4,'train')
 raise AssertionError('future persistence accepted')
except ValueError:pass
print('SYNTHETIC_OK',len(x),len(m['coefs']),len(m['tau']))
