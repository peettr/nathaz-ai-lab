import xarray as xr,numpy as np,json
from huggingface_hub import hf_hub_download
p=hf_hub_download('allenai/ACE2-ERA5','initial_conditions/ic_1979.nc',revision='f25123c52d7faa8f3533816a311cf3353ee83daa',local_dir='/content/ace_formal')
d=xr.open_dataset(p);print('IC_FIELDS',list(d.data_vars), 'GRID',d.latitude.values[:2],d.longitude.values[:2])
s=json.load(open('/content/ace_formal/sites_frozen.json'))
wb=xr.open_zarr('gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr',storage_options={'token':'anon'},consolidated=True)
for k in s['order']:
 a=s['stations'][k];la=a['cell_lat'];lo=a['cell_lon'];land=wb.land_sea_mask.sel(latitude=la,longitude=lo,method='nearest').values.item();print('LAND',k,la,lo,land)
