import numpy as np,xarray as xr
from climada.hazard.trop_cyclone.trop_cyclone_windfields import tctrack_to_si,_compute_windfields,MODEL_VANG
n=5;time=np.datetime64('2000-01-01')+np.arange(n).astype('timedelta64[h]')
d=xr.Dataset(data_vars={'lat':('time',np.full(n,25.0)),'lon':('time',np.array([-82.,-81.9,-81.8,-81.7,-81.6])),'central_pressure':('time',np.full(n,950.)),'radius_max_wind':('time',np.full(n,25.)),'max_sustained_wind':('time',np.full(n,110.)),'environmental_pressure':('time',np.full(n,1010.)),'time_step':('time',np.full(n,1.))},coords={'time':time},attrs={'max_sustained_wind_unit':'knots','central_pressure_unit':'mbar'})
si=tctrack_to_si(d);v,ix=_compute_windfields(si,np.array([[25.,-81.7],[26.,-81.7]]),MODEL_VANG['H08'],max_dist_eye_km=300)
print('PILOT',ix,np.linalg.norm(v,axis=2).max(axis=0),flush=True)
