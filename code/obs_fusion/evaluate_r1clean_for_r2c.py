#!/usr/bin/env python3
"""Independent cleaned-site fixed-75-km analytical LOO check for r2c."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.linalg import solve
R=Path(__file__).resolve().parent
DATES=json.loads((R/'selected_dates.json').read_text())
excluded={'BQX','GVW','T89','BSM','F12','5R3'}
st=pd.read_csv(R/'stations.csv').query('station not in @excluded').copy()
obs=pd.read_csv(R/'observations_qc2.csv.gz')
obs=obs[obs.date.isin(DATES)&obs.speed.notna()&~obs.ts_cb.astype(bool)&obs.station.isin(st.station)]
bg=pd.concat([pd.read_csv(R/f'era_{d}.csv') for d in DATES])
obs.hour=pd.to_datetime(obs.hour,utc=True);bg.hour=pd.to_datetime(bg.hour,utc=True)
df=obs.merge(bg,on=['station','hour'],validate='one_to_one').merge(st,on='station',validate='many_to_one')
df['era']=np.hypot(df.era_u,df.era_v)
ids=list(st.station);lookup={s:i for i,s in enumerate(ids)}
lat=np.deg2rad(st.lat.to_numpy());lon=np.deg2rad(st.lon.to_numpy())
a=np.sin((lat[:,None]-lat[None,:])/2)**2+np.cos(lat[:,None])*np.cos(lat[None,:])*np.sin((lon[:,None]-lon[None,:])/2)**2
D=12742*np.arcsin(np.sqrt(np.maximum(a,0)))
rows=[]
for _,g in df.groupby('hour'):
 if len(g)<3:continue
 idx=np.array([lookup[s] for s in g.station]);dist=D[np.ix_(idx,idx)];n=len(g)
 K=np.empty((n+1,n+1));K[:n,:n]=np.exp(-dist/75)+np.eye(n)*.08
 K[:n,n]=1;K[n,:n]=1;K[n,n]=0
 inv=solve(K,np.eye(n+1),assume_a='sym')
 y=g.speed.to_numpy();res=y-g.era.to_numpy()
 loo_y=y-(inv[:n,:n]@y)/np.diag(inv)[:n]
 loo_res=res-(inv[:n,:n]@res)/np.diag(inv)[:n]
 for s,oy,py,pr in zip(g.station,y,loo_y,g.era.to_numpy()+loo_res):
  rows.append((s,float(py-oy),float(pr-oy)))
p=pd.DataFrame(rows,columns=['station','ok75','era_resok'])
sc=lambda x:float(np.sqrt(np.mean(x*x)))
a=sc(p.ok75);b=sc(p.era_resok)
by={s:{'ok75':sc(g.ok75),'era_resok':sc(g.era_resok),'n':len(g)} for s,g in p.groupby('station')}
out={'n':len(p),'n_stations':len(by),'ok75_rmse':a,'era_resok_rmse':b,'gain':1-b/a,'station_wins':sum(v['era_resok']<v['ok75'] for v in by.values()),'station_total':len(by),'per_station':by,'method':'fixed exponential covariance range 75 km, nugget .08; analytical LOO with augmented unknown mean; same sites filtered before all fits'}
(R/'r1clean_r2c.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print({k:v for k,v in out.items() if k!='per_station'},flush=True)
