"""Single-member descriptive preview; no ensemble interval or acceptance gate."""
from pathlib import Path
import numpy as np,csv
from scipy.stats import genextreme,genpareto
r=Path(__file__).resolve().parent
sites=['KMSP','KDSM','KOMA','KDTW','KPIT','KALB','DFW','AUS']
years=np.arange(1980,2022)
season=lambda t:np.where((t.astype('datetime64[M]').astype(int)%12+1)>=10,t.astype('datetime64[Y]').astype(int)+1970,t.astype('datetime64[Y]').astype(int)+1969)
obs=[];times=[]
for y in years:
 with np.load(r/'reference'/f'cold_{y}.npz') as d:
  t=d['time'];assert np.all(season(t)==y);times.append(t);obs.append(np.hypot(d['u'],d['v']))
times=np.concatenate(times);obs=np.concatenate(obs)
with np.load(r/'members/m01/cold_points.npz') as d:
 assert list(d['order'])==sites;assert np.array_equal(d['time'],times)
 model=np.hypot(d['u'],d['v'])
assert np.all(np.isfinite(obs)) and np.all(np.isfinite(model))
sy=season(times)
training=((years>=1980)&(years<=1994))|((years>=2011)&(years<=2018))
holdout=((years>=1996)&(years<=2009))|((years>=2020)&(years<=2021))
assert training.sum()==23 and holdout.sum()==16
threshold=np.quantile(obs[np.isin(sy,years[training])],.95,axis=0)
def extremes(x,j,selection):
 maxima=[];excess=[]
 for y in selection:
  v=x[sy==y,j];maxima.append(v.max());inds=np.flatnonzero(v>threshold[j]);
  if len(inds):
   for c in np.split(inds,np.flatnonzero(np.diff(inds)>12)+1):excess.append(v[c].max()-threshold[j])
 return np.asarray(maxima),np.asarray(excess)
def gev50(mx):
 c,loc,scale=genextreme.fit(mx);return float(genextreme.ppf(.98,c,loc=loc,scale=scale))
def pot50(exc,n,u):
 if len(exc)<20:return float('nan')
 c,loc,scale=genpareto.fit(exc,floc=0);return float(u+genpareto.ppf(1+np.log(.98)/(len(exc)/n),c,loc=0,scale=scale))
rows=[]
for cohort,mask in [('holdout',holdout),('training',training)]:
 selected=years[mask]
 for j,site in enumerate(sites):
  om,oe=extremes(obs,j,selected);mm,me=extremes(model,j,selected)
  ot=obs[np.isin(sy,selected),j];mt=model[np.isin(sy,selected),j]
  row=dict(cohort=cohort,site=site,n_members=1,n_seasons=len(selected),n_era_pot_clusters=len(oe),n_ace_pot_clusters=len(me),threshold_mps=threshold[j])
  pairs={'mean_6h':(ot.mean(),mt.mean()),'season_median':(np.median(om),np.median(mm)),'season_p90':(np.quantile(om,.9),np.quantile(mm,.9)),'gev50':(gev50(om),gev50(mm)),'pot50':(pot50(oe,len(selected),threshold[j]),pot50(me,len(selected),threshold[j]))}
  for k,(o,m) in pairs.items():row.update({'era_'+k:float(o),'ace_'+k:float(m),k+'_bias_pct':float(100*(m/o-1))})
  rows.append(row)
with (r/'single_member_preview.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
for row in rows:print(row['cohort'],row['site'], 'median',round(row['season_median_bias_pct'],2),'p90',round(row['season_p90_bias_pct'],2),'GEV50',round(row['gev50_bias_pct'],2),'POT50',round(row['pot50_bias_pct'],2),'mean',round(row['mean_6h_bias_pct'],2))
print('DONE',len(rows))
