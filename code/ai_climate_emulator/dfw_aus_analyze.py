"""Paired 1979–2008 ACE2/ERA5 DFW/AUS six-hourly point check."""
from pathlib import Path
import json
import numpy as np,xarray as xr,pandas as pd
from scipy.stats import gumbel_r
out=Path('/content/dfw_aus_analysis');out.mkdir(exist_ok=False)
m=Path('/content/ace2_runs/dfw_aus_historical_1979_2008')
assert json.loads((m/'exit.json').read_text())['returncode']==0
points=json.loads(Path('/content/dfw_aus_era5/points.json').read_text())
d=xr.open_dataset(m/'autoregressive_predictions.nc')
assert d.sizes['time']==43832
for p in points:
 assert abs(float(d.lat.values[p['i']])-p['grid_lat'])<1e-4
 assert abs(float(d.lon.values[p['j']])-p['grid_lon'])<1e-4
sel={'lat':xr.DataArray([p['i'] for p in points],dims='station'),'lon':xr.DataArray([p['j'] for p in points],dims='station')}
t=d.valid_time.values[0]
valid=t<np.datetime64('2009-01-01T00:00:00')
t=t[valid]
assert len(t)==43831 and t[0]==np.datetime64('1979-01-01T06:00:00')
a=np.hypot(d.UGRD10m.isel(sample=0,**sel).transpose('time','station').values[valid],d.VGRD10m.isel(sample=0,**sel).transpose('time','station').values[valid])
rt=[];ru=[];rv=[]
for y in range(1979,2009):
 z=np.load(f'/content/dfw_aus_era5/era5_{y}.npz')
 rt.append(z['time']);ru.append(z['u']);rv.append(z['v'])
rt=np.concatenate(rt);ru=np.concatenate(ru);rv=np.concatenate(rv)
ix=np.searchsorted(rt,t)
assert np.array_equal(rt[ix],t)
b=np.hypot(ru[ix],rv[ix]);assert a.shape==b.shape==(43831,2) and np.isfinite(a).all() and np.isfinite(b).all()
years=t.astype('datetime64[Y]').astype(int)+1970
assert sorted(set(years))==list(range(1979,2009))
rows=[]
for j,p in enumerate(points):
 x=a[:,j];z=b[:,j]
 am=np.array([x[years==y].max() for y in range(1979,2009)])
 bm=np.array([z[years==y].max() for y in range(1979,2009)])
 def stat(v):
  loc,scale=gumbel_r.fit(v)
  return [np.median(v),np.quantile(v,.9),gumbel_r.ppf(.98,loc=loc,scale=scale),v.mean()]
 sa=stat(am);sb=stat(bm)
 row={**p,'n_years':30,'n_paired_steps':len(t),'ace_mean_speed':x.mean(),'era_mean_speed':z.mean(),'mean_speed_bias_pct':100*(x.mean()/z.mean()-1)}
 for name,aa,bb in zip(['annual_max_median','annual_max_p90','gumbel_50yr','annual_max_mean'],sa,sb):
  row['ace_'+name]=aa;row['era_'+name]=bb;row[name+'_bias_pct']=100*(aa/bb-1)
 rows.append(row)
 np.savez_compressed(out/f"points_{p['station_anchor']}.npz",time=t,ace=x.astype('f4'),era=z.astype('f4'),annual_max_ace=am.astype('f4'),annual_max_era=bm.astype('f4'))
df=pd.DataFrame(rows);df.to_csv(out/'metrics_dfw_aus.csv',index=False,float_format='%.5f')
print(df[['station_anchor','grid_lat','grid_lon','mean_speed_bias_pct','annual_max_median_bias_pct','annual_max_p90_bias_pct','gumbel_50yr_bias_pct']].to_string(index=False),flush=True)
print('ANALYSIS_DONE',len(df),len(t),flush=True)
