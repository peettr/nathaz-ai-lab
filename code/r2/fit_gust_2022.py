"""Frozen scalar gust multiplier from disjoint 2022 cases, HRRR grid points."""
import csv,datetime as dt,math,json,numpy as np
from earth2studio.data import HRRR,HRRR_FX
rows=list(csv.DictReader(open('/content/fit_2022_candidates.csv')))
fx=HRRR_FX();lat,lon=HRRR.grid(); ratios=[];evidence=[]
for r in rows:
 try:
  peak=dt.datetime.fromisoformat(r['peak_candidate_utc'].replace('Z',''))
  center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0)
  init=center-dt.timedelta(hours=2)
  arr=fx([init],[dt.timedelta(hours=2)],['u10m','v10m','fg10m'])
  vals={v:arr.sel(variable=v).values[0,0] for v in ('u10m','v10m','fg10m')}
  a=np.sin((np.deg2rad(lat)-math.radians(float(r['lat'])))/2)**2+np.cos(np.deg2rad(lat))*math.cos(math.radians(float(r['lat'])))*np.sin((np.deg2rad(lon%360)-math.radians(float(r['lon'])%360))/2)**2
  d=12742*np.arcsin(np.sqrt(np.minimum(a,1)))
  speed=np.hypot(vals['u10m'],vals['v10m']);mask=(d<=25)&(speed>=5)&np.isfinite(vals['fg10m'])
  x=vals['fg10m'][mask]/speed[mask]
  if len(x)==0:continue
  med=float(np.median(x));ratios.append(med)
  evidence.append({'id':r['id'],'station':r['station'],'init':init.isoformat(),'median_grid_ratio':med,'grids':len(x),'ncei_url':r['url']})
  print('FIT',r['id'],round(med,4),len(x),flush=True)
 except Exception as ex:print('FIT_ERROR',r['id'],repr(ex),flush=True)
if len(ratios)<5:raise ValueError(f'only {len(ratios)} fit dates')
coef=float(np.median(ratios));out={'factor':coef,'cases':evidence,'method':'median of per-case median HRRR GUST/hypot(u10,v10) at forecast +2h in 25km grids with mean wind >=5m/s;2022-only'}
open('/content/r2_gust_fit_2022.json','x').write(json.dumps(out,indent=2))
print('FACTOR',coef,'N',len(ratios),flush=True)
