"""Read-only H2 Idalia FR12 peak decomposition at DAT coordinates."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import csv,sys,datetime as dt
from pathlib import Path
import numpy as np,pandas as pd
P=Path(__file__).resolve().parent;H=P.parent/'obs_fusion/h2'
sys.path.insert(0,str(P));from pilot_hurricane_r3 import b,old,km,ok_predict
rows=[r for r in csv.DictReader((P/'dat_hurricane_points_r3.csv').open()) if r['event']=='IDALIA' and 'FR12' in r['damage_type']]
landfall=old.dt(old.CANDIDATES['IDALIA'][1]);start=landfall-dt.timedelta(hours=12);end=landfall+dt.timedelta(hours=12)
sid,raw=old.parse_hurdat()['IDALIA'];track,err=b.build_track(raw,old.bdeck(sid),start,end)
if err:raise RuntimeError(err)
wind,gust,_=b.predict(track,[{'lat':float(r['lat']),'lon':float(r['lon']),'id':r['objectid']} for r in rows],b.get_land())
times=pd.to_datetime(track.time.values,utc=True).astype('int64').to_numpy(); grid=pd.read_csv(H/'grid_idalia_expanded.csv.gz',parse_dates=['hour'])
status={r['station']:r['status'] for r in csv.DictReader((H/'station_clean_h2d.csv').open())};grid=grid[grid.station.map(status).eq('land')]
for i,r in enumerate(rows):
 h=pd.Timestamp(r['model_gust_peak_utc']);hns=h.value
 bg=float(np.interp(hns,times,gust[:,i])*old.KNOT)
 stations=grid[grid.hour.eq(h)&grid.obs_gust.notna()];res=stations.obs_gust.to_numpy(float)-stations.holland_gust.to_numpy(float)
 rr,nearest,n=ok_predict(float(r['lat']),float(r['lon']),stations.lat.to_numpy(float),stations.lon.to_numpy(float),res)
 lat=float(np.interp(hns,times,track.lat.values));lon=float(np.interp(hns,times,track.lon.values));rmw=float(np.interp(hns,times,track.radius_max_wind.values)*1.852)
 print(r['objectid'],'gust',r['model_gust_mps'],'background',round(bg,3),'residual',round(rr,3),'background_plus_res',round(bg+rr,3),'center_km',round(float(km(float(r['lat']),float(r['lon']),lat,lon)),2),'RMW_km',round(rmw,2),'ratio_gust',round(float(km(float(r['lat']),float(r['lon']),lat,lon))/rmw,3),'nearest_gust_station_km',round(nearest,2),'n',n)
