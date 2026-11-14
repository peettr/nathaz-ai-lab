"""Fetch WeatherBench2 ERA5 6-hourly U/V, bilinear to 8 ACE2 gridpoints.
Cloud Zarr remains remote; output small point series only on ephemeral Colab disk.
"""
import numpy as np,xarray as xr,time,json,os
from pathlib import Path
P=Path('/content/era5_point_series');P.mkdir(exist_ok=False)
model=xr.open_dataset('/content/ace2_runs/smoke2/autoregressive_predictions.nc')
# Declared station coords are reference anchors, not station observations.
stations={'KMSP':(44.88,-93.23),'KDSM':(41.53,-93.65),'KOMA':(41.30,-95.90),'KORD':(41.98,-87.90),'KDTW':(42.21,-83.35),'KBUF':(42.94,-78.74),'KPIT':(40.49,-80.23),'KALB':(42.75,-73.80)}
coords=[]
for station,(lat,lon) in stations.items():
 il=int(np.abs(model.lat.values-lat).argmin());jl=int(np.abs(model.lon.values-((lon+360)%360)).argmin());coords.append({'station':station,'station_lat':lat,'station_lon':lon,'grid_lat':float(model.lat.values[il]),'grid_lon':float(model.lon.values[jl]),'i':il,'j':jl})
(P/'points.json').write_text(json.dumps(coords,indent=2))
print('POINTS',coords,flush=True)
t0=time.monotonic();url='gs://weatherbench2/datasets/era5/1959-2022-6h-240x121_equiangular_with_poles_conservative.zarr'
d=xr.open_zarr(url,storage_options={'token':'anon'},consolidated=True)[['10m_u_component_of_wind','10m_v_component_of_wind']]
print('OPEN',round(time.monotonic()-t0,2),'CHUNK',d['10m_u_component_of_wind'].encoding['chunks'],flush=True)
lat=xr.DataArray([x['grid_lat'] for x in coords],dims='station');lon=xr.DataArray([x['grid_lon'] for x in coords],dims='station')
for year in range(1979,2009):
 p=P/f'era5_{year}.npz'
 if p.exists():raise RuntimeError(f'No overwrite {p}')
 t=time.monotonic();piece=d.sel(time=slice(f'{year}-01-01',f'{year}-12-31T18:00:00')).interp(latitude=lat,longitude=lon,method='linear')
 arr=piece.compute()
 times=arr.time.values;u=arr['10m_u_component_of_wind'].values;v=arr['10m_v_component_of_wind'].values
 assert np.all(np.isfinite(u)) and np.all(np.isfinite(v)) and u.shape[1]==len(coords)
 np.savez_compressed(p,time=times,u=u.astype('f4'),v=v.astype('f4'))
 print('YEAR',year,len(times),round(time.monotonic()-t,1),'SAMPLE',round(float(np.hypot(u,v).mean()),3),flush=True)
print('ERA5_DONE',round(time.monotonic()-t0,1),flush=True)
