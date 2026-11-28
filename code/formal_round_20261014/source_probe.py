from huggingface_hub import hf_hub_download
import xarray as xr,numpy as np,time
p=hf_hub_download('allenai/ACE2-ERA5','initial_conditions/ic_2001.nc',local_dir='/content/ace_formal')
d=xr.open_dataset(p)
print('IC',dict(d.sizes),list(d.data_vars),d.time.values,flush=True)
u='gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'
a=xr.open_zarr(u,storage_options={'token':'anon'},consolidated=True)
print('VALID',a.sel(time=slice('2020-01-01','2020-01-02')).time.values,flush=True)
for dt in ['2020-01-01T00:00:00','2020-01-01T06:00:00']:
 t=time.monotonic();s=a['10m_u_component_of_wind'].sel(time=dt).load()
 print('ONE GLOBAL',dt,round(time.monotonic()-t,1),float(s.sel(latitude=32.75,longitude=263,method='nearest')),flush=True)
