"""StormCast A100 smoke: load released weights and one public-data forecast."""
import time, json, traceback
import numpy as np
import torch
from earth2studio.models.px import StormCast
from earth2studio.data import HRRR
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic

print('START', time.strftime('%Y-%m-%dT%H:%M:%S%z'), flush=True)
print('DEVICE', torch.cuda.get_device_name(), torch.cuda.get_device_properties(0).total_memory, flush=True)
t0=time.monotonic()
try:
    package=StormCast.load_default_package()
    print('PACKAGE', package, flush=True)
    model=StormCast.load_model(package)
    print('WEIGHTS_LOADED_SEC', time.monotonic()-t0, 'variables',len(model.variables), flush=True)
    model=model.to('cuda').eval()
    print('MODEL_GPU_PEAK_GB',torch.cuda.max_memory_allocated()/1e9, flush=True)
    model.conditioning_data_source=__import__('earth2studio.data',fromlist=['ARCO']).ARCO()
    print('CONDITIONING_ARCO_ERA5_HOURLY',flush=True)
    t1=time.monotonic()
    output=ZarrBackend('/content/convective_smoke_v4.zarr')
    deterministic(['2023-06-18T03:00:00'], 1, model, HRRR(), output, output_coords={'variable': np.array(['u10m','v10m'])})
    torch.cuda.synchronize()
    print('FORECAST_DONE_SEC',time.monotonic()-t1, 'TOTAL_SEC',time.monotonic()-t0,'PEAK_GPU_GB',torch.cuda.max_memory_allocated()/1e9,flush=True)
    import xarray as xr
    ds=xr.open_zarr('/content/convective_smoke_v4.zarr')
    print('DATASET', ds, flush=True)
    iy,ix=np.unravel_index(np.argmin((model.lat-36.1622)**2+((model.lon%360)-(-97.0891%360))**2),model.lat.shape)
    print('STATION_GRID',iy,ix,float(model.lat[iy,ix]),float(model.lon[iy,ix]), flush=True)
    print('SITE_VALUES',ds.isel(hrrr_y=iy,hrrr_x=ix).to_dict(),flush=True)
except Exception:
    traceback.print_exc()
    raise
