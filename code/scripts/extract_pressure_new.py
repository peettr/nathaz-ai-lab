"""ERA5 surface pressure, conservative area-overlap onto ACE Gaussian plains."""
import json,calendar,time
from pathlib import Path
import numpy as np,xarray as xr
from scipy.sparse import csr_matrix
R=Path('/content/ace_formal/reference'); R.mkdir(parents=True,exist_ok=True)
D=xr.open_zarr('gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr',storage_options={'token':'anon'},consolidated=True).isel(latitude=slice(None,None,-1))
ic=xr.open_dataset('/content/ace_formal/initial_conditions/ic_1979.nc');lat=ic.latitude.values;lon=ic.longitude.values
I=np.flatnonzero((lat>=35)&(lat<=48));J=np.flatnonzero((lon>=255)&(lon<=272));assert len(I)>10 and len(J)>10
assert np.array_equal(I,np.arange(I[0],I[-1]+1)) and np.array_equal(J,np.arange(J[0],J[-1]+1))
def edges(x,periodic=False):
 e=np.r_[x[0]-(x[1]-x[0])/2,(x[:-1]+x[1:])/2,x[-1]+(x[-1]-x[-2])/2]
 if not periodic:e[0]=max(-90,e[0]);e[-1]=min(90,e[-1])
 return e
Y=edges(D.latitude.values);X=edges(D.longitude.values,True);y=edges(lat);x=edges(lon,True)
i0=np.searchsorted(Y,y[I[0]],side='right')-1;i1=np.searchsorted(Y,y[I[-1]+1],side='left')+1
j0=np.searchsorted(X,x[J[0]],side='right')-1;j1=np.searchsorted(X,x[J[-1]+1],side='left')+1
rows=[];cols=[];values=[]
for n,(i,j) in enumerate((i,j) for i in I for j in J):
 a=np.maximum(0,np.sin(np.deg2rad(np.minimum(Y[i0+1:i1+1],y[i+1])))-np.sin(np.deg2rad(np.maximum(Y[i0:i1],y[i]))))
 b=np.maximum(0,np.minimum(X[j0+1:j1+1],x[j+1])-np.maximum(X[j0:j1],x[j]))
 w=np.outer(a,b);w/=w.sum();rr,cc=np.nonzero(w)
 rows.extend([n]*len(rr));cols.extend((rr*(j1-j0)+cc).tolist());values.extend(w[rr,cc].tolist())
W=csr_matrix((values,(rows,cols)),shape=(len(I)*len(J),(i1-i0)*(j1-j0)))
assert np.allclose(np.asarray(W.sum(axis=1)).ravel(),1)
meta={'source':'WeatherBench2 ERA5 0.25 degree surface_pressure Pa','target':'ACE2 Gaussian 1 degree PRESsfc grid','lat':lat[I].tolist(),'lon':lon[J].tolist(),'source_crop':[int(i0),int(i1),int(j0),int(j1)],'method':'first-order spherical area overlap; cell edges midpoints'}
(R/'pressure_grid.json').write_text(json.dumps(meta,indent=2))
for season in range(1980,2010):
 target=R/f'pressure_{season}.npz'
 if target.exists():print('PRESSURE_SKIP',season,flush=True);continue
 t=time.monotonic();parts=[]
 for month in [10,11,12,1,2,3]:
  year=season+(month<=3)
  s=f'{year}-{month:02d}-01';end=f'{year}-{month:02d}-{calendar.monthrange(year,month)[1]:02d}T23:59:59'
  batch=D.surface_pressure.sel(time=slice(s,end)).isel(latitude=slice(i0,i1),longitude=slice(j0,j1)).load()
  p=([邮箱](len(batch.time),-1).T).T.astype('f4')
  assert p.shape==(len(batch.time),len(I)*len(J)) and np.isfinite(p).all()
  parts.append((batch.time.values,p));print('PRESSURE_MONTH',season,month,len(batch.time),round(time.monotonic()-t,1),flush=True)
 ts=np.concatenate([q[0] for q in parts]);p=np.concatenate([q[1] for q in parts]);expected=np.arange(np.datetime64(f'{season}-10-01T00'),np.datetime64(f'{season+1}-04-01T00'),np.timedelta64(6,'h')).astype('datetime64[ns]')
 assert np.array_equal(ts,expected)
 np.savez_compressed(target,time=ts,pressure=p)
 print('PRESSURE_SEASON_DONE',season,round(time.monotonic()-t,1),flush=True)
# Equal weighting of all 6-hourly cold-season instants for grid-cell climatology.
files=[np.load(R/f'pressure_{y}.npz') for y in range(1980,2010)]
clim=np.sum([f['pressure'].sum(axis=0,dtype='f8') for f in files],axis=0)/sum(len(f['pressure']) for f in files)
mins=[{'season':y,'minimum_anomaly_pa':float((f['pressure']-clim).min())} for y,f in zip(range(1980,2010),files)]
(R/'pressure_minima.json').write_text(json.dumps({'climatology_period':'1980/81–2009/10, complete cold seasons','rows':mins,'grid':meta},indent=2))
print('PRESSURE_DONE',len(mins),flush=True)
