#!/usr/bin/env python3
"""H2 held-out hurricane METAR reconstruction. Reuses B frozen H08 unchanged."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import io,json,sys,math,importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import timedelta
import numpy as np,pandas as pd,requests,xarray as xr
from scipy.linalg import solve
from scipy.spatial.distance import cdist
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent; B=R.parents[1]/'b_tc'; V=B/'v1'
spec=importlib.util.spec_from_file_location('b_h08',V/'chain_a_v1.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
old=b.old
E=['BERYL','NICHOLAS']; METHODS=['idw','ok','era','era_resok','holland','holland_resok']

def cache_csv(name,make):
 p=R/name
 if p.exists():return pd.read_csv(p)
 df=make();df.to_csv(p,index=False);return df

def fetch_event(name):
 h=old.parse_hurdat();sid,rows=h[name];t=old.dt(old.CANDIDATES[name][1]);start=t-timedelta(hours=12);end=t+timedelta(hours=12)
 track,error=b.build_track(rows,old.bdeck(sid),start,end)
 if error:raise ValueError(error)
 # hourly timestamps nearest the event bounds; no out-of-window hours
 hours=pd.date_range(pd.Timestamp(start).ceil('h'),pd.Timestamp(end).floor('h'),freq='h',tz='UTC')
 if len(hours)<20:raise ValueError('too few hours')
 print(name,'hours',len(hours),flush=True)
 features=old.json.loads(old.fetch(old.GEO.format(state='TX')))['features'];sites=[]
 nodes=list(zip(track.lat.values,track.lon.values))
 for f in features:
  p=f['properties'];lon,lat=f['geometry']['coordinates'][:2]
  if min(old.km(lat,lon,float(a),float(c)) for a,c in nodes)>300:continue
  if not (p.get('archive_begin') or '1900-01-01')[:10]<=t.date().isoformat()<=(p.get('archive_end') or '2100-01-01')[:10]:continue
  sites.append(dict(station=f['id'],lat=lat,lon=lon,name=p.get('sname','')))
 sites=sorted(sites,key=lambda x:x['station']);print(name,'stations',len(sites),flush=True)
 pd.DataFrame(sites).to_csv(R/f'stations_{name.lower()}_h2.csv',index=False)
 land=b.get_land();wind,gust,_=b.predict(track,sites,land)
 tracktime=pd.to_datetime(track.time.values,utc=True)
 windhour=np.array([np.interp(hours.asi8,tracktime.asi8,wind[:,j]) for j in range(len(sites))]).T*old.KNOT
 gusthour=np.array([np.interp(hours.asi8,tracktime.asi8,gust[:,j]) for j in range(len(sites))]).T*old.KNOT
 lat=np.asarray(track.lat.values);lon=np.asarray(track.lon.values);rmw=np.asarray(track.radius_max_wind.values)*1.852
 loclat=np.interp(hours.asi8,tracktime.asi8,lat);loclon=np.interp(hours.asi8,tracktime.asi8,lon);locrmw=np.interp(hours.asi8,tracktime.asi8,rmw)
 coords=[]
 for k,hr in enumerate(hours):
  for j,site in enumerate(sites):
   dist=old.km(site['lat'],site['lon'],loclat[k],loclon[k]);coords.append(dict(event=name,station=site['station'],hour=hr.isoformat(),lat=site['lat'],lon=site['lon'],distance_km=dist,rmw_ratio=dist/locrmw[k],holland=windhour[k,j],holland_gust=gusthour[k,j]))
 grid=pd.DataFrame(coords)
 def get_obs():
  url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py';parts=[];urls=[]
  for i in range(0,len(sites),35):
   params=dict(station=','.join(s['station'] for s in sites[i:i+35]),sts=(start-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),ets=(end+timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),tz='UTC',format='onlycomma',data='sknt,gust,metar',report_type='3,4')
   rr=requests.get(url,params=params,timeout=240);rr.raise_for_status();print('IEM',name,i,len(rr.content),flush=True)
   d=pd.read_csv(io.StringIO(rr.text),comment='#',low_memory=False)
   if not {'station','valid','sknt','gust','metar'}.issubset(d):raise ValueError((rr.url,rr.text[:500]))
   parts.append(d);urls.append(rr.url)
  (R/f'iem_urls_{name.lower()}_h2.json').write_text(json.dumps(urls,indent=2))
  return pd.concat(parts,ignore_index=True)
 obs=cache_csv(f'metar_{name.lower()}_h2.csv.gz',get_obs)
 obs['valid']=pd.to_datetime(obs.valid,utc=True,errors='coerce');obs['hour']=(obs.valid+pd.Timedelta(minutes=30)).dt.floor('h');obs=obs[obs.hour.isin(hours)].copy()
 obs['delta']=(obs.valid-obs.hour).abs();obs=obs.sort_values(['station','hour','delta','valid']).drop_duplicates(['station','hour'])
 for field in ['sknt','gust']:obs[field]=pd.to_numeric(obs[field],errors='coerce')
 # conservative sanity bound, not a physical hurricane maximum; see parameter table
 obs.loc[~obs.sknt.between(0,120),'sknt']=np.nan;obs.loc[~obs.gust.between(0,150),'gust']=np.nan
 obs.loc[obs.gust<obs.sknt,'gust']=np.nan
 obs['obs']=obs.sknt*old.KNOT;obs['obs_gust']=obs.gust*old.KNOT
 def get_era():
  uri='gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
  ds=xr.open_zarr(uri,chunks=None,storage_options={'token':'anon'})[['10m_u_component_of_wind','10m_v_component_of_wind']]
  st=pd.DataFrame(sites);loc={'latitude':xr.DataArray(st.lat.to_numpy(),dims='station'),'longitude':xr.DataArray(st.lon.to_numpy()%360,dims='station')}
  a=ds.sel(time=slice(hours[0].tz_localize(None).isoformat(),hours[-1].tz_localize(None).isoformat())).interp(**loc).load()
  print('ERA',name,a.sizes,flush=True)
  if a.sizes['time']!=len(hours):raise ValueError('ERA time mismatch')
  out=[]
  for k,hr in enumerate(hours):
   for j,s in enumerate(sites):out.append(dict(station=s['station'],hour=hr.isoformat(),era=float(np.hypot(a['10m_u_component_of_wind'].values[k,j],a['10m_v_component_of_wind'].values[k,j]))))
  return pd.DataFrame(out)
 era=cache_csv(f'era_{name.lower()}_h2.csv',get_era)
 for frame in (obs,era):frame.hour=pd.to_datetime(frame.hour,utc=True)
 grid.hour=pd.to_datetime(grid.hour,utc=True)
 grid=grid.merge(obs[['station','hour','obs','obs_gust']],on=['station','hour'],how='left',validate='one_to_one').merge(era,on=['station','hour'],validate='one_to_one')
 grid.to_csv(R/f'grid_{name.lower()}_h2.csv.gz',index=False,compression='gzip');return grid,hours

def predict(g):
 out=[]
 for hour,x in g.groupby('hour',sort=True):
  x=x.reset_index(drop=True);training=np.flatnonzero(x.obs.notna().to_numpy());n=len(training)
  if n<4:continue
  lat=np.radians(x.lat.to_numpy());lon=np.radians(x.lon.to_numpy())
  z=np.sin((lat[:,None]-lat[None,:])/2)**2+np.cos(lat[:,None])*np.cos(lat[None,:])*np.sin((lon[:,None]-lon[None,:])/2)**2
  dist=12742*np.arcsin(np.minimum(1,np.sqrt(z)))
  for i in range(len(x)):
   if not np.isfinite(x.obs.iloc[i]):continue
   ix=training[training!=i]
   if len(ix)<4:continue
   dd=dist[ix,i]; yy=x.obs.to_numpy()[ix];w=1/np.maximum(dd,0.01)**2
   values=dict(idw=np.dot(w,yy)/w.sum(),era=x.era.iloc[i],holland=x.holland.iloc[i]);
   # ordinary kriging with normalized exponential covariance, fixed 75 km, nugget 8%
   C=np.exp(-dist[np.ix_(ix,ix)]/75)+np.eye(len(ix))*.08
   k=np.r_[np.exp(-dd/75),1.];K=np.zeros((len(ix)+1,len(ix)+1));K[:-1,:-1]=C;K[-1,:-1]=1;K[:-1,-1]=1
   wk=solve(K,k,assume_a='sym')[:-1]
   values['ok']=wk@yy
   for base in ('era','holland'):
    resid=yy-x[base].to_numpy()[ix]
    values[base+'_resok']=values[base]+wk@resid
   rec=x.iloc[i][['event','station','hour','obs','obs_gust','distance_km','rmw_ratio','holland_gust']].to_dict();rec.update(values)
   # Gust is independent; missing gust remains missing (no use of sustained winds).
   ig=ix[np.isfinite(x.obs_gust.to_numpy()[ix])]
   if len(ig)>=4:
    d=dist[ig,i]; yg=x.obs_gust.to_numpy()[ig];wg=1/np.maximum(d,.01)**2;rec['gust_idw']=wg@yg/wg.sum()
    Cg=np.exp(-dist[np.ix_(ig,ig)]/75)+np.eye(len(ig))*.08;Kg=np.zeros((len(ig)+1,len(ig)+1));Kg[:-1,:-1]=Cg;Kg[-1,:-1]=1;Kg[:-1,-1]=1
    ww=solve(Kg,np.r_[np.exp(-d/75),1],assume_a='sym')[:-1];rec['gust_ok']=ww@yg
    rec['gust_holland']=x.holland_gust.iloc[i];rec['gust_holland_resok']=rec['gust_holland']+ww@(yg-x.holland_gust.to_numpy()[ig])
   out.append(rec)
 return pd.DataFrame(out)

def score(x,y):
 v=np.asarray(x,dtype=float)-np.asarray(y,dtype=float);v=v[np.isfinite(v)]
 return dict(n=len(v),rmse=float(np.sqrt(np.mean(v*v))),bias=float(v.mean()),mae=float(np.abs(v).mean())) if len(v) else dict(n=0,rmse=None,bias=None,mae=None)

def main():
 grids=[];pred=[];coverage={};missing=[]
 for name in E:
  g,hours=fetch_event(name);grids.append(g)
  p=predict(g);pred.append(p)
  # Valid storm-center local peak window: >=75% event hours and observations within +/- 2h of modeled station peak.
  for sid,s in g.groupby('station'):
   valid=s.obs.notna().sum();peak_t=s.loc[s.holland.idxmax(),'hour'];bracket=bool(((s.hour-peak_t).abs()<=pd.Timedelta(hours=2)).mul(s.obs.notna()).any())
   good=bool(valid>=math.ceil(.75*len(hours)) and bracket)
   coverage[(name,sid)]=good
   if not good:missing.append(dict(event=name,station=sid,valid_hours=int(valid),expected_hours=len(hours),model_peak_utc=peak_t.isoformat(),near_model_peak=bracket))
 print('predictions',sum(len(x) for x in pred),'missing',len(missing),flush=True)
 p=pd.concat(pred,ignore_index=True);p['eligible']=[coverage[(e,s)] for e,s in zip(p.event,p.station)]
 p.to_csv(R/'predictions_h2.csv.gz',index=False,compression='gzip');pd.DataFrame(missing).to_csv(R/'missing_stations_h2.csv',index=False)
 metrics={};peakrows=[]
 for (event,sid),s in p[p.eligible].groupby(['event','station']):
  # Common observed hours for all methods; compare predicted max on observed timestamps.
  row=dict(event=event,station=sid,obs=float(s.obs.max()),obs_gust=float(s.obs_gust.max()),rmw_ratio=float(s.loc[s.obs.idxmax(),'rmw_ratio']))
  for m in METHODS:row[m]=float(s[m].max())
  for m in ('gust_idw','gust_ok','gust_holland','gust_holland_resok'):row[m]=float(s[m].max()) if m in s and s[m].notna().any() else np.nan
  peakrows.append(row)
 peaks=pd.DataFrame(peakrows);peaks.to_csv(R/'peaks_h2.csv',index=False)
 for event in E+['COMBINED']:
  pp=peaks if event=='COMBINED' else peaks[peaks.event==event];hh=p[p.eligible] if event=='COMBINED' else p[(p.eligible)&(p.event==event)]
  by={m:{'peak':score(pp[m],pp.obs),'hourly':score(hh[m],hh.obs)} for m in METHODS}
  by['gust']={m:score(pp[m],pp.obs_gust) for m in ('gust_idw','gust_ok','gust_holland','gust_holland_resok')}
  base=min(('idw','ok'),key=lambda m:by[m]['peak']['rmse']);fusion=min(('era_resok','holland_resok'),key=lambda m:by[m]['peak']['rmse']);gain=1-by[fusion]['peak']['rmse']/by[base]['peak']['rmse'];wins=int(((pp[fusion]-pp.obs).abs()<(pp[base]-pp.obs).abs()).sum())
  groups={}
  for label,mask in {'<1R':pp.rmw_ratio<1,'1–3R':(pp.rmw_ratio>=1)&(pp.rmw_ratio<=3),'>3R':pp.rmw_ratio>3}.items():groups[label]={'n':int(mask.sum()),base:score(pp.loc[mask,base],pp.loc[mask,'obs']),fusion:score(pp.loc[mask,fusion],pp.loc[mask,'obs'])}
  metrics[event]=dict(stations=len(pp),hourly_records=len(hh),methods=by,baseline=base,best_fusion=fusion,gain=gain,station_wins=wins,distance_groups=groups,not_eligible=sum(z['event']==event for z in missing) if event!='COMBINED' else len(missing))
 (R/'metrics_h2.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False))
 plt.figure(figsize=(7,6));colors={'BERYL':'#d45734','NICHOLAS':'#2468a5'}
 for event,group in peaks.groupby('event'):
  plt.scatter(group.obs,group[metrics[event]['best_fusion']],label=f'{event} (n={len(group)})',alpha=.75,c=colors[event])
 mx=max(peaks.obs.max(),max(peaks[m].max() for m in ['era_resok','holland_resok']))*1.1
 plt.plot([0,mx],[0,mx],'k--',lw=1);plt.xlim(0,mx);plt.ylim(0,mx);plt.xlabel('Observed peak 2-min sustained (m/s)');plt.ylabel('LOO fusion predicted event peak (m/s)');plt.legend();plt.title('IEM hourly METAR / NHC HURDAT2-ATCF Holland H08 / ARCO ERA5');plt.tight_layout();plt.savefig(R/'peak_scatter_h2.png',dpi=160)
 print(json.dumps({e:{k:v for k,v in a.items() if k in ['stations','baseline','best_fusion','gain','station_wins','not_eligible']} for e,a in metrics.items()},indent=2),flush=True)
if __name__=='__main__':main()
