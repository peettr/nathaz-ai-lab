#!/usr/bin/env python3
"""Independent t0 GC37-input against native GFS f000 850/500 T/U QA."""
import argparse,hashlib,json,pathlib
import numpy as np,xarray as xr,pygrib
p=argparse.ArgumentParser();p.add_argument('--cycle',default='2020060806');p.add_argument('--root',default='/content/r234c_gc37_428d60ab');a=p.parse_args();r=pathlib.Path(a.root)
src=r/f'input_{a.cycle}_zero.nc'; raw=r/'raw'/f'gfs.0p25.{a.cycle}.f000.grib2';d=xr.open_dataset(src);g=pygrib.open(str(raw));metrics={}
for level in (850,500):
 for name,short in [('temperature','t'),('u_component_of_wind','u')]:
  native=g.select(shortName=short,typeOfLevel='isobaricInhPa',level=level)[0].values
  if np.ma.isMaskedArray(native):native=native.filled(np.nan)
  actual=np.asarray(d[name].sel(level=level).isel(batch=0,time=-1).values)
  diff=actual-np.asarray(native)[::-1,:]; metrics[f'{name}_{level}']={'rmse':float(np.sqrt(np.mean(diff.astype('float64')**2))),'max_abs':float(np.max(np.abs(diff))),'n':int(diff.size)}
g.close();d.close();result={'cycle':a.cycle,'t0_input_sha256':hashlib.file_digest(src.open('rb'),'sha256').hexdigest(),'native_file_sha256':hashlib.file_digest(raw.open('rb'),'sha256').hexdigest(),'pressure_levels_hpa':[850,500],'metrics':metrics}
out=r/f'QA_T0_{a.cycle}.json';out.open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
