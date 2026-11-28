#!/usr/bin/env python3
"""Station-held-out hourly wind-speed LOO benchmark and day-block uncertainty."""
import json,os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
from functools import lru_cache
import numpy as np,pandas as pd
from scipy.spatial.distance import cdist
from scipy.linalg import lu_factor,lu_solve
from sklearn.ensemble import HistGradientBoostingRegressor
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
D=json.loads((R/'selected_dates.json').read_text());st=pd.read_csv(R/'stations.csv')
obs=pd.read_csv(R/'observations_qc2.csv.gz');obs=obs[obs.date.isin(D)].copy()
bg=pd.concat([pd.read_csv(R/f'era_{d}.csv').merge(pd.read_csv(R/f'hrrr_{d}.csv'),on=['station','hour'],validate='one_to_one') for d in D])
obs.hour=pd.to_datetime(obs.hour,utc=True);bg.hour=pd.to_datetime(bg.hour,utc=True)
df=obs.merge(bg,on=['station','hour'],validate='one_to_one').merge(st,on='station',validate='many_to_one')
df=df[df.speed.notna() & ~df.ts_cb.astype(bool)].copy()
for b in ['era','hrrr']:df[b+'_speed']=np.hypot(df[b+'_u'],df[b+'_v'])
df['drct']=pd.to_numeric(df.drct,errors='coerce')
df['obs_u']=-df.speed*np.sin(np.deg2rad(df.drct));df['obs_v']=-df.speed*np.cos(np.deg2rad(df.drct))
# distances use spherical great-circle (km)
lat=np.deg2rad(st.lat.to_numpy());lon=np.deg2rad(st.lon.to_numpy());
a=np.sin((lat[:,None]-lat[None,:])/2)**2+np.cos(lat[:,None])*np.cos(lat[None,:])*np.sin((lon[:,None]-lon[None,:])/2)**2
DIST=6371*2*np.arcsin(np.sqrt(a)); ids={s:i for i,s in enumerate(st.station)}
# Hypothesis choices locked before inspection of scores: IDW p=2; daily exponential covariance;
# range fixed to 75 km as conservative spatial scale; nugget 8% of sample daily variance.
# Same covariance for all methods: no target station observation is used in fit.
METHODS=['idw','ok','era','hrrr','era_resok','hrrr_resok','gbt','gbt_resok']
records=[]; loo_weights={}
for hour,g in df.groupby('hour',sort=True):
 g=g.reset_index(drop=True);n=len(g)
 if n<60:continue
 ii=np.array([ids[s] for s in g.station]); dist=DIST[np.ix_(ii,ii)];off=dist+np.eye(n)*1e12
 near=off.min(axis=1)
 weights=np.where(dist>0,1/np.maximum(dist,0.01)**2,0);np.fill_diagonal(weights,0);weights/=weights.sum(axis=1)[:,None]
 y=g.speed.to_numpy();pred={'idw':weights@y,'era':g.era_speed.to_numpy(),'hrrr':g.hrrr_speed.to_numpy()}
 # Ordinary kriging LOOCV analytic identity: y_i - (K^-1*[y,0])_i / K^-1_ii
 # augmented covariance has constant mean constraint. Nugget controls numerical singularity.
 C=np.exp(-dist/75.0)+np.eye(n)*0.08
 K=np.empty((n+1,n+1));K[:n,:n]=C;K[:n,n]=1;K[n,:n]=1;K[n,n]=0
 lu,piv=lu_factor(K,check_finite=False)
 inv=lu_solve((lu,piv),np.eye(n+1),check_finite=False)
 W=-inv[:n,:n]/np.diag(inv)[:n,None];np.fill_diagonal(W,0)
 loo_weights[hour.isoformat()]=(list(g.station),W)
 def loook(values):
  v=values.astype(float);return W@v
 pred['ok']=loook(y)
 for b in ['era','hrrr']:
  residual=y-pred[b];pred[b+'_resok']=pred[b]+loook(residual)
 # secondary u,v; same weights/covariance, measured directions only
 for key in ['obs_u','obs_v']:
  yy=g[key].to_numpy();valid=np.isfinite(yy)
  if valid.all():
   component=key[-1]; pred['idw_'+component]=weights@yy;pred['ok_'+component]=loook(yy)
   for b in ['era','hrrr']:
    base=g[b+'_'+component].to_numpy();pred[b+'_resok_'+component]=base+loook(yy-base)
 for j in range(n):
  record=dict(station=g.station.iloc[j],date=str(hour.date()),hour=hour.isoformat(),obs=y[j],near_km=near[j],obs_u=g.obs_u.iloc[j],obs_v=g.obs_v.iloc[j])
  for m,v in pred.items():record[m]=v[j]
  for b in ['era','hrrr']:
   record[b+'_u']=g[b+'_u'].iloc[j];record[b+'_v']=g[b+'_v'].iloc[j]
  records.append(record)
print('spatial predictions',len(records),flush=True)
p=pd.DataFrame(records)
# GBT: one fit per station, strictly exclude that station across all dates;
# training examples and prediction times share weather, but target station never enters training.
feat=['era_u','era_v','hrrr_u','hrrr_v','lat','lon','elevation_m','hod_sin','hod_cos']
df['hod_sin']=np.sin(2*np.pi*df.hour.dt.hour/24);df['hod_cos']=np.cos(2*np.pi*df.hour.dt.hour/24)
df['elevation_m']=df.elevation_m.fillna(df.elevation_m.median())
models=[]
for k,s in enumerate(p.station.unique()):
 train=df[df.station!=s];test=df[df.station==s]
 model=HistGradientBoostingRegressor(max_iter=80,max_leaf_nodes=12,learning_rate=.06,l2_regularization=5,random_state=2718)
 model.fit(train[feat],train.speed)
 # predictions for entire station set at these hours; in-sample residuals may be optimistic,
 # but held-out station is absent from model training.
 pred_all=model.predict(df[feat]);sub=df[['station','hour','speed']].copy();sub['ml']=pred_all
 testrows=p[p.station==s]
 predictions=[]
 for _,r in testrows.iterrows():
  gg=sub[sub.hour==pd.Timestamp(r.hour)]; target=gg[gg.station==s]
  if len(target)!=1:raise ValueError('target absent')
  pred=float(target.ml.iloc[0]);others=gg[gg.station!=s]
  names,W=loo_weights[r.hour];target_index=names.index(s)
  residual_by_station=dict(zip(others.station,(others.speed-others.ml).to_numpy()))
  correction=sum(W[target_index,j]*residual_by_station[name] for j,name in enumerate(names) if name!=s)
  predictions.append((r.hour,pred,pred+correction))
 vals=pd.DataFrame(predictions,columns=['hour','gbt','gbt_resok'])
 p.loc[p.station==s,['gbt','gbt_resok']]=vals[['gbt','gbt_resok']].to_numpy()
 if k%20==0:print('ML',k,s,flush=True)
# GBT residual OK uses the same strictly held-out ordinary-kriging weights.
p.to_csv(R/'predictions_r1_clean.csv.gz',index=False,compression='gzip')
def score(g,m):
 error=g[m]-g.obs
 return dict(n=int(len(error)),rmse=float(np.sqrt(np.mean(error**2))),mae=float(np.mean(np.abs(error))),bias=float(np.mean(error)))
metrics={m:score(p,m) for m in METHODS}
station={s:{m:score(g,m) for m in METHODS} for s,g in p.groupby('station')}
peak=p.loc[p.groupby(['station','date']).obs.idxmax()]
peak_scores={m:score(peak,m) for m in METHODS}
rng=np.random.default_rng(2718);days=np.array(sorted(p.date.unique()));boot={m:[] for m in METHODS}
for _ in range(2000):
 picked=rng.choice(days,size=len(days),replace=True);g=pd.concat([p[p.date==d] for d in picked],ignore_index=True)
 for m in METHODS:boot[m].append(score(g,m)['rmse'])
for m in METHODS:metrics[m]['rmse_ci95']=list(np.quantile(boot[m],[.025,.975]))
base=min(('idw','ok'),key=lambda m:metrics[m]['rmse']);best=min([m for m in METHODS if m not in ['idw','ok','era','hrrr']],key=lambda m:metrics[m]['rmse'])
gain=1-metrics[best]['rmse']/metrics[base]['rmse']
station_win=sum(station[s][best]['rmse']<station[s][base]['rmse'] for s in station)
bootgain=[1-np.array(boot[best])[i]/np.array(boot[base])[i] for i in range(len(boot[base]))]
bands={}
for label,mask in {'<25':p.near_km<25,'25–50':(p.near_km>=25)&(p.near_km<=50),'>50':p.near_km>50}.items():
 bands[label]={'n':int(mask.sum()),'baseline_rmse':score(p[mask],base)['rmse'] if mask.any() else None,'best_rmse':score(p[mask],best)['rmse'] if mask.any() else None}
secondary={}
for m in ['idw','ok','era','hrrr','era_resok','hrrr_resok']:
 valid=p[['obs_u','obs_v',m+'_u',m+'_v']].dropna()
 secondary[m]={'u_rmse':float(np.sqrt(np.mean((valid[m+'_u']-valid.obs_u)**2))),'v_rmse':float(np.sqrt(np.mean((valid[m+'_v']-valid.obs_v)**2))),'direction_mae_deg':float(np.mean(np.abs((np.rad2deg(np.arctan2(valid[m+'_u'],valid[m+'_v'])-np.arctan2(valid.obs_u,valid.obs_v))+180)%360-180)))}
result=dict(n_hours=int(p.hour.nunique()),n_observations=int(len(p)),n_stations=int(p.station.nunique()),dates=days.tolist(),methods=metrics,station=station,peak=peak_scores,nearest_distance=bands,secondary=secondary,baseline=base,best=best,gain=gain,gain_ci95=list(np.quantile(bootgain,[.025,.975])),station_wins=station_win,station_total=len(station))
(R/'metrics_r1_clean.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
plt.figure(figsize=(9,4.5));order=sorted(METHODS,key=lambda m:metrics[m]['rmse']);v=[metrics[m]['rmse'] for m in order]
plt.barh(order,v,color=['#477cb3' if m in ('idw','ok') else '#269c82' for m in order]);plt.gca().invert_yaxis();plt.xlabel('Station-held-out 10-m wind speed RMSE (m/s)');plt.title('TX four-city region, 10 non-TS windy days | IEM METAR, ARCO ERA5, AWS HRRR f01');plt.tight_layout();plt.savefig(R/'comparison_r1_clean.png',dpi=150)
print('DONE',base,best,gain,station_win,'/',len(station),flush=True)
