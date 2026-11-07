"""ERA5 WB2 0.25-deg U/V conservative native ACE2 Gaussian cell extraction, Colab CPU."""
import sys,time,json,calendar
from pathlib import Path
import numpy as np,xarray as xr
from run_colab import ROOT,ALL,GRID
url='gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'
s=xr.open_zarr(url,storage_options={'token':'anon'},consolidated=True)
assert s['10m_u_component_of_wind'].encoding['chunks']==(1,721,1440)
s=s.isel(latitude=slice(None,None,-1))
slat=s.latitude.values;slon=s.longitude.values
# Same ACE Gaussian latitude as model IC. Confirm against independent frozen cell coordinates.
mlat=np.sort(np.rad2deg(np.arcsin(np.polynomial.legendre.leggauss(180)[0])))
mlon=np.arange(360)+.5
assert abs(mlat[137]-47.368182269015726)<1e-5 and abs(mlat[131]-41.384849548339844)<1e-5

def edges(x,periodic=False):
 e=np.empty(len(x)+1);e[1:-1]=(x[1:]+x[:-1])/2;e[0]=x[0]-(x[1]-x[0])/2;e[-1]=x[-1]+(x[-1]-x[-2])/2
 if not periodic:e[0]=max(-90,e[0]);e[-1]=min(90,e[-1])
 return e
sy=edges(slat);sx=edges(slon,True);ty=edges(mlat);tx=edges(mlon,True)
i0=int(np.searchsorted(sy,min(ty[i] for i,j in GRID.values()),side='right')-1)
i1=int(np.searchsorted(sy,max(ty[i+1] for i,j in GRID.values()),side='left')+1)
j0=int(np.searchsorted(sx,min(tx[j] for i,j in GRID.values()),side='right')-1)
j1=int(np.searchsorted(sx,max(tx[j+1] for i,j in GRID.values()),side='left')+1)
W=[];nearest=[]
for st in ALL:
 i,j=GRID[st]
 yy=np.maximum(0,np.sin(np.deg2rad(np.minimum(sy[i0+1:i1+1],ty[i+1])))-np.sin(np.deg2rad(np.maximum(sy[i0:i1],ty[i]))))
 xx=np.maximum(0,np.minimum(sx[j0+1:j1+1],tx[j+1])-np.maximum(sx[j0:j1],tx[j]))
 w=yy[:,None]*xx[None,:];w/=w.sum();W.append(w.ravel())
 # Nearest 0.25-degree cell to station itself for sensitivity.
 from run_colab import COORD
 lat,lon=COORD[st];nearest.append((int(np.argmin(abs(slat-lat)))-i0,int(np.argmin(abs(slon-(lon%360))))-j0))
W=np.stack(W,axis=1);assert np.allclose(W.sum(axis=0),1)
ROOT.joinpath('era_grid.json').write_text(json.dumps({'source_url':url,'method':'native ACE Gaussian cell U/V first-order sin(latitude)*longitude area overlap; magnitude after remapping','crop':[i0,i1,j0,j1],'indices':GRID,'stations':ALL,'nearest_025_index_in_crop':nearest,'nonzero_weights':(W>0).sum(axis=0).tolist()},indent=2))
print('ERA_GRID',i0,i1,j0,j1,flush=True)
dest=ROOT/'era_seasons.jsonl';done=set()
if dest.exists():
 for z in dest.read_text().splitlines():done.add(json.loads(z)['season_year'])
for y in range(2000,2022):
 if y in done:continue
 started=time.monotonic();months=[]
 for m in (10,11,12,1,2,3):
  yr=y if m>=10 else y+1
  a=f'{yr}-{m:02d}-01T00:00:00';b=f'{yr}-{m:02d}-{calendar.monthrange(yr,m)[1]:02d}T23:59:59'
  block=s[['10m_u_component_of_wind','10m_v_component_of_wind']].sel(time=slice(a,b)).isel(latitude=slice(i0,i1),longitude=slice(j0,j1)).load()
  n=len(block.time);assert n in (112,116,120,124),(yr,m,n)
  u=block['10m_u_component_of_wind'].values;v=block['10m_v_component_of_wind'].values
  uv=u.reshape(n,-1)@W;vv=v.reshape(n,-1)@W
  nv=np.stack([np.hypot(u[:,i,j],v[:,i,j]) for i,j in nearest],axis=1)
  months.append((block.time.values,np.hypot(uv,vv),nv))
  print('ERA_MONTH',yr,m,n,round(time.monotonic()-started,1),flush=True)
 ts=np.concatenate([z[0] for z in months]);vel=np.concatenate([z[1] for z in months]);near=np.concatenate([z[2] for z in months]);expected=np.arange(np.datetime64(f'{y}-10-01T00'),np.datetime64(f'{y+1}-04-01T00'),np.timedelta64(6,'h')).astype('datetime64[ns]')
 assert np.array_equal(ts,expected) and np.isfinite(vel).all() and np.isfinite(near).all()
 row={'season_year':y,'stations':{st:{'ace1_max_mps':float(vel[:,k].max()),'nearest025_max_mps':float(near[:,k].max()),'max_utc':str(ts[vel[:,k].argmax()])} for k,st in enumerate(ALL)},'n_6h':len(ts)}
 with dest.open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
 print('ERA_DONE',y,len(ts),round(time.monotonic()-started,1),flush=True)
ROOT.joinpath('era.done').write_text(json.dumps({'seasons':len(done)+sum(1 for _ in dest.open())-len(done),'expected':22}))
