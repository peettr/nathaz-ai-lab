import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import json,math
from pathlib import Path
import numpy as np,pandas as pd
from scipy.linalg import solve
from scipy.optimize import minimize_scalar
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
TAGS=['ne_20190128_wide','ne_20210114_wide','ks_20221202','ks_20180306','tx_20191126']
METHODS=['idw','ok75','okfit','era','era_resok75','era_resokfit']
audit=pd.read_csv(R/'station_clean_h3.csv').set_index('station');allowed=set(audit[audit.status=='land'].index)
def score(y,p):
 e=np.asarray(p,dtype=float)-np.asarray(y,dtype=float);e=e[np.isfinite(e)]
 return {'n':int(len(e)),'rmse':float(np.sqrt(np.mean(e*e))) if len(e) else None,'bias':float(e.mean()) if len(e) else None,'mae':float(np.mean(abs(e))) if len(e) else None}
def dist(x):
 lat=np.deg2rad(x.lat.to_numpy());lon=np.deg2rad(x.lon.to_numpy());z=np.sin((lat[:,None]-lat[None,:])/2)**2+np.cos(lat[:,None])*np.cos(lat[None,:])*np.sin((lon[:,None]-lon[None,:])/2)**2
 return 12742*np.arcsin(np.minimum(1,np.sqrt(np.maximum(z,0))))
def fit(d,v):
 if len(v)<5:return 75.,False
 ii,jj=np.triu_indices(len(v),1);h=d[ii,jj];sv=.5*(v[ii]-v[jj])**2;bins=[]
 for lo in np.arange(0,300,25):
  use=(h>=lo)&(h<lo+25)
  if use.sum()>=4:bins.append((float(h[use].mean()),float(sv[use].mean()),float(use.sum())**.5))
 if len(bins)<3:return 75.,False
 c,g,w=np.array(bins).T;sill=max(float(np.var(v)),.01)
 obj=lambda r:np.mean((w*(g-sill*(1.08-np.exp(-c/r))))**2)
 res=minimize_scalar(obj,bounds=(20,300),method='bounded',options={'xatol':2})
 return float(res.x),True
def weight(d,ix,i,r):
 n=len(ix);k=np.empty((n+1,n+1));k[:n,:n]=np.exp(-d[np.ix_(ix,ix)]/r)+np.eye(n)*.08;k[:n,n]=1;k[n,:n]=1;k[n,n]=0
 return solve(k,np.r_[np.exp(-d[ix,i]/r),1.],assume_a='sym')[:n]
def predict(g):
 rows=[];fallback={'okfit':0,'resfit':0}
 for hour,x in g.groupby('hour',sort=True):
  x=x.reset_index(drop=True);d=dist(x);valid=np.flatnonzero(x.obs.notna().to_numpy());y=x.obs.to_numpy();era=x.era.to_numpy();gust=x.obs_gust.to_numpy()
  for i in valid:
   ix=valid[valid!=i]
   if len(ix)<4:continue
   dd=d[ix,i];w=1/np.maximum(dd,.01)**2;w/=w.sum()
   rf,ok=fit(d[np.ix_(ix,ix)],y[ix]);fallback['okfit']+=not ok
   rr,ok=fit(d[np.ix_(ix,ix)],(y-era)[ix]);fallback['resfit']+=not ok
   w75=weight(d,ix,i,75.);wf=weight(d,ix,i,rf);wr=weight(d,ix,i,rr)
   row={'event':x.event.iloc[i],'station':x.station.iloc[i],'hour':hour,'obs':y[i],'obs_gust':gust[i], 'idw':w@y[ix],'ok75':w75@y[ix],'okfit':wf@y[ix],'era':era[i],'era_resok75':era[i]+w75@(y-era)[ix],'era_resokfit':era[i]+wr@(y-era)[ix]}
   ig=ix[np.isfinite(gust[ix])]
   if len(ig)>=4:
    wg=1/np.maximum(d[ig,i],.01)**2;wg/=wg.sum();row['gust_idw']=wg@gust[ig]
    row['gust_ok75']=weight(d,ig,i,75.)@gust[ig];r,_=fit(d[np.ix_(ig,ig)],gust[ig]);row['gust_okfit']=weight(d,ig,i,r)@gust[ig]
   rows.append(row)
 return pd.DataFrame(rows),fallback
allp=[];missing=[];counts={};outages=[]
for tag in TAGS:
 g=pd.read_csv(R/f'grid_{tag}_h3.csv.gz',parse_dates=['hour']);g=g[g.station.isin(allowed)].copy();window=json.loads((R/f'window_{tag}_h3.json').read_text());t=pd.Timestamp(window['peak_utc']);eligible={}
 for sid,s in g.groupby('station'):
  valid=int(s.obs.notna().sum());bracket=bool(((s.hour-t).abs()<=pd.Timedelta(hours=2)).mul(s.obs.notna()).any());good=valid>=math.ceil(.75*25) and bracket
  eligible[sid]=good
  if not good:missing.append(dict(event=tag,station=sid,valid_hours=valid,expected_hours=25,near_regional_peak=bracket))
 p,fall=predict(g);p['eligible']=p.station.map(eligible);allp.append(p);counts[tag]={'candidate_land':g.station.nunique(),'eligible':sum(eligible.values()),'fallback':fall,'ts_cb_reports':window['ts_cb']}
 print(tag,counts[tag],len(p),flush=True)
p=pd.concat(allp,ignore_index=True);p.to_csv(R/'predictions_h3.csv.gz',index=False,compression='gzip');pd.DataFrame(missing).to_csv(R/'missing_h3.csv',index=False)
peaks=[]
for (event,station),x in p[p.eligible].groupby(['event','station']):
 row={'event':event,'station':station,'obs':float(x.obs.max()),'obs_gust':float(x.obs_gust.max())}
 for m in METHODS+['gust_idw','gust_ok75','gust_okfit']:row[m]=float(x[m].max()) if x[m].notna().any() else np.nan
 peaks.append(row)
q=pd.DataFrame(peaks);q.to_csv(R/'peaks_h3.csv',index=False)
def summary(q,h):
 if len(q)<8:return {'stations':len(q),'evaluable':False}
 by={m:{'peak':score(q.obs,q[m]),'hourly':score(h.obs,h[m])} for m in METHODS}
 base=min(['idw','ok75','okfit'],key=lambda m:by[m]['peak']['rmse']);fusion=min(['era_resok75','era_resokfit'],key=lambda m:by[m]['peak']['rmse']);gain=1-by[fusion]['peak']['rmse']/by[base]['peak']['rmse'];wins=int(((q[fusion]-q.obs).abs()<(q[base]-q.obs).abs()).sum());n=len(q)
 verdict='值得' if gain>=.2 and wins/n>=2/3 else ('有条件' if gain>=.1 or wins/n>=2/3 else '插值够用')
 gust={m:score(q.obs_gust,q[m]) for m in ['gust_idw','gust_ok75','gust_okfit']}
 strong=q[q.obs>=15]
 return dict(stations=n,evaluable=True,methods=by,baseline=base,best_fusion=fusion,gain=gain,wins=wins,verdict=verdict,gust_peak=gust,strong15={'n':len(strong),'baseline':score(strong.obs,strong[base]),'fusion':score(strong.obs,strong[fusion])},peak_bias={'baseline':by[base]['peak']['bias'],'fusion':by[fusion]['peak']['bias']})
metrics={tag:summary(q[q.event==tag],p[(p.event==tag)&p.eligible]) for tag in TAGS}
strict=[tag for tag in TAGS if counts[tag]['ts_cb_reports']==0 and metrics[tag]['evaluable']]
metrics['COMBINED_STRICT']=summary(q[q.event.isin(strict)],p[p.event.isin(strict)&p.eligible]);metrics['COMBINED_EXPLORATORY']=summary(q,p[p.eligible])
payload={'metadata':{'events':TAGS,'strict_no_ts_cb':strict,'selection':'NOAA state/UTC day High Wind >=5, Thunderstorm Wind 0; selected plains boxes; METAR TS/CB audit','counts':counts,'missing_count':len(missing),'station_clean':'station_clean_h3.csv','parameters':{'coverage':'assumption >=75% of 25h and report within ±2h regional median peak','QC':'assumption 0–120 kt mean, 0–150 kt gust; gust>=mean','IDW':'assumption power 2','OK':'assumption exponential range 75 km nugget .08; empirical 25km bins to 300km, 20–300km fit; fallback 75km','ERA5':'ARCO hourly 10m u/v interpolated to station then magnitude'}} ,'metrics':metrics}
(R/'metrics_h3.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
fig,ax=plt.subplots(figsize=(7,6))
for event,x in q.groupby('event'):
 m=metrics[event].get('best_fusion')
 if m:ax.scatter(x.obs,x[m],label=event+' n='+str(len(x)),s=15,alpha=.6)
lim=max(q.obs.max(),max(q[m].max() for m in ['era_resok75','era_resokfit']))*1.05;ax.plot([0,lim],[0,lim],'k--');ax.set(xlim=(0,lim),ylim=(0,lim),xlabel='Observed METAR peak sustained wind (m/s)',ylabel='LOO ERA5+residual OK peak (m/s)',title='IEM METAR / NOAA Storm Events / ARCO ERA5');ax.legend(fontsize=7);fig.tight_layout();fig.savefig(R/'peak_scatter_h3.png',dpi=160)
print(json.dumps({k:{z:v.get(z) for z in ['stations','baseline','best_fusion','gain','wins','verdict']} for k,v in metrics.items()},indent=2),flush=True)
