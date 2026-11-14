#!/usr/bin/env python3
"""Replay v2 WindNinja exact settings except frozen height/vegetation factors."""
import csv,json,math,os,subprocess,time,traceback
from pathlib import Path
import pandas as pd,numpy as np,rasterio,pyproj
R=Path('/content/r232d_v3');sites=pd.read_csv(R/'stations_v3_inputs.csv').set_index('station');assert len(sites)==12
v2=pd.read_csv(R/'paired_inputs_v3.csv',float_precision='round_trip');assert len(v2)==4295 and set(v2.period)=={'train','test'}
strong=v2[(v2.period=='test')&(v2.obs_ms>=v2.p90)].copy();assert len(strong)==207
exe=str(R/'wn_env/bin/WindNinja_cli');assert Path(exe).exists()
env={**os.environ,'WINDNINJA_DATA':str(R/'wn_env/share/windninja'),'PROJ_DATA':str(R/'wn_env/share/proj'),'PROJ_LIB':str(R/'wn_env/share/proj')}
xy=pyproj.Transformer.from_crs('EPSG:4326','EPSG:32632',always_xy=True)
D=R/'wn_tmp';D.mkdir(exist_ok=True)
def simulate(row,height,vegetation):
 sid=row.station;speed=row.bilinear_ms
 assert np.isfinite(speed) and speed>0
 direc=(270-math.degrees(math.atan2(row.fc_v,row.fc_u)))%360
 cfg=D/'windninja.cfg'
 cfg.write_text(f'num_threads = 1\nelevation_file = {R/"dem"/(sid+".tif")}\nvegetation = {vegetation}\nmesh_resolution = 100\nunits_mesh_resolution = m\ninitialization_method = domainAverageInitialization\ninput_speed = {speed:.8f}\ninput_speed_units = mps\ninput_direction = {direc:.8f}\ninput_wind_height = 10\nunits_input_wind_height = m\noutput_wind_height = {height}\nunits_output_wind_height = m\noutput_speed_units = mps\nwrite_ascii_output = true\noutput_path = {D}\n')
 try:
  p=subprocess.run([exe,str(cfg)],capture_output=True,text=True,timeout=180,env=env)
  if p.returncode:raise RuntimeError(f'exit={p.returncode} {(p.stdout+p.stderr)[-500:]}')
  asc=list(D.glob('*_vel.asc'));assert len(asc)==1,len(asc)
  x,y=xy.transform(float(sites.loc[sid,'lon']),float(sites.loc[sid,'lat']))
  with rasterio.open(asc[0]) as img:
   val=float(next(img.sample([(x,y)]))[0]);assert np.isfinite(val) and val>=0 and val!=img.nodata
  with rasterio.open(next(D.glob('*_ang.asc'))) as img:
   ang=float(next(img.sample([(x,y)]))[0]);assert np.isfinite(ang) and 0<=ang<=360
  return val,int((ang%360)//90)
 finally:
  for pth in D.iterdir():pth.unlink()
# A v2 configuration reproduction on one exact pair before changing parameters.
row=next(v2.itertuples(index=False));val,sec=simulate(row,10,'grass')
parity={'station':row.station,'valid_utc':row.valid_utc,'v2_wn_ms':row.wn_ms,'replayed_wn_ms':val,'v2_sector':int(row.wn_sector),'replayed_sector':sec}
(R/'parity_v2.json').write_text(json.dumps(parity,indent=2));print('PARITY',parity,flush=True)
assert abs(val-row.wn_ms)<0.011 and sec==int(row.wn_sector),'v2 parity mismatch'
for label,items,factor in [('primary',v2,'both'),('height_only_strong',strong,'height')]:
 path=R/(label+'_wn.csv');failpath=R/(label+'_failures.jsonl')
 assert not path.exists() and not failpath.exists()
 t0=time.monotonic()
 with path.open('x',newline='') as f,failpath.open('x') as err:
  w=csv.DictWriter(f,fieldnames=['station','valid_utc','wn_ms','wn_sector']);w.writeheader()
  for i,row in enumerate(items.itertuples(index=False),1):
   s=sites.loc[row.station]
   try:
    vegetation=s.vegetation if factor=='both' else 'grass'
    value,sector=simulate(row,float(s.output_wind_height_m),vegetation)
    w.writerow(dict(station=row.station,valid_utc=row.valid_utc,wn_ms=value,wn_sector=sector));f.flush()
   except Exception as e:
    err.write(json.dumps(dict(station=row.station,valid_utc=row.valid_utc,error=str(e)))+'\n');err.flush()
   if i%50==0:print('PROGRESS',label,i,len(items),'sec',round(time.monotonic()-t0),flush=True)
 print('DONE',label,i,'sec',round(time.monotonic()-t0),flush=True)
(R/'run.done').write_text(json.dumps({'end':time.time(),'primary':len(v2),'strong':len(strong)}))
