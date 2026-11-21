"""Ten-member CONUS out-of-training pilot, 2026 OKC, L1 only."""
import datetime as dt,json,math,time
from pathlib import Path
import numpy as np,torch,xarray as xr
from earth2studio.models.px import StormCastCONUS
from earth2studio.data import ARCO,HRRR,HRRR_FX
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic
peak=dt.datetime(2026,4,4,2,3);init=dt.datetime(2026,4,4,1)
lat0,lon0=35.3886,-97.6002
p=Path('/content/r2_conus_pilot_1329296_L1.jsonl');assert not p.exists()
m=StormCastCONUS.load_model(StormCastCONUS.load_default_package(),conditioning_data_source=ARCO()).to('cuda').eval()
la,lo=m.lat,m.lon%360
a=np.sin((np.deg2rad(la)-math.radians(lat0))/2)**2+np.cos(np.deg2rad(la))*math.cos(math.radians(lat0))*np.sin((np.deg2rad(lo)-math.radians(lon0%360))/2)**2
d=12742*np.arcsin(np.sqrt(np.minimum(a,1)))
for seed in range(101,111):
 root=Path(f'/content/r2_CONUS_1329296_L1_seed{seed}.zarr')
 if root.exists():raise FileExistsError(root)
 t=time.monotonic();torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
 deterministic([init],2,m,HRRR(),ZarrBackend(str(root)),output_coords={'variable':np.array(['u10m','v10m'])},verbose=False)
 z=xr.open_zarr(root);winds={h:np.hypot(z['u10m'].isel(time=0,lead_time=h).values,z['v10m'].isel(time=0,lead_time=h).values) for h in (1,2)}
 row={'event_id':'1329296','station':'OKC','seed':seed,'obs_kt':55,'init':init.isoformat(),'peak_utc':peak.isoformat(),'condition':'ARCO_ERA5','runtime_s':time.monotonic()-t,'gpu_peak_gb':torch.cuda.max_memory_allocated()/1e9}
 for name,r,tol in [('wide',25,1),('narrow',10,.5)]:
  poss=[]
  for h,w in winds.items():
   valid=init+dt.timedelta(hours=h)
   if abs((valid-peak).total_seconds())>tol*3600:continue
   x=np.where(d<=r,w,np.nan);ij=np.unravel_index(np.nanargmax(x),x.shape)
   poss.append({'ms':float(x[ij]),'distance_km':float(d[ij]),'valid':valid.isoformat()})
  row[name]=max(poss,key=lambda x:x['ms']) if poss else None
 with p.open('a') as f:f.write(json.dumps(row)+'\n')
 print('CONUS_MEMBER',seed,round(row['runtime_s'],1),row['wide'],flush=True)
print('CONUS_PILOT_COMPLETE',flush=True)
