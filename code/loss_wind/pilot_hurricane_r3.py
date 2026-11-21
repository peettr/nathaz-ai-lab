#!/usr/bin/env python3
"""Read H2 grids/code without modifying H; recompute H08 at DAT locations, fixed-75km residual OK.
Outputs new-only r3 artifacts. NWS DAT windspeed is never an input to wind reconstruction.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import sys,csv,gzip,json,math,collections,datetime as dt
from pathlib import Path
import numpy as np,pandas as pd,requests
from scipy.linalg import solve
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent; H=P.parent/'obs_fusion/h2'
sys.path.insert(0,str(H)); import chain_a_v1 as b
old=b.old
DAT='https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer/0/query'
CASES={'IDA':('2021-08-28','2021-09-02',(28,34),(-93,-88)), 'IDALIA':('2023-08-28','2023-09-02',(24,35),(-88,-80)), 'HELENE':('2024-09-25','2024-09-30',(24,37),(-88,-75))}
FIELDS=['objectid','stormdate','damage_txt','dod_txt','dod','damage','windspeed','comments','lat','lon','efscale','event_id','surveytype']
def km(a,b,c,d):
 a=np.radians(a);b=np.radians(b);c=np.radians(c);d=np.radians(d)
 q=np.sin((a-c)/2)**2+np.cos(a)*np.cos(c)*np.sin((b-d)/2)**2
 return 12742*np.arcsin(np.minimum(1,np.sqrt(np.maximum(0,q))))
def utc(ms):return dt.datetime.fromtimestamp(ms/1000,dt.timezone.utc)
def query_details(points):
 ids=[p['objectid'] for p in points];out={}
 for i in range(0,len(ids),100):
  r=requests.get(DAT,params={'f':'json','objectIds':','.join(map(str,ids[i:i+100])),'outFields':','.join(FIELDS),'returnGeometry':'false'},timeout=90);r.raise_for_status();j=r.json()
  if 'error' in j:raise RuntimeError(j['error'])
  for p in j['features']:out[p['attributes']['objectid']]=p['attributes']
 assert len(out)==len(ids),(len(out),len(ids));return out

def ok_predict(target_lat,target_lon,slat,slon,resid,limit=40):
 dist=km(slat,slon,target_lat,target_lon);ix=np.argsort(dist)[:limit];n=len(ix)
 if n<4:return np.nan,float(np.min(dist)) if n else np.nan,n
 d=km(slat[ix,None],slon[ix,None],slat[None,ix],slon[None,ix]);K=np.empty((n+1,n+1))
 K[:n,:n]=np.exp(-d/75)+np.eye(n)*.08;K[n,:n]=K[:n,n]=1;K[n,n]=0
 v=np.r_[np.exp(-dist[ix]/75),1]
 try:w=solve(K,v,assume_a='sym')[:n];return float(w@resid[ix]),float(dist[ix[0]]),n
 except Exception:return np.nan,float(dist[ix[0]]),n

def main():
 for n in ['dat_hurricanes_r3.json','dat_hurricane_points_r3.csv','summary_r3.json','fr12_trend_r3.png']:
  if (P/n).exists():raise FileExistsError(P/n)
 census=json.loads((P/'dat_census_2019_2024_r2.json').read_text())['features'];land=b.get_land();tracks=old.parse_hurdat();allpts=[]
 selections={};all_details={}
 for event,(start,end,latbox,lonbox) in CASES.items():
  pts=[p for p in census if p['efscale']=='Tropical' and p.get('stormdate') and p.get('lat') and start<=utc(p['stormdate']).strftime('%Y-%m-%d')<end and latbox[0]<=p['lat']<=latbox[1] and lonbox[0]<=p['lon']<=lonbox[1]]
  assert len(pts)==len({p['objectid'] for p in pts});selections[event]=pts
  all_details.update(query_details(pts))
 for event,points in selections.items():
  if not points:continue
  landfall=old.dt(old.CANDIDATES[event][1]);start=landfall-dt.timedelta(hours=12);end=landfall+dt.timedelta(hours=12)
  sid,raw=tracks[event];track,err=b.build_track(raw,old.bdeck(sid),start,end)
  if err:raise RuntimeError(event+': '+err)
  grid=pd.read_csv(H/f'grid_{event.lower()}_expanded.csv.gz',parse_dates=['hour'])
  status={r['station']:r['status'] for r in csv.DictReader((H/'station_clean_h2d.csv').open())}
  grid=grid[grid.station.map(status).eq('land')].copy()
  sites=[{'lat':float(p['lat']),'lon':float(p['lon']),'id':p['objectid']} for p in points]
  wind,gust,_=b.predict(track,sites,land)
  times=pd.to_datetime(track.time.values,utc=True).astype('int64').to_numpy()
  hours=pd.date_range(start.ceil('h') if hasattr(start,'ceil') else pd.Timestamp(start).ceil('h'),pd.Timestamp(end).floor('h'),freq='h',tz='UTC')
  # Exact same linear 15-min -> hour interpolation as H2 run_h2_expanded.py lines 51-59.
  w0=np.array([np.interp(hours.asi8,times,wind[:,j]) for j in range(len(sites))]).T*old.KNOT
  g0=np.array([np.interp(hours.asi8,times,gust[:,j]) for j in range(len(sites))]).T*old.KNOT
  center_lat=np.interp(hours.asi8,times,track.lat.values);center_lon=np.interp(hours.asi8,times,track.lon.values)
  rmw=np.interp(hours.asi8,times,track.radius_max_wind.values)*1.852
  # model predictions are computed on entire fixed landfall +/-12h P2 window;
  # DAT timestamp itself may be day-only or outside the window and is not used to tune wind.
  reconstructed=[[] for _ in points]
  for k,h in enumerate(hours):
   stations=grid[grid.hour.eq(h) & grid.obs.notna()].copy()
   if len(stations)<4:continue
   slat=stations.lat.to_numpy(float);slon=stations.lon.to_numpy(float)
   rs=stations.obs.to_numpy(float)-stations.holland.to_numpy(float)
   guststations=stations[stations.obs_gust.notna()].copy()
   for j,p in enumerate(points):
    rr,near,n=ok_predict(p['lat'],p['lon'],slat,slon,rs)
    if not np.isfinite(rr):continue
    pred=max(0,float(w0[k,j]+rr))
    gg=np.nan;ng=np.nan
    if len(guststations)>=4:
     gg_res,ng,_=ok_predict(p['lat'],p['lon'],guststations.lat.to_numpy(float),guststations.lon.to_numpy(float),guststations.obs_gust.to_numpy(float)-guststations.holland_gust.to_numpy(float))
     if np.isfinite(gg_res):gg=max(0,float(g0[k,j]+gg_res))
    ratio=float(km(p['lat'],p['lon'],center_lat[k],center_lon[k])/rmw[k]) if rmw[k]>0 else np.nan
    reconstructed[j].append((pred,gg,str(h),near,ng,ratio,n))
  metrics=json.loads((H/'metrics_clean_h2d.json').read_text())['land_metrics'][event]['methods']
  obs_cache=[]
  for file in (P/'iem_month_cache_r2').glob('*.csv'):
   if not file.name.startswith(('LA_','MS_','FL_','GA_','NC_','SC_','TN_')):continue
   if file.name[3:10] not in {start.strftime('%Y-%m'),end.strftime('%Y-%m')}:continue
   state=file.name.split('_')[0]
   coords={r['station']:r for r in csv.DictReader((H/f'stations_{event.lower()}_expanded.csv').open()) if r['state']==state}
   if not coords:continue
   with file.open() as f:
    for q in csv.DictReader(f):
     if q['station'] not in coords:continue
     try:
      ot=dt.datetime.fromisoformat(q['valid'].replace('Z','+00:00'))
      if ot.tzinfo is None:ot=ot.replace(tzinfo=dt.timezone.utc)
      v=float(q['gust'])
     except (ValueError,TypeError):continue
     if not v>0:continue
     s=coords[q['station']];obs_cache.append((float(s['lat']),float(s['lon']),state+':'+q['station'],v,ot))
  for j,p in enumerate(points):
   d=all_details[p['objectid']];series=reconstructed[j]
   # closest station observed gust within DAT timestamp +/-12h, using cached IEM month files.
   nearby=[];t=utc(p['stormdate'])
   for slat,slon,station,v,ot in obs_cache:
    if abs((ot-t).total_seconds())>12*3600:continue
    distance=float(km(p['lat'],p['lon'],slat,slon))
    if distance<=10:nearby.append((distance,station,v,ot.isoformat()))
   near_obs=min((x[0] for x in nearby),default=None)
   obs=max((x for x in nearby if x[0]==near_obs),key=lambda x:x[2],default=None)
   wp=max(series,key=lambda x:x[0]) if series else None
   gp=max((x for x in series if np.isfinite(x[1])),key=lambda x:x[1],default=None)
   speed=None
   try:speed=float(d['windspeed']);speed=speed if speed>0 else None
   except (ValueError,TypeError):pass
   row={'event':event,'objectid':p['objectid'],'dat_utc':t.isoformat(),'lat':p['lat'],'lon':p['lon'],'damage_type':d.get('damage_txt'),'dod':d.get('dod'),'dod_txt':d.get('dod_txt'),'damage':d.get('damage'),'comment':d.get('comments'),'dat_windspeed_damage_inferred_raw':d.get('windspeed'),'dat_windspeed_numeric_assume_mph':speed,
     'model_sustained_mps':round(wp[0],3) if wp else None,'model_sustained_peak_utc':wp[2] if wp else None,'model_gust_mps':round(gp[1],3) if gp else None,'model_gust_peak_utc':gp[2] if gp else None,
     'method':'H2_CLIMADA_H08_Holland+residual_OK_fixed75_at_DAT','background':'H08_Holland_track_NHC_HURDAT2_ATCF; H2 cached station grid residuals','peak_definition':'P2_landfall_plusminus12h','gust_averaging':'H2 5s gust assumption; METAR gust comparison','sustained_averaging':'H2 METAR approximately 2min','nearest_input_station_km':round(wp[3],3) if wp else None,'gust_nearest_input_km':round(gp[4],3) if gp else None,'rmw_ratio_at_sustained_peak':round(wp[5],3) if wp else None,'rmw_bin':('<1' if wp[5]<1 else '1-3' if wp[5]<=3 else '>3') if wp and np.isfinite(wp[5]) else 'unknown','input_count_at_sustained_peak':wp[6] if wp else None,
     'h2_event_sustained_rmse_mps':round(metrics['holland_resok75']['peak']['rmse'],3),'h2_event_sustained_bias_mps':round(metrics['holland_resok75']['peak']['bias'],3),'h2_event_gust_rmse_mps':round(metrics['gust']['gust_holland_resok75']['rmse'],3),'h2_event_gust_bias_mps':round(metrics['gust']['gust_holland_resok75']['bias'],3),
     'near_station_10km':obs[1] if obs else None,'near_station_km':round(obs[0],3) if obs else None,'near_station_peak_gust_kt':obs[2] if obs else None,'near_station_peak_utc':obs[3] if obs else None,'near_station_qc':'IEM as-is; not colocated/not event attribution QC','dat_minus_model_gust_mph_assumed':round(speed-(gp[1]*2.2369362921),2) if speed is not None and gp else None,
     'wind_origin':'reconstructed_not_measured','independent_strict':False,'storm_attribution':'date_and_geography_only_unverified'}
   allpts.append(row)
  print(event,'DAT',len(points),'model',sum(bool(v) for v in reconstructed),'FR12',sum('FR12' in (all_details[x['objectid']].get('damage_txt') or '') for x in points),flush=True)
 (P/'dat_hurricanes_r3.json').write_text(json.dumps({'source':DAT,'cases':{e:[p['objectid'] for p in x] for e,x in selections.items()},'details':{str(r['objectid']):r for r in allpts}},ensure_ascii=False,indent=2))
 with (P/'dat_hurricane_points_r3.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(allpts[0]));writer.writeheader();writer.writerows(allpts)
 fig,axes=plt.subplots(1,2,figsize=(12,4.5));fr=[r for r in allpts if 'FR12' in (r['damage_type'] or '') and r['model_gust_mps'] is not None]
 for r in fr:
  try:dod=float(r['dod'])
  except (ValueError,TypeError):continue
  axes[0].scatter(r['model_gust_mps'],dod,c={'IDA':'#1f77b4','IDALIA':'#ff7f0e','HELENE':'#2ca02c'}[r['event']],alpha=.5,s=16)
 axes[0].set(xlabel='Reconstructed peak gust (m/s, not measured)',ylabel='DAT FR12 DOD numeric code',title='FR12 damage vs reconstructed wind')
 bins=[0,15,20,25,30,35,40,50,70,200];data=collections.defaultdict(list)
 for r in fr:
  try:dod=float(r['dod']);x=float(r['model_gust_mps'])
  except (ValueError,TypeError):continue
  for a,bn in zip(bins,bins[1:]):
   if a<=x<bn:data[f'{a}-{bn}'].append(dod);break
 xx=[];yy=[];nn=[]
 for name,ds in data.items():
  a,bn=map(float,name.split('-'));xx.append((a+bn)/2);yy.append(float(np.median(ds)));nn.append(len(ds))
 axes[1].scatter(xx,yy,s=[max(12,6*n) for n in nn],color='#333333')
 for x,y,n in zip(xx,yy,nn):axes[1].annotate(str(n),(x,y),xytext=(3,3),textcoords='offset points',fontsize=8)
 axes[1].set(xlabel='Reconstructed peak gust (m/s)',ylabel='Median FR12 DOD (number = bin count)',title='Exploratory bins (no zero-damage controls)')
 fig.text(.5,.005,'Sources: NWS DAT point layer; H2 NHC/ATCF + IEM station residuals. H2 reconstruction may underestimate peaks; not a measured damage-point wind.',ha='center',fontsize=8)
 fig.tight_layout(rect=(0,.035,1,1));fig.savefig(P/'fr12_trend_r3.png',dpi=170);plt.close(fig)
 summary={'cases':{},'fr12_bins':dict(data),'units_warning':'DAT windspeed mph assumed; field dictionary has no units; only descriptive','station_residual':'H2 cleaned land stations, fixed 75-km exponential ordinary kriging, max 40 nearest stations'}
 for e in CASES:
  a=[r for r in allpts if r['event']==e];f=[r for r in a if 'FR12' in (r['damage_type'] or '')];d=[r for r in f if r['dod'] is not None and r['model_gust_mps'] is not None]
  valid=[(float(r['model_gust_mps']),float(r['dod'])) for r in d if str(r['dod']).replace('.','',1).isdigit()]
  delta=[r['dat_minus_model_gust_mph_assumed'] for r in a if r['dat_minus_model_gust_mph_assumed'] is not None]
  summary['cases'][e]={'points':len(a),'model_points':sum(r['model_gust_mps'] is not None for r in a),'fr12':len(f),'fr12_numeric_dod_model':len(valid),'near10_gust':sum(r['near_station_10km'] is not None for r in a),'dat_wind_numeric_comparable':len(delta),'dat_minus_model_gust_mph_median':float(np.median(delta)) if delta else None,'fr12_spearman':float(spearmanr(*zip(*valid)).statistic) if len(valid)>=3 and len(set(y for x,y in valid))>1 else None,'fr12_dod_distribution':dict(collections.Counter(str(r['dod']) for r in f))}
 (P/'summary_r3.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary['cases'],indent=2))
if __name__=='__main__':main()
