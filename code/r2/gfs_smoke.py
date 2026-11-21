"""One paired V1 forecast with GFS available at start time (lagged cycle)."""
import datetime as dt,json,time,numpy as np,torch,xarray as xr
from pathlib import Path
from earth2studio.models.px import StormCast
from earth2studio.data import GFS_FX,HRRR
from earth2studio.run import deterministic
from earth2studio.io import ZarrBackend
class LaggedGFS:
 def __init__(self):self.source=GFS_FX(verbose=False)
 def __call__(self,time,lead_time,variable):
  t=np.atleast_1d(time).astype('datetime64[h]');assert len(t)==1
  old=t[0]-np.timedelta64(6,'h');cycle=np.datetime64('1970-01-01T00','h')+np.timedelta64(int(old.astype('int64')//6*6),'h')
  lead=np.atleast_1d(lead_time).astype('timedelta64[ns]');shift=lead+(t[0]-cycle).astype('timedelta64[ns]')
  print('CYCLE',cycle,'REQUEST',t[0],shift.tolist(),flush=True)
  return self.source([cycle.astype('datetime64[ns]')],shift,variable).assign_coords(time=t.astype('datetime64[ns]'),lead_time=lead)
p=Path('/content/r2_gfs_smoke_1089702_L2_seed101_attempt2.zarr');assert not p.exists()
m=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=LaggedGFS()).to('cuda').eval()
t=time.monotonic();torch.manual_seed(101);torch.cuda.manual_seed_all(101)
deterministic([dt.datetime(2023,4,20,2)],3,m,HRRR(),ZarrBackend(str(p)),output_coords={'variable':np.array(['u10m','v10m'])},verbose=False)
z=xr.open_zarr(p);la,lo=41.53,-93.66
import math
a=np.sin((np.deg2rad(m.lat)-math.radians(la))/2)**2+np.cos(np.deg2rad(m.lat))*math.cos(math.radians(la))*np.sin((np.deg2rad(m.lon%360)-math.radians(lo%360))/2)**2
d=12742*np.arcsin(np.sqrt(np.minimum(a,1)))
x=np.hypot(z['u10m'].isel(time=0,lead_time=2).values,z['v10m'].isel(time=0,lead_time=2).values)
r={'event':'1089702','seed':101,'peak_utc':'2023-04-20T03:56','hrrr_init':'2023-04-20T02:00','gfs_cycle':'2023-04-19T18:00','gfs_forecast_hour':10,'max25_ms':float(np.nanmax(np.where(d<=25,x,np.nan))),'runtime_s':time.monotonic()-t,'gpu_gb':torch.cuda.max_memory_allocated()/1e9}
Path('/content/r2_gfs_smoke.json').write_text(json.dumps(r,indent=2));print('RESULT',r,flush=True)
