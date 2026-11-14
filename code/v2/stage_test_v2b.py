#!/usr/bin/env python3
"""v2 frozen protocol: SIX end-stamped bins centered on valid time; FOUR f24 main gate."""
import csv,json,math,os,subprocess,time
from pathlib import Path
import numpy as np,pandas as pd,rasterio,pyproj
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path('/content/e_terrain_v2');O=R/'stage_test_v2b';O.mkdir(exist_ok=False)
sites=pd.read_csv(R/'stations_frozen.csv').set_index('station');assert len(sites)==12
sources=['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS'];leads=[24,48]
parts=list((R/'full/forecast_parts').glob('*.csv'));errors=list((R/'full/forecast_parts').glob('ERROR_*.txt'))
print('STAGE_FORECAST_OBJECTS',len(parts),len(errors),flush=True)
f=pd.concat([pd.read_csv(p) for p in parts],ignore_index=True)
f['init_utc']=pd.to_datetime(f.init_utc,utc=True);f['valid_utc']=f.init_utc+pd.to_timedelta(f.lead_h,unit='h')
f=f[(f.valid_utc>=pd.Timestamp('2023-10-01',tz='UTC'))&(f.valid_utc<pd.Timestamp('2024-04-01',tz='UTC'))].copy()
assert not f.duplicated(['station','source','lead_h','valid_utc']).any()
# center 60-minute interval (t-30,t+30], 10-minute *end* labels t-20,..,t+30
observations=[]
for sid in sites.index:
 o=pd.read_csv(R/f'obs_{sid}.csv',parse_dates=['time_utc']).set_index('time_utc').sort_index()
 idx=pd.DatetimeIndex(f.loc[f.station==sid,'valid_utc'].unique()).sort_values()
 for t in idx:
  stamps=[t+pd.Timedelta(minutes=k) for k in (-20,-10,0,10,20,30)]
  vals=o.speed_ms.reindex(stamps)
  observations.append((sid,t,float(vals.mean()) if vals.notna().sum()==6 else np.nan,int(vals.notna().sum())))
obs=pd.DataFrame(observations,columns=['station','valid_utc','obs_ms','obs_bins'])
f=f.merge(obs,on=['station','valid_utc'],validate='many_to_one');f['bilinear_ms']=np.hypot(f.fc_u,f.fc_v)
f['sector']=((np.degrees(np.arctan2(-f.fc_u,-f.fc_v))%360)//90).astype(int)
f['terrain']=f.station.map(sites.terrain);f['period']=np.where(f.valid_utc<pd.Timestamp('2024-01-01',tz='UTC'),'train','test')
# all-source baselines with sector-conditioned OLS, train only; no leaking test targets.
def fit(x,y):
 mask=np.isfinite(x)&np.isfinite(y)
 if mask.sum()<2:return None
 a,b=np.linalg.lstsq(np.column_stack([x[mask],np.ones(mask.sum())]),y[mask],rcond=None)[0]
 return [float(a),float(b),int(mask.sum())]
def predict(x,coef):return max(0.,coef[0]*x+coef[1]) if coef else np.nan
coef=[]
for (sid,src,lead,sec),g in f[f.period=='train'].groupby(['station','source','lead_h','sector']):
 m=fit(g.bilinear_ms.to_numpy(),g.obs_ms.to_numpy());coef.append((sid,src,int(lead),int(sec),m))
lookup={(s,src,h,q):v for s,src,h,q,v in coef}
assert all(v is not None for _,_,_,_,v in coef)
f['mos_ms']=[predict(row.bilinear_ms,lookup.get((row.station,row.source,int(row.lead_h),int(row.sector)))) for row in f.itertuples()]
f['wn_ms']=np.nan
main=f[(f.source=='FOUR_v200_GFS')&(f.lead_h==24)&f.obs_ms.notna()&(f.period=='test')].copy()
# Derive train-only percentiles from exactly paired, six-bin target. Not from test observations.
thresholds={sid:{'p90':float(g.obs_ms.quantile(.9)),'p99':float(g.obs_ms.quantile(.99)),'train_n':len(g)} for sid,g in main[main.period=='train'].groupby('station')}
print('STAGE_THRESHOLD_STATIONS',len(thresholds),flush=True)
executable=str(R/'wn_env/bin/WindNinja_cli');env={**os.environ,'WINDNINJA_DATA':str(R/'wn_env/share/windninja'),'PROJ_DATA':str(R/'wn_env/share/proj'),'PROJ_LIB':str(R/'wn_env/share/proj')}
xy=pyproj.Transformer.from_crs('EPSG:4326','EPSG:32632',always_xy=True)
check=O/'main_pairs_v2.csv';failed=[];t0=time.monotonic()
stage_paths=[R/'stage_v2b/main_pairs_v2.csv',R/'stage_test_v2b/main_pairs_v2.csv']
staged=pd.concat([pd.read_csv(p,parse_dates=['init_utc','valid_utc']) for p in stage_paths if p.exists()],ignore_index=True) if any(p.exists() for p in stage_paths) else pd.DataFrame()
if not staged.empty:
 assert not staged.duplicated(['station','valid_utc']).any()
 staged_keys=set(zip(staged.station,staged.valid_utc))
else:staged_keys=set()
print('STAGE_REUSED',len(staged_keys),flush=True)
columns=['station','terrain','source','init_utc','valid_utc','lead_h','period','obs_ms','obs_bins','sector','wn_sector','bilinear_ms','mos_ms','wn_ms']
with check.open('x',newline='') as out:
 w=csv.DictWriter(out,fieldnames=columns);w.writeheader()
 for count,row in enumerate(main.itertuples(),1):
  if (row.station,row.valid_utc) in staged_keys:continue
  sid=row.station;speed=row.bilinear_ms
  if not np.isfinite(speed) or speed<=0:failed.append((sid,str(row.valid_utc),'invalid wind'));continue
  direc=(270-math.degrees(math.atan2(row.fc_v,row.fc_u)))%360
  d=O/'wn_tmp';d.mkdir(exist_ok=True)
  cfg=d/'windninja.cfg'
  cfg.write_text(f'num_threads = 1\nelevation_file = {R/"dem"/(sid+".tif")}\nvegetation = grass\nmesh_resolution = 100\nunits_mesh_resolution = m\ninitialization_method = domainAverageInitialization\ninput_speed = {speed:.8f}\ninput_speed_units = mps\ninput_direction = {direc:.8f}\ninput_wind_height = 10\nunits_input_wind_height = m\noutput_wind_height = 10\nunits_output_wind_height = m\noutput_speed_units = mps\nwrite_ascii_output = true\noutput_path = {d}\n')
  try:
   p=subprocess.run([executable,str(cfg)],capture_output=True,text=True,timeout=180,env=env)
   if p.returncode:raise RuntimeError(f'exit={p.returncode}: {(p.stdout+p.stderr)[-350:]}')
   asc=list(d.glob('*_vel.asc'))
   if len(asc)!=1:raise ValueError(f'output rasters={len(asc)}')
   x,y=xy.transform(float(sites.loc[sid,'lon']),float(sites.loc[sid,'lat']))
   with rasterio.open(asc[0]) as raster:
    val=float(next(raster.sample([(x,y)]))[0]);assert np.isfinite(val) and val>=0 and val!=raster.nodata
   with rasterio.open(next(d.glob('*_ang.asc'))) as angle:
    ang=float(next(angle.sample([(x,y)]))[0]);assert np.isfinite(ang) and 0<=ang<=360
   record={c:getattr(row,c) for c in columns if c not in ('wn_ms','wn_sector')};record['wn_ms']=val;record['wn_sector']=int((ang%360)//90)
   w.writerow(record);out.flush()
  except Exception as exc:failed.append((sid,str(row.valid_utc),str(exc)))
  finally:
   for pth in d.iterdir():pth.unlink()
  if count%100==0:print('WN_V2_PROGRESS',count,len(main),'errors',len(failed),'sec',int(time.monotonic()-t0),flush=True)
print('WN_V2_DONE',len(main),len(failed),int(time.monotonic()-t0),flush=True)
(O/'wn_failures.json').write_text(json.dumps(failed,indent=2))
