"""Paired V1 experiment with historical GFS forecast conditioning.

Uses last GFS cycle at least six hours older than HRRR init; this conservative
availability proxy is NOT an observed publication timestamp.
"""
import csv,datetime as dt,json,math,time,traceback
from pathlib import Path
import numpy as np,torch,xarray as xr
from earth2studio.models.px import StormCast
from earth2studio.data import GFS_FX,HRRR
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic
ROOT=Path('/content');out=ROOT/'r2_v1_gfs.jsonl'
events=[r for r in csv.DictReader((ROOT/'events_r2_verified.csv').open()) if r['group']=='v1'][:10]
class LaggedGFS:
 def __init__(self):self.source=GFS_FX(verbose=False)
 def __call__(self,time,lead_time,variable):
  times=np.atleast_1d(time).astype('datetime64[h]')
  if len(times)!=1:raise ValueError('single initialization only')
  # six full hours after the nominal cycle; avoids same-cycle hindsight.
  init=times[0]; cycle=(init-np.timedelta64(6,'h')).astype('datetime64[h]')
  cycle=np.datetime64('1970-01-01T00','h')+np.timedelta64(int(cycle.astype('int64')//6*6),'h')
  offset=init-cycle
  lead=np.atleast_1d(lead_time).astype('timedelta64[ns]')
  shifted=lead+offset.astype('timedelta64[ns]')
  data=self.source([cycle.astype('datetime64[ns]')],shifted,variable)
  return data.assign_coords(time=times.astype('datetime64[ns]'),lead_time=lead)
model=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=LaggedGFS()).to('cuda').eval()
hr=HRRR();lat,lon=model.lat,model.lon%360
seen={(x['id'],x['lead_h'],x['seed']) for line in out.read_text().splitlines() if (x:=json.loads(line)).get('status')=='ok'} if out.exists() else set()
print('GFS_START',len(events),'existing',len(seen),flush=True)
for e in events:
 peak=dt.datetime.fromisoformat(e['utc']);slat=float(e['lat']);slon=float(e['lon']);center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0)
 a=np.sin((np.deg2rad(lat)-math.radians(slat))/2)**2+np.cos(np.deg2rad(lat))*math.cos(math.radians(slat))*np.sin((np.deg2rad(lon)-math.radians(slon%360))/2)**2
 d=12742*np.arcsin(np.sqrt(np.minimum(a,1)))
 for lead in (1,2,3):
  init=center-dt.timedelta(hours=lead)
  cycle=dt.datetime.fromtimestamp((((int(init.replace(tzinfo=dt.timezone.utc).timestamp())//3600)-6)//6*6)*3600,dt.timezone.utc).replace(tzinfo=None)
  for seed in range(101,111):
   if (e['id'],lead,seed) in seen:continue
   t=time.monotonic();root=ROOT/f"r2_GFS_{e['id']}_L{lead}_seed{seed}.zarr"
   row={'id':e['id'],'group':'v1','station':e['station'],'lead_h':lead,'seed':seed,'obs_kt':float(e['obs_kt']),'init':init.isoformat(),'peak_utc':peak.isoformat(),'gfs_cycle':cycle.isoformat(),'gfs_offset_hours':(init-cycle).total_seconds()/3600,'condition':'GFS_FX_prior_cycle_6h_lag','ncei_url':e['ncei_url'],'iem_url':e['iem_url']}
   try:
    if root.exists():raise FileExistsError(root)
    torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    deterministic([init],lead+1,model,hr,ZarrBackend(str(root)),output_coords={'variable':np.array(['u10m','v10m'])},verbose=False)
    z=xr.open_zarr(root);fields={h:np.hypot(z['u10m'].isel(time=0,lead_time=h).values,z['v10m'].isel(time=0,lead_time=h).values) for h in range(max(1,lead-1),lead+2)}
    for name,radius,tol in [('wide',25,1),('narrow',10,.5)]:
     best=None
     for h,x in fields.items():
      valid=init+dt.timedelta(hours=h)
      if abs((valid-peak).total_seconds())>tol*3600:continue
      masked=np.where(d<=radius,x,np.nan)
      if np.isnan(masked).all():continue
      ij=np.unravel_index(np.nanargmax(masked),masked.shape)
      if best is None or masked[ij]>best['ms']:best={'ms':float(masked[ij]),'distance_km':float(d[ij]),'time_bias_min':(valid-peak).total_seconds()/60,'valid':valid.isoformat()}
     row[name]=best
    row['status']='ok'
   except Exception as ex:row.update(status='error',error=repr(ex),trace=traceback.format_exc()[-1500:])
   row['runtime_sec']=round(time.monotonic()-t,2)
   with out.open('a') as f:f.write(json.dumps(row)+'\n')
   print('GFS_ROW',e['id'],lead,seed,row['status'],row['runtime_sec'],row.get('error',''),flush=True)
print('GFS_DONE',flush=True)
