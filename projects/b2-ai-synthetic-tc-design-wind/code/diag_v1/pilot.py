import numpy as np,xarray as xr,zipfile
from climada.hazard.trop_cyclone.trop_cyclone_windfields import tctrack_to_si,_compute_windfields,MODEL_VANG
p='/content/RAFT.NA.v20231016.nc';d=xr.open_dataset(p)
print('dims',dict(d.sizes),'vars',list(d.data_vars),'units',d.attrs,flush=True)
print('sample',[(v,d[v][0,:3].values.tolist()) for v in ('lat','lon','vmax','mslp','rmax')],flush=True)
with zipfile.ZipFile('/content/STORMV4.zip') as z:
 names=[x for x in z.namelist() if '_NA_' in x];print('storm files',names,flush=True)
