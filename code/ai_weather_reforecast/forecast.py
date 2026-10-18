"""Run one ERA5-initialised global deterministic forecast; save only regional fields."""
import os, sys, time, json, traceback
import numpy as np, torch, xarray as xr
from earth2studio.data import ARCO
from earth2studio.models.px import Pangu6, FuXi
from earth2studio.run import deterministic
from earth2studio.io import ZarrBackend
from collections import OrderedDict

model_name,event,lead=sys.argv[1],sys.argv[2],int(sys.argv[3])
assert model_name in ('Pangu6','FuXi') and event in ('E1','E2') and lead in (12,24,48,72,120)
valid=np.datetime64({'E1':'2018-08-10T18:00','E2':'2020-06-09T06:00'}[event])
init=valid-np.timedelta64(lead,'h')
lat_bounds={'E1':(34.5,35.5),'E2':(39.5,41.5)}[event]
lon_bounds={'E1':(265.0,265.75),'E2':(255.5,258.5)}[event]
lat=np.arange(lat_bounds[1],lat_bounds[0]-0.001,-0.25)
lon=np.arange(lon_bounds[0],lon_bounds[1]+0.001,0.25)
cls={'Pangu6':Pangu6,'FuXi':FuXi}[model_name]
base='/content/ai_weather';os.makedirs(base,exist_ok=True)
suffix='grid25_rhproxy_v3' if model_name=='FuXi' else 'grid25'
out=f'{base}/{model_name}_{event}_{lead}_{suffix}.zarr'
assert not os.path.exists(out),f'existing output {out}'
print('START',model_name,event,lead,str(init),out,flush=True)
t0=time.monotonic()
model=cls.load_model(cls.load_default_package())
print('MODEL_READY',round(time.monotonic()-t0,2),flush=True)
# Read both initial frames for FuXi, one for Pangu; ARCO is an unauthenticated source.
t1=time.monotonic()
io=ZarrBackend(out)
variables=np.array([v for v in model.output_coords(model.input_coords())['variable'] if v.startswith(('t','q','r','u','v','z')) or v in ('sp','msl')])
# Retain all model variables over the small region; no large field lands on 工作站.
coords=OrderedDict(lat=lat,lon=lon,variable=variables)
class ERA5WithRH:
 def __init__(self):self.source=ARCO(verbose=False)
 def __call__(self,times,names):
  names=list(names); extra=[v for v in names if v.startswith('r') and v[1:].isdigit()]
  request=list(dict.fromkeys([v for v in names if v not in extra]+['q'+v[1:] for v in extra]+['t'+v[1:] for v in extra]))
  da=self.source(times,request)
  result=[]
  for v in names:
   if v not in extra: result.append(da.sel(variable=v,drop=True));continue
   level=int(v[1:]);q=da.sel(variable='q'+str(level),drop=True);T=da.sel(variable='t'+str(level),drop=True);p=level*100
   vapor=q*p/(.622+.378*q)
   es=611.2*np.exp(17.67*(T-273.15)/(T-29.65))
   rh=(100*vapor/es).clip(min=.1,max=100.)
   result.append(rh)
  return xr.concat(result,dim=xr.IndexVariable('variable',names)).transpose(*da.dims)
source=ERA5WithRH() if model_name=='FuXi' else ARCO(verbose=False)
deterministic([init],lead//6,model,source,io,output_coords=coords,verbose=False)
print('COMPLETE',model_name,event,lead,'seconds',round(time.monotonic()-t0,2),'inference_plus_data',round(time.monotonic()-t1,2),flush=True)
with open(f'{base}/{model_name}_{event}_{lead}_{suffix}.json','w') as f:json.dump(dict(model=model_name,event=event,lead_h=lead,init=str(init),valid=str(valid),seconds=time.monotonic()-t0,output=out),f)
