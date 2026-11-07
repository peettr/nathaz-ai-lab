"""Extract v2 ERA5 seasonal wind for FROZEN admitted stations on Colab only."""
import csv,json,calendar,os,time
from pathlib import Path
import numpy as np,xarray as xr
root=Path('/content/site_stage_v2');p=root/'station_admission.csv'
assert p.exists(), 'ADMISSION MUST BE FROZEN BEFORE ERA5 PAIRING'
rows=[r for r in csv.DictReader(p.open()) if r['admitted']=='true'];assert rows
url='gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'
s=xr.open_zarr(url,storage_options={'token':'anon'},consolidated=True)
s=s.isel(latitude=slice(None,None,-1));slat=s.latitude.values;slon=s.longitude.values
mlat=np.sort(np.rad2deg(np.arcsin(np.polynomial.legendre.leggauss(180)[0])));mlon=np.arange(360)+.5
def edges(x,periodic=False):
 e=np.empty(len(x)+1);e[1:-1]=(x[1:]+x[:-1])/2;e[0]=x[0]-(x[1]-x[0])/2;e[-1]=x[-1]+(x[-1]-x[-2])/2
 if not periodic:e[0]=max(-90,e[0]);e[-1]=min(90,e[-1])
 return e
sy=edges(slat);sx=edges(slon,True);ty=edges(mlat);tx=edges(mlon,True)
indices=[(int(r['ace_iy']),int(r['ace_ix'])) for r in rows];i0=int(np.searchsorted(sy,min(ty[i] for i,j in indices),side='right')-1);i1=int(np.searchsorted(sy,max(ty[i+1] for i,j in indices),side='left')+1);j0=int(np.searchsorted(sx,min(tx[j] for i,j in indices),side='right')-1);j1=int(np.searchsorted(sx,max(tx[j+1] for i,j in indices),side='left')+1)
W=[]
for i,j in indices:
 yy=np.maximum(0,np.sin(np.deg2rad(np.minimum(sy[i0+1:i1+1],ty[i+1])))-np.sin(np.deg2rad(np.maximum(sy[i0:i1],ty[i]))))
 xx=np.maximum(0,np.minimum(sx[j0+1:j1+1],tx[j+1])-np.maximum(sx[j0:j1],tx[j]))
 w=yy[:,None]*xx[None,:];w/=w.sum();W.append(w.ravel())
W=np.stack(W,axis=1);assert np.allclose(W.sum(axis=0),1)
dest=root/'era_seasons.jsonl';done=set()
if dest.exists():
 for x in dest.read_text().splitlines():done.add(json.loads(x)['season_year'])
for y in range(2007,2022):
 if y in done:continue
 months=[]
 for m in (10,11,12,1,2,3):
  yr=y if m>=10 else y+1
  a=f'{yr}-{m:02d}-01T00:00:00';b=f'{yr}-{m:02d}-{calendar.monthrange(yr,m)[1]:02d}T23:59:59'
  block=s[['10m_u_component_of_wind','10m_v_component_of_wind']].sel(time=slice(a,b)).isel(latitude=slice(i0,i1),longitude=slice(j0,j1)).load();n=len(block.time)
  assert n in (112,116,120,124),(yr,m,n)
  vel=np.hypot(block['10m_u_component_of_wind'].values.reshape(n,-1)@W,block['10m_v_component_of_wind'].values.reshape(n,-1)@W)
  months.append((block.time.values,vel));print('ERA_MONTH',yr,m,n,flush=True)
 ts=np.concatenate([z[0] for z in months]);vel=np.concatenate([z[1] for z in months]);expected=np.arange(np.datetime64(f'{y}-10-01T00'),np.datetime64(f'{y+1}-04-01T00'),np.timedelta64(6,'h')).astype('datetime64[ns]')
 assert np.array_equal(ts,expected) and np.isfinite(vel).all()
 row={'season_year':y,'stations':{r['station']:{'ace1_max_mps':float(vel[:,k].max()),'max_utc':str(ts[vel[:,k].argmax()])} for k,r in enumerate(rows)},'n_6h':len(ts)}
 with dest.open('a') as f:f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
 print('ERA_DONE',y,len(ts),flush=True)
(root/'era.done').write_text(str(len(done)+sum(1 for _ in dest.open())-len(done)))
