#!/usr/bin/env python3
"""Sparse-network station-out benchmark, seeded site splits; no downloads."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.linalg import solve
from scipy.optimize import minimize_scalar
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingRegressor
R=Path(__file__).resolve().parent
DATES=json.loads((R/'selected_dates.json').read_text())
st=pd.read_csv(R/'stations.csv').query("station != 'BSM'").copy()
obs=pd.read_csv(R/'observations_qc2.csv.gz')
obs=obs[obs.date.isin(DATES)&obs.speed.notna()&~obs.ts_cb.astype(bool)&(obs.station!='BSM')]
bg=pd.concat([pd.read_csv(R/f'era_{d}.csv') for d in DATES])
obs.hour=pd.to_datetime(obs.hour,utc=True);bg.hour=pd.to_datetime(bg.hour,utc=True)
df=obs.merge(bg,on=['station','hour'],validate='one_to_one').merge(st,on='station',validate='many_to_one')
df['era']=np.hypot(df.era_u,df.era_v)
df['elevation_m']=df.elevation_m.fillna(df.elevation_m.median())
df['hod_sin']=np.sin(2*np.pi*df.hour.dt.hour/24);df['hod_cos']=np.cos(2*np.pi*df.hour.dt.hour/24)
land=pd.read_csv(R/'landcover_r1_addendum.csv')[['station','group']]
df=df.merge(land,on='station',how='left',validate='many_to_one')
FEATURES=['era_u','era_v','lat','lon','elevation_m','hod_sin','hod_cos']
METHODS=['idw','ok75','okfit','era','era_resok','gbt','gbt_resok']
coords=st.set_index('station')[['lat','lon']]; ids=list(coords.index); lookup={s:i for i,s in enumerate(ids)}
lat=np.deg2rad(coords.lat.to_numpy());lon=np.deg2rad(coords.lon.to_numpy())
a=np.sin((lat[:,None]-lat[None,:])/2)**2+np.cos(lat[:,None])*np.cos(lat[None,:])*np.sin((lon[:,None]-lon[None,:])/2)**2
D=12742*np.arcsin(np.sqrt(np.maximum(a,0)))
# Empirical semivariogram: 25-km bins, to 300 km; one-parameter weighted fit
# gamma(h)=sill*(1.08-exp(-h/r)); sill from training-hour sample variance.
def fit_range(dist,values):
 ii,jj=np.triu_indices(len(values),1); h=dist[ii,jj]; sv=.5*(values[ii]-values[jj])**2
 centers=[];gam=[];weights=[]
 for l in np.arange(0,300,25):
  sel=(h>=l)&(h<l+25)
  if sel.sum()>=4: centers.append(float(np.mean(h[sel])));gam.append(float(np.mean(sv[sel])));weights.append(float(sel.sum()))
 if len(centers)<3:return 75.,False
 centers=np.array(centers);gam=np.array(gam);weights=np.sqrt(np.array(weights));sill=max(float(np.var(values)),.01)
 objective=lambda r: np.mean((weights*(gam-sill*(1.08-np.exp(-centers/r))))**2)
 result=minimize_scalar(objective,bounds=(20,300),method='bounded',options={'xatol':2})
 return float(result.x),True

def okw(dtt,dti,y,range_km):
 n=len(y); K=np.empty((n+1,n+1));K[:n,:n]=np.exp(-dtt/range_km)+np.eye(n)*.08
 K[:n,n]=1;K[n,:n]=1;K[n,n]=0
 rhs=np.vstack([np.exp(-dti.T/range_km),np.ones((1,dti.shape[0]))])
 return solve(K,rhs,assume_a='sym')[:n].T

def model():return HistGradientBoostingRegressor(max_iter=80,max_leaf_nodes=12,learning_rate=.06,l2_regularization=5,random_state=2718)
# precompute per-hour frame, without duplicating source files
hours=[g for _,g in df.groupby('hour',sort=True)]
all_ids=sorted(set(df.station));rng=np.random.default_rng(314159)
rows=[];split_stats=[];fit_fallback=0;fitted_ranges=[]
for frac in (.50,.25,.10):
 for rep in range(20):
  shuffled=rng.permutation(all_ids);train_sites=set(shuffled[:round(frac*len(all_ids))]);test_sites=set(all_ids)-train_sites
  train=df[df.station.isin(train_sites)];test=df[df.station.isin(test_sites)]
  # Two site-disjoint cross fits: each input station residual is strictly out-of-fit.
  sites=np.array(sorted(train_sites));rng_cf=np.random.default_rng(2026+rep+int(frac*1000));sites=rng_cf.permutation(sites)
  folds=[set(x) for x in np.array_split(sites,2)]
  cross={}
  for held in folds:
   source=train[~train.station.isin(held)];target=train[train.station.isin(held)]
   m=model();m.fit(source[FEATURES],source.speed)
   cross.update(zip(target.index,m.predict(target[FEATURES])))
  full=model();full.fit(train[FEATURES],train.speed)
  testpred=dict(zip(test.index,full.predict(test[FEATURES])))
  nrows=0;nearest=[]
  for g in hours:
   tr=g[g.station.isin(train_sites)];te=g[g.station.isin(test_sites)]
   if len(tr)<5 or len(te)==0:continue
   tindex=np.array([lookup[s] for s in tr.station]);eindex=np.array([lookup[s] for s in te.station]);dtt=D[np.ix_(tindex,tindex)];dti=D[np.ix_(eindex,tindex)]
   y=tr.speed.to_numpy();yb=tr.era.to_numpy();b=te.era.to_numpy()
   w=1/np.maximum(dti,.01)**2;w/=w.sum(axis=1)[:,None]
   rang,success=fit_range(dtt,y)
   if not success:fit_fallback+=1
   fitted_ranges.append(rang)
   w75=okw(dtt,dti,y,75.);wf=okw(dtt,dti,y,rang)
   cp=np.array([cross[i] for i in tr.index]);pml=np.array([testpred[i] for i in te.index])
   predictions=np.column_stack([w@y,w75@y,wf@y,b,b+w75@(y-yb),pml,pml+w75@(y-cp)])
   err=predictions-te.speed.to_numpy()[:,None];distance=dti.min(axis=1)
   for j,(_,r) in enumerate(te.iterrows()):
    record={'fraction':frac,'repeat':rep,'station':r.station,'date':r.date,'hour':str(r.hour),'obs':float(r.speed),'near_km':float(distance[j]),'group':r.group}
    record.update({m:float(err[j,k]) for k,m in enumerate(METHODS)})
    rows.append(record)
   nearest.extend(distance.tolist());nrows+=len(te)
  split_stats.append({'fraction':frac,'repeat':rep,'n':nrows,'input_stations':len(train_sites),'test_stations':len(test_sites),'mean_nearest_km':float(np.mean(nearest))})
  print('split',frac,rep,'rows',nrows,'km',round(np.mean(nearest),1),flush=True)
p=pd.DataFrame(rows)
def scores(g):
 return {m:{'n':int(len(g)),'rmse':float(np.sqrt(np.mean(g[m]**2))),'mae':float(np.mean(abs(g[m]))),'bias':float(np.mean(g[m]))} for m in METHODS}
out={'seed':314159,'fractions':{},'split_stats':split_stats,'fit_range_fallback_hours':fit_fallback,'fit_range_median_km':float(np.median(fitted_ranges)), 'n_unique_stations':len(all_ids),'excluded_station':'BSM','dates':DATES,'methods':METHODS,'parameter_provenance':{'input_splits':'assumption: uniform seeded random sites, round(fraction*N), 20 independent draws per fraction; no geographic stratification','ok75':'assumption inherited r1: exp covariance range 75 km, nugget .08 of sill','okfit':'assumption: hourly station-only speed semivariogram 25-km bins, exponential covariance range fit 20-300 km; fixed nugget .08; fallback 75 km with <3 bins','gbt':'assumption inherited r1 80 iterations, 12 leaves, learning rate .06, L2=5; ERA5 u/v, elevation, lat/lon, UTC hour sin/cos','gbt_resok':'input-site residuals from 2 site-disjoint cross-fit models; full GBT trained only on input sites predicts test sites; fixed 75-km OK residual correction','landcover':'reused r1 addendum ESA WorldCover 2021 v200, 1 km modal class; 50 built-up else nonbuilt'}}
for frac,g in p.groupby('fraction',sort=False):
 base_scores=scores(g);base=min(['idw','ok75','okfit'],key=lambda x:base_scores[x]['rmse']);best=min(['era_resok','gbt','gbt_resok'],key=lambda x:base_scores[x]['rmse'])
 station={s:scores(z) for s,z in g.groupby('station')}
 # At each site/date/repetition select actual observed-peak hour; not predicted maximum.
 peak=g.loc[g.groupby(['repeat','station','date']).obs.idxmax()]
 groups={name:{'n_station':int(z.station.nunique()),'n_samples':int(len(z)),'methods':scores(z)} for name,z in g.groupby('group',dropna=False)}
 station_wins=sum(z[best]['rmse']<z[base]['rmse'] for z in station.values())
 out['fractions'][str(frac)]={'n':int(len(g)),'mean_nearest_km':float(g.near_km.mean()),'methods':base_scores,'best_interpolation':base,'best_fusion':best,'gain':1-base_scores[best]['rmse']/base_scores[base]['rmse'],'station_wins':station_wins,'station_total':len(station),'station':station,'peak_at_observed_hour':scores(peak),'peak_n':len(peak),'landcover':groups}
 (R/'metrics_r2.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print('saved metrics_r2.json',flush=True)
# plot split-wise pooled RMSE against the actual mean distance
fig,ax=plt.subplots(figsize=(8,5))
for m,label in [('idw','IDW'),('ok75','OK 75 km'),('okfit','OK hourly fitted'),('era','ERA5 direct'),('era_resok','ERA5+residual OK'),('gbt','GBT ERA5'),('gbt_resok','GBT+cross-fit residual OK')]:
 x=[out['fractions'][str(f)]['mean_nearest_km'] for f in (.5,.25,.1)]
 y=[out['fractions'][str(f)]['methods'][m]['rmse'] for f in (.5,.25,.1)]
 ax.plot(x,y,marker='o',label=label)
ax.set_xlabel('Mean held-out station distance to nearest input station (km)');ax.set_ylabel('Station-hour RMSE (m/s)')
ax.set_title('10 windy UTC days, 20 site splits per density | IEM METAR, ARCO ERA5')
ax.legend(fontsize=8);ax.grid(alpha=.25);fig.tight_layout();fig.savefig(R/'rmse_distance_r2.png',dpi=160)
print('saved rmse_distance_r2.png',flush=True)
