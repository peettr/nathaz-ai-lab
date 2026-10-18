"""StormCast-CONUS A100 80GB one real 2026 test and p30 pressure audit."""
import datetime as dt,json,time,math
from pathlib import Path
import numpy as np,torch,xarray as xr
from earth2studio.models.px import StormCastCONUS
from earth2studio.data import ARCO,HRRR
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic
root=Path('/content/r2_conus_smoke_2026_attempt3.zarr')
if root.exists():raise FileExistsError(root)
t=time.monotonic();m=StormCastCONUS.load_model(StormCastCONUS.load_default_package(),conditioning_data_source=ARCO()).to('cuda').eval()
load_sec=round(time.monotonic()-t,2)
print('LOADED',load_sec,'VARIABLES',len(m.variables),'P30_NAME',[x for x in m.variables if 'p30' in x.lower() or 'p_hl30' in x.lower()],'GRID',m.lat.shape,flush=True)
vars=['u10m','v10m'];ps=[x for x in m.variables if 'p30' in x.lower() or 'p_hl30' in x.lower()];fallback=['p20hl'] if not ps and 'p20hl' in m.variables else [];vars+=(ps or fallback)[:1]
init=dt.datetime(2026,4,4,1)
t=time.monotonic();deterministic([init],2,m,HRRR(),ZarrBackend(str(root)),output_coords={'variable':np.array(vars)},verbose=False)
z=xr.open_zarr(root);slat,slon=35.3931,-97.6007
a=np.sin((np.deg2rad(m.lat)-math.radians(slat))/2)**2+np.cos(np.deg2rad(m.lat))*math.cos(math.radians(slat))*np.sin((np.deg2rad(m.lon%360)-math.radians(slon%360))/2)**2;ij=np.unravel_index(np.argmin(a),a.shape)
result={'model':'StormCastCONUS','event_id':'1329296','init':init.isoformat(),'load_sec':load_sec,'variables':vars,'grid':list(m.lat.shape),'forecast_sec':round(time.monotonic()-t,2),'gpu_peak_gb':torch.cuda.max_memory_allocated()/1e9,'station_grid':list(map(int,ij))}
for k in (ps or fallback)[:1]:result[k+'_Pa']=[float(z[k].isel(time=0,lead_time=h).values[ij]) for h in (0,1,2)]
Path('/content/r2_conus_smoke.json').write_text(json.dumps(result,indent=2))
print('SMOKE',result,flush=True)
