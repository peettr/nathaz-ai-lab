"""Extract public WB2 ERA5 u10/v10 for DFW and AUS on ACE2 grid."""
from pathlib import Path
import json,time
import numpy as np
import xarray as xr
out=Path('/content/dfw_aus_era5');out.mkdir(exist_ok=False)
ic=xr.open_dataset('/content/ace2/initial_conditions/ic_1979.nc')
anchors={'DFW':(32.8968,-97.038),'AUS':(30.183,-97.6799)}
points=[]
for key,(latitude,longitude) in anchors.items():
 i=int(np.abs(ic.latitude.values-latitude).argmin())
 j=int(np.abs(ic.longitude.values-(longitude%360)).argmin())
 points.append(dict(station_anchor=key,station_lat=latitude,station_lon=longitude,grid_lat=float(ic.latitude.values[i]),grid_lon=float(ic.longitude.values[j]),i=i,j=j))
(out/'points.json').write_text(json.dumps(points,indent=2))
print('POINTS',points,flush=True)
url='gs://weatherbench2/datasets/era5/1959-2022-6h-240x121_equiangular_with_poles_conservative.zarr'
d=xr.open_zarr(url,storage_options={'token':'anon'},consolidated=True)[['10m_u_component_of_wind','10m_v_component_of_wind']]
lat=xr.DataArray([x['grid_lat'] for x in points],dims='station')
lon=xr.DataArray([x['grid_lon'] for x in points],dims='station')
for year in range(1979,2009):
 t=time.monotonic()
 piece=d.sel(time=slice(f'{year}-01-01',f'{year}-12-31T18:00:00')).interp(latitude=lat,longitude=lon,method='linear').compute()
 u=piece['10m_u_component_of_wind'].values;v=piece['10m_v_component_of_wind'].values
 assert u.shape[1]==2 and np.isfinite(u).all() and np.isfinite(v).all()
 np.savez_compressed(out/f'era5_{year}.npz',time=piece.time.values,u=u.astype('f4'),v=v.astype('f4'))
 print('YEAR',year,len(piece.time),round(time.monotonic()-t,1),flush=True)
print('ERA5_DONE',flush=True)
