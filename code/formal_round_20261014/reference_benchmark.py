import xarray as xr,numpy as np,time
p='/content/ace_formal/initial_conditions/ic_2001.nc'
d=xr.open_dataset(p)
y=d.latitude.values;x=d.longitude.values
print('GRID',y[:3],y[-3:],x[:3],x[-3:],flush=True)
a=xr.open_zarr('gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr',storage_options={'token':'anon'},consolidated=True)
sel=a['10m_u_component_of_wind'].sel(time=slice('1996-10-01T00:00','1996-10-03T18:00')).isel(latitude=slice(450,510),longitude=slice(1000,1100))
t=time.monotonic();v=sel.load();print('12 STEPS',round(time.monotonic()-t,2),v.shape,float(v.mean()),flush=True)
