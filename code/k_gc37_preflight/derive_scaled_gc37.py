#!/usr/bin/env python3
"""Generate approved w(p)=w(100 hPa)*p/100 sensitivity from zero-case input."""
import argparse,hashlib,json,pathlib,time
import numpy as np,xarray as xr
p=argparse.ArgumentParser();p.add_argument('--cycle',default='2020060806');p.add_argument('--root',default='/content/r234c_gc37_428d60ab');a=p.parse_args()
r=pathlib.Path(a.root); src=r/f'input_{a.cycle}_zero.nc';dest=r/f'input_{a.cycle}_scaled.nc'
if dest.exists(): raise SystemExit('refuse_existing_scaled')
d=xr.load_dataset(src);p100=d.vertical_velocity.sel(level=100)
for lev in d.level.values:
 if lev<100:d['vertical_velocity'].loc[{'level':lev}]=p100*(float(lev)/100.)
d.to_netcdf(dest,engine='netcdf4',encoding={v:{'zlib':True,'complevel':1} for v in d.data_vars}); d.close()
info={'case':'scaled','src_sha256':hashlib.file_digest(src.open('rb'),'sha256').hexdigest(),'dst_sha256':hashlib.file_digest(dest.open('rb'),'sha256').hexdigest(),'formula':'w(p<100 hPa)=w(100 hPa)*p/100; others identical','cycle':a.cycle}
(r/f'input_{a.cycle}_scaled.json').write_text(json.dumps(info,indent=2));print('SCALED_INPUT_READY',info,flush=True)
