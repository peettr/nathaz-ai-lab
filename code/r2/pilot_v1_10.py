"""Ten independent StormCast V1 members on a verified 2023 ASOS event."""
import datetime as dt, json, math, time, os
from pathlib import Path
import numpy as np, torch, xarray as xr
from earth2studio.models.px import StormCast
from earth2studio.data import ARCO,HRRR,HRRR_FX
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic
p=Path('/content/r2_pilot_metrics.jsonl')
if p.exists():raise FileExistsError(p)
peak=dt.datetime(2023,4,20,3,56);init=dt.datetime(2023,4,20,2)
lat,lon=41.53,-93.66
print('LOAD',flush=True)
m=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=ARCO()).to('cuda').eval()
print('GRID',m.lat.shape,float(m.lat.min()),float(m.lat.max()),float(m.lon.min()),float(m.lon.max()),flush=True)
a=np.sin((np.deg2rad(m.lat)-math.radians(lat))/2)**2+np.cos(np.deg2rad(m.lat))*math.cos(math.radians(lat))*np.sin((np.deg2rad(m.lon%360)-math.radians(lon%360))/2)**2
d=12742*np.arcsin(np.sqrt(np.minimum(a,1)))
print('NEAREST_KM',d.min(),flush=True)
for n,seed in enumerate(range(101,111)):
 t=time.monotonic();torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
 root=Path(f'/content/r2_V1_DSM_L2_seed{seed}.zarr')
 if root.exists():raise FileExistsError(root)
 deterministic([init],3,m,HRRR(),ZarrBackend(str(root)),output_coords={'variable':np.array(['u10m','v10m'])},verbose=False)
 ds=xr.open_zarr(root)
 row={'id':'1089702','lead_h':2,'seed':seed,'init':init.isoformat(),'obs_kt':54,'condition':'ARCO_ERA5','seconds':round(time.monotonic()-t,2),'gpu_gb':round(torch.cuda.max_memory_allocated()/1e9,3)}
 for radius,tol,name in [(25,1,'wide'),(10,.5,'narrow')]:
  best=None
  for h in [1,2,3]:
   if abs((init+dt.timedelta(hours=h)-peak).total_seconds())>tol*3600:continue
   wind=np.hypot(ds['u10m'].isel(time=0,lead_time=h).values,ds['v10m'].isel(time=0,lead_time=h).values)
   masked=np.where(d<=radius,wind,np.nan);ij=np.unravel_index(np.nanargmax(masked),masked.shape)
   z={'ms':float(masked[ij]),'distance_km':float(d[ij]),'valid':(init+dt.timedelta(hours=h)).isoformat()}
   if best is None or z['ms']>best['ms']:best=z
  row[name]=best
 with p.open('a') as f:f.write(json.dumps(row)+'\n')
 print('MEMBER',row,flush=True)
print('COMPLETE',n+1,flush=True)
