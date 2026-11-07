"""Formal ACE2-ERA5 10-member cold-season point validation against 0.25 deg ERA5 conservative cells."""
import json,sys,os,csv
from pathlib import Path
import numpy as np
from scipy.stats import genextreme,genpareto
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent
N=10
seasons=np.arange(1980,2022)
held=((seasons>=1996)&(seasons<=2009))|((seasons>=2020)&(seasons<=2021))
train=((seasons>=1980)&(seasons<=1994))|((seasons>=2011)&(seasons<=2018))
assert train.sum()==23 and held.sum()==16
assert np.count_nonzero(train&held)==0
order=['KMSP','KDSM','KOMA','KDTW','KPIT','KALB','DFW','AUS']
def slices(t):
 times=t.astype('datetime64[M]').astype(int)
 years=t.astype('datetime64[Y]').astype(int)+1970
 month=times%12+1
 return np.where(month>=10,years,years-1)
ref=[];model=[];rt=[]
for y in seasons:
 f=root/'reference'/f'cold_{y}.npz'
 assert f.exists(),f
 with np.load(f) as a:
  tt=a['time'];speed=np.hypot(a['u'],a['v']);assert np.all(slices(tt)==y)
  rt.append(tt);ref.append(speed)
ref_time=np.concatenate(rt);ref_sp=np.concatenate(ref);assert ref_sp.shape[1]==8
for m in range(1,N+1):
 f=root/'members'/f'm{m:02d}'/'cold_points.npz';assert f.exists(),f
 with np.load(f) as a:
  assert list(a['order'])==order and np.array_equal(a['time'],ref_time),(m,len(a['time']),len(ref_time))
  model.append(np.hypot(a['u'],a['v']))
model_sp=np.stack(model)
assert np.isfinite(model_sp).all() and np.isfinite(ref_sp).all()
ref_season=np.array([ref_sp[slices(ref_time)==y].max(axis=0) for y in seasons])
mod_season=np.array([[z[slices(ref_time)==y].max(axis=0) for y in seasons] for z in model_sp])
assert mod_season.shape==(10,42,8)
np.savez_compressed(root/'seasonal_maxima.npz',seasons=seasons,era=ref_season,ace=mod_season,order=order)
# POT threshold is training ERA5 cold-season 6h p95, reused unchanged on held out.
train_t=np.isin(slices(ref_time),seasons[train])
threshold=np.quantile(ref_sp[train_t],.95,axis=0)
def clusters(x,threshold,hours=72):
 # In a single cold season; elapsed input data are 6h. Gaps >72h form a new cluster.
 ids=np.flatnonzero(x>threshold)
 if len(ids)==0:return np.array([],dtype=float)
 parts=np.split(ids,np.flatnonzero(np.diff(ids)>hours//6)+1)
 return np.array([x[p].max()-threshold for p in parts])
# fixed thresholds, decluster within each cold season, not across summers
ref_pot=[[clusters(ref_sp[slices(ref_time)==y,j],threshold[j]) for j in range(8)] for y in seasons]
mod_pot=[[[clusters(model_sp[m,slices(ref_time)==y,j],threshold[j]) for j in range(8)] for y in seasons] for m in range(10)]
def gev50(a):
 try:
  shape,loc,scale=genextreme.fit(a)
  result=genextreme.ppf(.98,shape,loc=loc,scale=scale)
  return float(result) if np.isfinite(result) and result>0 else np.nan
 except Exception:return np.nan
def pot50(excesses,nseasons,u):
 excess=np.concatenate(excesses)
 if len(excess)<20:return np.nan
 try:
  shape,loc,scale=genpareto.fit(excess,floc=0)
  rate=len(excess)/nseasons
  result=u+genpareto.ppf(1+np.log(.98)/rate,shape,loc=0,scale=scale)
  return float(result) if np.isfinite(result) and result>0 else np.nan
 except Exception:return np.nan
def metrics(mx,pot,p,n_seasons,j):
 vals=mx.ravel();clusters_=[pot[m][s][j] for m in range(len(pot)) for s in p]
 return np.array([float(np.median(vals)),float(np.quantile(vals,.9)),gev50(vals),pot50(clusters_,n_seasons,threshold[j])])
# Bootstrap blocks by forcing year, and resample members; shared forcing dependence preserved.
# Each bootstrap draw uses the *same* sampled year indices for all ensemble members.
rng=np.random.default_rng(20261014);B=600
rows=[];samples={}
for cohort,mask in [('holdout',held),('training',train)]:
 selected=np.flatnonzero(mask);ycount=len(selected)
 for j,site in enumerate(order):
  r=ref_season[selected,j];e=mod_season[:,selected,j]
  eras=np.array([np.median(r),np.quantile(r,.9),gev50(r),pot50([ref_pot[s][j] for s in selected],ycount,threshold[j])])
  ace=metrics(e,mod_pot,selected,10*ycount,j)
  boot=np.empty((B,4))
  for b in range(B):
   ii=rng.integers(0,10,10);ys=rng.choice(selected,size=ycount,replace=True)
   vals=mod_season[ii[:,None],ys[None,:],j].ravel()
   peaks=[mod_pot[m][s][j] for m in ii for s in ys]
   boot[b]=[np.median(vals),np.quantile(vals,.9),gev50(vals),pot50(peaks,10*ycount,threshold[j])]
  lower=np.nanquantile(boot,.05,axis=0);upper=np.nanquantile(boot,.95,axis=0)
  samples[(cohort,site)]=boot
  row={'period':cohort,'site':site,'n_seasons':ycount,'n_members':10,'n_model_seasons':10*ycount,'pot_threshold_mps':threshold[j], 'ace_mean_6h':model_sp[:,np.isin(slices(ref_time),seasons[mask]),j].mean(),'era_mean_6h':ref_sp[np.isin(slices(ref_time),seasons[mask]),j].mean()}
  row['mean_bias_pct']=100*(row['ace_mean_6h']/row['era_mean_6h']-1)
  for k,key in enumerate(['median','p90','gev50','pot50']):
   row['era_'+key]=eras[k];row['ace_'+key]=ace[k];row['ace_'+key+'_lo90']=lower[k];row['ace_'+key+'_hi90']=upper[k]
   row[key+'_bias_pct']=100*(ace[k]/eras[k]-1) if np.isfinite(ace[k]) and np.isfinite(eras[k]) else np.nan
   row[key+'_era_inside90']=bool(np.isfinite(eras[k]) and lower[k]<=eras[k]<=upper[k])
   row[key+'_bootstrap_valid']=int(np.isfinite(boot[:,k]).sum())
  rows.append(row)
  print('SCORED',cohort,site,'bias',row['gev50_bias_pct'],'inCI',row['gev50_era_inside90'],flush=True)
with (root/'formal_metrics.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary={'source':'ACE2-ERA5 pinned HF f25123c52d7faa8f3533816a311cf3353ee83daa; ERA5 WeatherBench2 1959-2023 0.25deg 6h, first-order conservative U/V direct to ACE cells','cold_seasons':[1980,2021],'holdout_start_years':seasons[held].tolist(),'training_start_years':seasons[train].tolist(),'excluded_straddling_seasons':[1995,2010,2019],'ensemble_init_months_1979':list(range(1,11)),'bootstrap_replicates':B,'bootstrap_seed':20261014,'resampling':'members and forcing-year blocks; same sampled years across ensemble members','pot_threshold':'reference training 6h speed empirical p95 per grid; fixed for holdout','pot_decluster_hours':72,'bias_sign':'positive ACE > ERA','rows':rows}
(root/'formal_metrics.json').open('x').write(json.dumps(summary,indent=2,allow_nan=True))
for cohort in ['holdout','training']:
 subset=[r for r in rows if r['period']==cohort]
 fig,axs=plt.subplots(2,2,figsize=(14,9),sharex=True)
 for ax,key,title in zip(axs.flat,['median','p90','gev50','pot50'],['Seasonal max median','Seasonal max p90','GEV 50-year','POT-GPD 50-year']):
  x=np.arange(8);obs=np.array([r['era_'+key] for r in subset]);em=np.array([r['ace_'+key] for r in subset]);lo=np.array([r['ace_'+key+'_lo90'] for r in subset]);hi=np.array([r['ace_'+key+'_hi90'] for r in subset]);ax.errorbar(x+.12,em,yerr=np.array([em-lo,hi-em]),fmt='s',capsize=3,label='ACE2 ensemble (90% bootstrap CI)');ax.plot(x-.12,obs,'ko',label='ERA5 0.25° conservative');ax.set_xticks(x,order,rotation=30);ax.set_ylabel('10-m wind (m/s)');ax.set_title(title);ax.grid(alpha=.2)
 axs[0,0].legend(fontsize=8)
 fig.suptitle(f'ACE2–ERA5 {cohort}: {subset[0]["n_seasons"]} complete cold seasons, 10 distinct 1979 monthly ICs')
 fig.text(.02,.01,'Source: Ai2 ACE2-ERA5 HF checkpoint + AMIP forcing; ECMWF ERA5, Google WeatherBench2 0.25° 6h conservatively regridded on native ACE grid. Cold season is not a classified non-convective event.',fontsize=8)
 fig.tight_layout(rect=[0,.035,1,.95]);fig.savefig(root/f'{cohort}_comparison.png',dpi=130);plt.close(fig)
print('FORMAL_ANALYSIS_DONE',len(rows),len(seasons),B,flush=True)
