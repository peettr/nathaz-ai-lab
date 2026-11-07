"""R5: read-only H2 Holland+residual P2 at CRASAR buildings; no DAT wind inputs."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import json,csv,datetime as dt,sys,math
from pathlib import Path
import numpy as np,pandas as pd
P=Path(__file__).resolve().parent;H=P.parent/'obs_fusion/h2'
sys.path.insert(0,str(P))
from pilot_hurricane_r3 import b,old,km,ok_predict
areas=['ian_harlem','idalia_jena']
rows=[r for r in json.loads((P/'r5_water_screen.json').read_text()) if r['area'] in areas]
assert len(rows)==len({r['building_id'] for r in rows}),'Duplicate building IDs: resolve before model'
for event in ['IAN','IDALIA']:
 a=[r for r in rows if r['event']==event]
 landfall=old.dt(old.CANDIDATES[event][1]);start=landfall-dt.timedelta(hours=12);end=landfall+dt.timedelta(hours=12)
 sid,raw=old.parse_hurdat()[event];track,err=b.build_track(raw,old.bdeck(sid),start,end)
 if err:raise RuntimeError(err)
 print(event,'predict sites',len(a),flush=True)
 sustained,gust,_=b.predict(track,[{'lat':r['lat'],'lon':r['lon'],'id':r['building_id']} for r in a],b.get_land())
 times=pd.to_datetime(track.time.values,utc=True).astype('int64').to_numpy()
 hours=pd.date_range(pd.Timestamp(start).ceil('h'),pd.Timestamp(end).floor('h'),freq='h',tz='UTC')
 w0=np.stack([np.interp(hours.asi8,times,sustained[:,j]) for j in range(len(a))],axis=1)*old.KNOT
 g0=np.stack([np.interp(hours.asi8,times,gust[:,j]) for j in range(len(a))],axis=1)*old.KNOT
 grid=pd.read_csv(H/f'grid_{event.lower()}_expanded.csv.gz',parse_dates=['hour'])
 status={r['station']:r['status'] for r in csv.DictReader((H/'station_clean_h2d.csv').open())}
 grid=grid[grid.station.map(status).eq('land')].copy()
 center_lat=np.interp(hours.asi8,times,track.lat.values);center_lon=np.interp(hours.asi8,times,track.lon.values)
 rmw=np.interp(hours.asi8,times,track.radius_max_wind.values)*1.852
 peakw=[None]*len(a);peakg=[None]*len(a)
 for k,h in enumerate(hours):
  stations=grid[grid.hour.eq(h)&grid.obs.notna()]
  if len(stations)<4:continue
  slat=stations.lat.to_numpy(float);slon=stations.lon.to_numpy(float)
  residual=stations.obs.to_numpy(float)-stations.holland.to_numpy(float)
  gs=stations[stations.obs_gust.notna()]
  gg_lat=gs.lat.to_numpy(float);gg_lon=gs.lon.to_numpy(float)
  gg_res=gs.obs_gust.to_numpy(float)-gs.holland_gust.to_numpy(float)
  for j,r in enumerate(a):
   rr,near,n=ok_predict(r['lat'],r['lon'],slat,slon,residual)
   if np.isfinite(rr):
    v=max(0,float(w0[k,j]+rr))
    if peakw[j] is None or v>peakw[j][0]:peakw[j]=(v,str(h),near,n,float(w0[k,j]),rr,k)
   if len(gs)>=4:
    rr,near,n=ok_predict(r['lat'],r['lon'],gg_lat,gg_lon,gg_res)
    if np.isfinite(rr):
     v=max(0,float(g0[k,j]+rr))
     if peakg[j] is None or v>peakg[j][0]:peakg[j]=(v,str(h),near,n,float(g0[k,j]),rr,k)
  print(event,'hour',k+1,'/',len(hours),flush=True)
 metrics=json.loads((H/'metrics_clean_h2d.json').read_text())['land_metrics'][event]['methods']
 for j,r in enumerate(a):
  wp=peakw[j];gp=peakg[j]
  if not wp or not gp:continue
  ratio=float(km(r['lat'],r['lon'],center_lat[gp[6]],center_lon[gp[6]])/rmw[gp[6]]) if rmw[gp[6]]>0 else math.nan
  r.update({'model_method':'H2_CLIMADA_H08_Holland+residual_OK_fixed75','background':'H08_Holland_NHC_HURDAT2_ATCF','peak_definition':'P2_landfall_plusminus12h','event_type':'hurricane','wind_origin':'reconstructed_not_measured','peak_correction_mps':0,'peak_correction_version':'v1.2_hurricane_Holland_no_correction','gust_averaging':'H2 5s gust assumption; METAR gust comparison','sustained_averaging':'H2 METAR ~2min',
  'reconstructed_raw_gust_mps':round(gp[0],3),'reconstructed_raw_sustained_mps':round(wp[0],3),'model_gust_mps':round(gp[0],3),'model_sustained_mps':round(wp[0],3),'model_gust_peak_utc':gp[1],'model_sustained_peak_utc':wp[1],
  'gust_nearest_input_km':round(gp[2],3),'sustained_nearest_input_km':round(wp[2],3),'rmw_ratio_at_gust_peak':round(ratio,3),'rmw_bin_at_gust_peak':('<1' if ratio<1 else '1-3' if ratio<=3 else '>3') if np.isfinite(ratio) else 'unknown','gust_background_mps':round(gp[4],3),'gust_residual_mps':round(gp[5],3),
  'h2_event_gust_rmse_mps':round(metrics['gust']['gust_holland_resok75']['rmse'],3),'h2_event_gust_bias_mps':round(metrics['gust']['gust_holland_resok75']['bias'],3),
  'h2_event_sustained_rmse_mps':round(metrics['holland_resok75']['peak']['rmse'],3),'h2_event_sustained_bias_mps':round(metrics['holland_resok75']['peak']['bias'],3),'sample_error_not_point_guarantee':True})
 print(event,'complete',sum('model_gust_mps' in r for r in a),flush=True)
out=P/'r5_buildings_modeled.json'
if out.exists():raise FileExistsError(out)
out.write_text(json.dumps(rows,indent=1))
print('DONE',len(rows))
