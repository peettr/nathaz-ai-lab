import xarray as xr
u='gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'
s=xr.open_zarr(u,storage_options={'token':'anon'},consolidated=True)
print([x for x in s.data_vars if 'land' in x.lower() or 'mask' in x.lower()]);print(s.sizes)
