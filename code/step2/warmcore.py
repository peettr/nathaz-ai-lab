"""Warm-core metadata: ERA5 T300 center-1-degree minus 5--10-degree annulus."""
import json,time,traceback
from pathlib import Path
import numpy as np,xarray as xr
R=Path('/content/l2612'); cohort=json.loads((R/'cohort_2021.json').read_text());out=R/'warmcore.jsonl';done={}
if out.exists():
 for line in out.read_text().splitlines():
  r=json.loads(line);done[r['sid']]=r
s=xr.open_zarr('gs://weatherbench2/datasets/era5/1959-2022-full_37-6h-0p25deg_derived.zarr',storage_options={'token':'anon'},chunks=None)
lat=s['latitude'].values;lon=s['longitude'].values
for i,r in enumerate(cohort):
 if r['sid'] in done:continue
 t=time.time()
 try:
  # Explicitly wrap longitude and use latitude-dependent longitudinal distance.
  iy=np.flatnonzero(abs(lat-r['lat'])<=10)
  delta=((lon-r['lon']+180)%360-180)*np.cos(np.deg2rad(r['lat']))
  ix=np.flatnonzero(abs(delta)<=10)
  a=s['temperature'].sel(time=np.datetime64(r['time']),level=300).isel(latitude=iy,longitude=ix).values
  dist=np.hypot(lat[iy,None]-r['lat'],delta[None,ix]);inner=np.nanmean(a[dist<=1]);outer=np.nanmean(a[(dist>=5)&(dist<=10)])
  v={'sid':r['sid'],'time':r['time'],'warmcore_K':float(inner-outer),'center_K':float(inner),'annulus_K':float(outer)}
 except Exception as e:v={'sid':r['sid'],'time':r['time'],'error':repr(e)}
 with out.open('a') as f:f.write(json.dumps(v)+'\n');f.flush()
 if i%10==0:print(i+1,len(cohort),round(time.time()-t,2),v,flush=True)
(R/'warmcore.done').write_text('ok\n')
