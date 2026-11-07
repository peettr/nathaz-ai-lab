#!/usr/bin/env python3
"""Recompute H2 LOO after land/sea/duplicate segregation; old grids read-only."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import math,json
from pathlib import Path
import numpy as np,pandas as pd
from scipy.linalg import solve
from scipy.optimize import minimize_scalar
R=Path(__file__).resolve().parent
assert not (R/'metrics_clean_h2d.json').exists()
REGULAR=['DELTA','ZETA','IDA','NICHOLAS','IAN','NICOLE','IDALIA','DEBBY','HELENE','MILTON']
EVENTS=REGULAR+['BERYL']
METHODS=['idw','ok75','okfit','era','era_resok75','era_resokfit','holland','holland_resok75','holland_resokfit']
AUDIT=pd.read_csv(R/'station_clean_h2d.csv').set_index('station')
status=AUDIT.status.to_dict()
def norm(s):return s if ':' in s else 'TX:'+s
def score(p,y):
 e=np.asarray(p,float)-np.asarray(y,float);e=e[np.isfinite(e)]
 return dict(n=len(e),rmse=float(np.sqrt(np.mean(e**2))) if len(e) else None,bias=float(np.mean(e)) if len(e) else None,mae=float(np.mean(abs(e))) if len(e) else None)
def distmat(x):
 lat=np.deg2rad(x.lat.to_numpy());lon=np.deg2rad(x.lon.to_numpy());z=np.sin((lat[:,None]-lat[None,:])/2)**2+np.cos(lat[:,None])*np.cos(lat[None,:])*np.sin((lon[:,None]-lon[None,:])/2)**2
 return 12742*np.arcsin(np.minimum(1,np.sqrt(np.maximum(0,z))))
def fit_range(d,v):
 if len(v)<5:return 75.,False
 ii,jj=np.triu_indices(len(v),1);h=d[ii,jj];sv=.5*(v[ii]-v[jj])**2
 centers=[];gam=[];weights=[]
 for low in np.arange(0,300,25):
  use=(h>=low)&(h<low+25)
  if use.sum()>=4:
   centers.append(float(h[use].mean()));gam.append(float(sv[use].mean()));weights.append(float(use.sum())**.5)
 if len(centers)<3:return 75.,False
 centers=np.asarray(centers);gam=np.asarray(gam);weights=np.asarray(weights);sill=max(float(np.var(v)),.01)
 objective=lambda r:np.mean((weights*(gam-sill*(1.08-np.exp(-centers/r))))**2)
 opt=minimize_scalar(objective,bounds=(20,300),method='bounded',options={'xatol':2})
 return float(opt.x),True
def okw(d,ix,i,r):
 n=len(ix); K=np.empty((n+1,n+1));K[:n,:n]=np.exp(-d[np.ix_(ix,ix)]/r)+np.eye(n)*.08;K[:n,n]=1;K[n,:n]=1;K[n,n]=0
 return solve(K,np.r_[np.exp(-d[ix,i]/r),1.],assume_a='sym')[:n]
def predict(g):
 out=[];fits={'speed_fallback':0,'era_fallback':0,'holland_fallback':0,'count':0}
 for hour,x in g.groupby('hour',sort=True):
  x=x.reset_index(drop=True);d=distmat(x)
  valid=np.flatnonzero(x.obs.notna().to_numpy());ys=x.obs.to_numpy();era=x.era.to_numpy();holl=x.holland.to_numpy()
  for i in valid:
   ix=valid[valid!=i]
   if len(ix)<4:continue
   dd=d[ix,i];w=1/np.maximum(dd,.01)**2;w=w/w.sum()
   values={'idw':w@ys[ix],'era':era[i],'holland':holl[i]}
   for base,v in [('speed',ys),('era',ys-era),('holland',ys-holl)]:
    f,ok=fit_range(d[np.ix_(ix,ix)],v[ix]);fits['count']+=1
    if not ok:fits[base+'_fallback']+=1
    w75=okw(d,ix,i,75.);wf=okw(d,ix,i,f)
    if base=='speed':values['ok75']=w75@v[ix];values['okfit']=wf@v[ix]
    else:
     prefix=base+'_resok';values[prefix+'75']=values[base]+w75@v[ix];values[prefix+'fit']=values[base]+wf@v[ix]
   rec=x.loc[i,['event','station','hour','obs','obs_gust','rmw_ratio','holland_gust']].to_dict();rec.update(values)
   ig=ix[np.isfinite(x.obs_gust.to_numpy()[ix])]
   if len(ig)>=4:
    yg=x.obs_gust.to_numpy()[ig];dgi=d[ig,i];wg=1/np.maximum(dgi,.01)**2;wg/=wg.sum()
    rec['gust_idw']=wg@yg
    wg75=okw(d,ig,i,75.);rf,_=fit_range(d[np.ix_(ig,ig)],yg);wgfit=okw(d,ig,i,rf)
    rec['gust_ok75']=wg75@yg;rec['gust_okfit']=wgfit@yg;rec['gust_holland']=x.holland_gust.iloc[i]
    resid=yg-x.holland_gust.to_numpy()[ig]
    rg,_=fit_range(d[np.ix_(ig,ig)],resid);wrf=okw(d,ig,i,rg)
    rec['gust_holland_resok75']=rec['gust_holland']+wg75@resid
    rec['gust_holland_resokfit']=rec['gust_holland']+wrf@resid
   out.append(rec)
 return pd.DataFrame(out),fits
def coverage(g):
 eligible={};missing=[]
 for sid,s in g.groupby('station'):
  valid=int(s.obs.notna().sum());total=s.hour.nunique();pt=s.loc[s.holland.idxmax(),'hour']
  bracket=bool(((s.hour-pt).abs()<=pd.Timedelta(hours=2)).mul(s.obs.notna()).any())
  good=valid>=math.ceil(.75*total) and bracket
  eligible[sid]=good
  if not good:missing.append(dict(event=s.event.iloc[0],station=sid,status=status[norm(sid)],valid_hours=valid,expected_hours=total,model_peak_utc=str(pt),near_model_peak=bracket))
 return eligible,missing
def peaks_for(p):
 rows=[]
 if p.empty:return pd.DataFrame(columns=['event','station','obs']+METHODS)
 for (e,s),x in p[p.eligible].groupby(['event','station']):
  a={'event':e,'station':s,'obs':float(x.obs.max()),'obs_gust':float(x.obs_gust.max()),'rmw_ratio':float(x.loc[x.obs.idxmax(),'rmw_ratio'])}
  for m in METHODS+['gust_idw','gust_ok75','gust_okfit','gust_holland','gust_holland_resok75','gust_holland_resokfit']:
   a[m]=float(x[m].max()) if m in x and x[m].notna().any() else np.nan
  rows.append(a)
 return pd.DataFrame(rows)
def summary(p,pk,missing,events):
 h=p[(p.event.isin(events))&p.eligible];q=pk[pk.event.isin(events)]
 by={m:{'peak':score(q[m],q.obs),'hourly':score(h[m],h.obs)} for m in METHODS}
 by['gust']={m:score(q[m],q.obs_gust) for m in ['gust_idw','gust_ok75','gust_okfit','gust_holland','gust_holland_resok75','gust_holland_resokfit']}
 eligible=len(q)>=8
 base=min(['idw','ok75','okfit'],key=lambda m:by[m]['peak']['rmse'] if by[m]['peak']['rmse'] is not None else np.inf)
 fusion=min(['era_resok75','era_resokfit','holland_resok75','holland_resokfit'],key=lambda m:by[m]['peak']['rmse'] if by[m]['peak']['rmse'] is not None else np.inf)
 gain=1-by[fusion]['peak']['rmse']/by[base]['peak']['rmse'] if eligible and by[base]['peak']['rmse'] else None
 wins=int(((q[fusion]-q.obs).abs()<(q[base]-q.obs).abs()).sum()) if eligible else None
 groups={band:{'n':int(mask.sum()),base:score(q.loc[mask,base],q.loc[mask,'obs']),fusion:score(q.loc[mask,fusion],q.loc[mask,'obs'])} for band,mask in {'<1R':q.rmw_ratio<1,'1-3R':(q.rmw_ratio>=1)&(q.rmw_ratio<=3),'>3R':q.rmw_ratio>3}.items()}
 return dict(stations=len(q),hourly_records=len(h),evaluable=eligible,methods=by,baseline=base,best_fusion=fusion,gain=gain,station_wins=wins,distance_groups=groups,not_eligible=sum(z['event'] in events for z in missing))
allp=[];allpk=[];allmissing=[];fitstats={}
for e in EVENTS:
 grid=R/f'grid_{e.lower()}_expanded.csv.gz'
 if not grid.exists():grid=R/f'grid_{e.lower()}_h2.csv.gz'
 g=pd.read_csv(grid,parse_dates=['hour']);g['station_key']=g.station.map(norm)
 assert set(g.station_key).issubset(status)
 for group in ['land','platform']:
  x=g[g.station_key.map(status)==group].copy()
  if not len(x):continue
  # Never pool water-majority/identified platform sites with land sites.
  cover,missing=coverage(x);allmissing.extend(missing)
  pred,fits=predict(x);fitstats[e+'_'+group]=fits
  if pred.empty:continue
  pred['pool']=group;pred['eligible']=pred.station.map(cover)
  allp.append(pred);pk=peaks_for(pred);pk['pool']=group;allpk.append(pk)
  print(e,group,'sites',x.station.nunique(),'qualified',sum(cover.values()),'predicted_sites',pk.station.nunique(),'rows',len(pred),flush=True)
p=pd.concat(allp,ignore_index=True);pk=pd.concat(allpk,ignore_index=True)
p.to_csv(R/'predictions_clean_h2d.csv.gz',index=False,compression='gzip');pk.to_csv(R/'peaks_clean_h2d.csv',index=False);pd.DataFrame(allmissing).to_csv(R/'missing_clean_h2d.csv',index=False)
m={};sea={}
for e in EVENTS:
 m[e]=summary(p[p.pool=='land'],pk[pk.pool=='land'],[z for z in allmissing if z['status']=='land'],[e])
 sea[e]=summary(p[p.pool=='platform'],pk[pk.pool=='platform'],[z for z in allmissing if z['status']=='platform'],[e])
evaluable=[e for e in REGULAR if m[e]['evaluable']]
m['COMBINED']=summary(p[p.pool=='land'],pk[pk.pool=='land'],[z for z in allmissing if z['status']=='land'],evaluable)
payload={'metadata':{'regular_events':REGULAR,'extra_event':'BERYL','combined_events':evaluable,'combined_excludes_beryl':True,'source_grids':'grid_*_expanded.csv.gz or grid_*_h2.csv.gz; read-only','audit':'station_clean_h2d.csv','scope':'land only primary; water-majority/platform sites independent secondary pool; unknown cover excluded; no station in two pools','windfield':'cached B v1 chain_a_v1 Holland predictions, coefficients unchanged','UTC':True,'mean_and_gust_separate':True,'parameters':{'station_duplicate':'<2 km connected components, highest count valid observed hours across cached events, tie lexical; T89 excluded as suspect co-location with CVB','WorldCover':'ESA WorldCover 2021 v200 modal class 1km circle; class 80 or explicit offshore station name segregated; unknown coverage excluded','fixed_kriging':'assumption exponential range 75km, nugget 0.08, ordinary constraint','fit_kriging':'assumption 25km empirical semivariogram bins to 300km, weighted exponential sill=training variance, nugget 0.08, range 20-300km fitted per target/hour, <3 bins fallback 75km; target entirely excluded','peak':'at same observed hours, at least 75% valid and obs within +-2h of H08 modeled site peak (original H2 assumption)','holland_timing_gust':'B v1 prereg hypotheses: 1min sustained to METAR factor 0.97, gust sea 1.20, land 1.30, not literature values'},'fit_counts':fitstats},'land_metrics':m,'water_platform_metrics':sea,'audit_counts':AUDIT.status.value_counts().to_dict()}
(R/'metrics_clean_h2d.json').open('x').write(json.dumps(payload,indent=2,ensure_ascii=False))
print(json.dumps({k:{'n':v['stations'],'base':v['baseline'],'fusion':v['best_fusion'],'gain':v['gain'],'wins':v['station_wins']} for k,v in m.items()},indent=2),flush=True)
