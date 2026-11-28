"""Extract small ERA5 regional profile arrays from public Google ARCO Zarr."""
import os, numpy as np, zarr
from datetime import datetime,timedelta
from earth2studio.data.utils import obstore_zarr_store
from earth2studio.data import ARCO
root='/content/ai_weather';os.makedirs(root,exist_ok=True)
g=zarr.open(obstore_zarr_store('gs://'+ARCO.ARCO_PATH.lstrip('/'),store_kwargs={'skip_signature':True}),mode='r')
levels=np.asarray(g['level'][:]);print('LEVELS',levels,flush=True)
for event,valid,latb,lonb in [('E1','2018-08-10T18:00', (34.5,35.5),(265.,265.75)),('E2','2020-06-09T06:00',(39.5,41.5),(255.5,258.5))]:
 lat=np.arange(latb[1],latb[0]-.001,-.25);lon=np.arange(lonb[0],lonb[1]+.001,.25)
 la=slice(int(round((90-lat[0])*4)),int(round((90-lat[-1])*4))+1)
 lo=slice(int(round(lon[0]*4)),int(round(lon[-1]*4))+1)
 dt=datetime.fromisoformat(valid)
 times={'valid':dt,'P24':dt-timedelta(hours=24),'P48':dt-timedelta(hours=48),'P72':dt-timedelta(hours=72),'P120':dt-timedelta(hours=120)}
 if event=='E1':times['reference00']=dt+timedelta(hours=6)
 for tag,t in times.items():
  path=f'{root}/truth_{event}_{tag}_v2.npz'
  assert not os.path.exists(path),path
  ti=int((t-datetime(1900,1,1)).total_seconds()/3600)
  record={'level':levels,'lat':lat,'lon':lon,'time':str(t),'source':'gs://'+ARCO.ARCO_PATH.lstrip('/')}
  for short,key in [('t','temperature'),('q','specific_humidity'),('u','u_component_of_wind'),('v','v_component_of_wind'),('z','geopotential')]:
   record[short]=np.asarray(g[key][ti,:,la,lo],dtype=np.float32)
  for short,key in [('sp','surface_pressure'),('t2m','2m_temperature'),('d2m','2m_dewpoint_temperature'),('u10m','10m_u_component_of_wind'),('v10m','10m_v_component_of_wind'),('tcwv','total_column_water_vapour')]:
   record[short]=np.asarray(g[key][ti,la,lo],dtype=np.float32)
  record['zsfc']=np.asarray(g['geopotential_at_surface'][ti,la,lo],dtype=np.float32)
  np.savez_compressed(path,**record)
  print('TRUTH_COMPLETE',event,tag,path,'shape',record['t'].shape,flush=True)
