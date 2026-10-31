"""HRRR gust and same-coefficient baseline for CONUS pilot case."""
import datetime as dt,json,math,numpy as np
from pathlib import Path
from earth2studio.data import HRRR,HRRR_FX
peak=dt.datetime(2026,4,4,2,3);init=dt.datetime(2026,4,4,1);la0,lo0=35.3886,-97.6002
arr=HRRR_FX()([init],[dt.timedelta(hours=x) for x in (1,2)],['u10m','v10m','fg10m'])
la,lo=HRRR.grid();a=np.sin((np.deg2rad(la)-math.radians(la0))/2)**2+np.cos(np.deg2rad(la))*math.cos(math.radians(la0))*np.sin((np.deg2rad(lo%360)-math.radians(lo0%360))/2)**2;d=12742*np.arcsin(np.sqrt(np.minimum(a,1)))
out={'event_id':'1329296','init':'2026-04-04T01:00','peak':'2026-04-04T02:03'}
for win,r,tol in [('wide',25,1),('narrow',10,.5)]:
 for field in ('gust','speed10'):
  best=None
  for i,h in enumerate((1,2)):
   valid=init+dt.timedelta(hours=h)
   if abs((valid-peak).total_seconds())>3600*tol:continue
   if field=='gust':v=arr.sel(variable='fg10m').values[0,i]
   else:v=np.hypot(arr.sel(variable='u10m').values[0,i],arr.sel(variable='v10m').values[0,i])
   x=np.where(d<=r,v,np.nan);ij=np.unravel_index(np.nanargmax(x),x.shape)
   z={'ms':float(x[ij]),'distance_km':float(d[ij]),'valid':valid.isoformat()}
   if best is None or z['ms']>best['ms']:best=z
  out[win+'_'+field]=best
Path('/content/r2_conus_hrrr_1329296.json').write_text(json.dumps(out,indent=2));print('BASELINE',out,flush=True)
