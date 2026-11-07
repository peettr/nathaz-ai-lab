import xarray as xr
u='gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'
d=xr.open_zarr(u,storage_options={'token':'anon'},consolidated=True)
print('VARIABLES',[(k,str(d[k].dims),d[k].attrs.get('units','')) for k in d.data_vars if 'pressure' in k.lower() or 'land' in k.lower() or '10m_' in k.lower()])
print('TIME',str(d.time.values[0]),str(d.time.values[-1]));print('GRID',str(d.latitude.values[:2]),str(d.longitude.values[:2]))
