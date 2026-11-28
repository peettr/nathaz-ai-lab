"""Exact cell-overlap conservative U/V on native ACE Gaussian cells, public WB2 ERA5 0.25 deg 6-hourly.
Only eight regional point series leave the Colab VM. No prior 1.5-degree remap.
"""
import os,time,json,sys,calendar
from pathlib import Path
import numpy as np,xarray as xr
root=Path('/content/ace_formal/reference');root.mkdir(parents=True,exist_ok=True)
url='gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'
source=xr.open_zarr(url,storage_options={'token':'anon'},consolidated=True)
assert source['10m_u_component_of_wind'].encoding['chunks']==(1,721,1440)
source=source.isel(latitude=slice(None,None,-1))
ic=xr.open_dataset('/content/ace_formal/initial_conditions/ic_1979.nc')
mlat=ic.latitude.values;mlon=ic.longitude.values
frozen=json.load(open('/content/ace_formal/sites_frozen.json'))
stations={k:(frozen['stations'][k]['i'],frozen['stations'][k]['j']) for k in frozen['order']}
assert all(np.isclose(mlat[i],frozen['stations'][k]['cell_lat']) and np.isclose(mlon[j],frozen['stations'][k]['cell_lon']) for k,(i,j) in stations.items())
slat=source.latitude.values;slon=source.longitude.values
assert np.all(np.diff(slat)>0) and np.all(np.diff(slon)>0)
def edges(coords,periodic=False):
 e=np.empty(len(coords)+1,dtype='f8');e[1:-1]=(coords[:-1]+coords[1:])/2
 e[0]=coords[0]-(coords[1]-coords[0])/2;e[-1]=coords[-1]+(coords[-1]-coords[-2])/2
 if not periodic:e[0]=max(-90,e[0]);e[-1]=min(90,e[-1])
 return e
sy=edges(slat);sx=edges(slon,True);ty=edges(mlat);tx=edges(mlon,True)
# Fixed regional crop contains the 8 ACE cells plus margin.
i0=int(np.searchsorted(sy,min(ty[i] for i,j in stations.values()),side='right')-1)
i1=int(np.searchsorted(sy,max(ty[i+1] for i,j in stations.values()),side='left')+1)
j0=int(np.searchsorted(sx,min(tx[j] for i,j in stations.values()),side='right')-1)
j1=int(np.searchsorted(sx,max(tx[j+1] for i,j in stations.values()),side='left')+1)
W=[];coords={}
for name,(i,j) in stations.items():
 yy=np.maximum(0,np.sin(np.deg2rad(np.minimum(sy[i0+1:i1+1],ty[i+1])))-np.sin(np.deg2rad(np.maximum(sy[i0:i1],ty[i]))))
 xx=np.maximum(0,np.minimum(sx[j0+1:j1+1],tx[j+1])-np.maximum(sx[j0:j1],tx[j]))
 w=yy[:,None]*xx[None,:];w/=w.sum();W.append(w.ravel());coords[name]={'lat':float(mlat[i]),'lon':float(mlon[j]),'i':i,'j':j}
W=np.stack(W,axis=1);assert np.allclose(W.sum(axis=0),1)
meta=json.dumps({'source_url':url,'source_chunks':[1,721,1440],'method':'first-order area overlap: sin(latitude) * longitude for rectilinear cells; midpoint cell edges; U and V independently then norm','crop_indices':[i0,i1,j0,j1],'stations':coords,'target_latitudes':mlat.tolist(),'target_longitudes':mlon.tolist(),'order':list(stations),'weight_nonzero_per_point':(W>0).sum(axis=0).tolist()},indent=2)
metadata=root/'grid_and_weights.json'
if metadata.exists():assert metadata.read_text()==meta
else:metadata.write_text(meta)
print('WEIGHTS',i0,i1,j0,j1,coords,(W>0).sum(axis=0),flush=True)
start=int(os.environ.get('FIRST_SEASON','1980'));end=int(os.environ.get('LAST_SEASON','2009'))
for season in range(start,end+1):
 dst=root/f'cold_{season}.npz'
 if dst.exists():print('SKIP',season,flush=True);continue
 t=time.monotonic();parts=[]
 for month in [10,11,12,1,2,3]:
  year=season if month>=10 else season+1
  first=f'{year}-{month:02d}-01T00:00:00';last=f'{year}-{month:02d}-{calendar.monthrange(year,month)[1]:02d}T23:59:59'
  batch=source[['10m_u_component_of_wind','10m_v_component_of_wind']].sel(time=slice(first,last)).isel(latitude=slice(i0,i1),longitude=slice(j0,j1)).load()
  assert len(batch.time) in (112,116,120,124), (season,month,len(batch.time))
  u=batch['10m_u_component_of_wind'].values.reshape(len(batch.time),-1)@W
  v=batch['10m_v_component_of_wind'].values.reshape(len(batch.time),-1)@W
  parts.append((batch.time.values,u,v))
  print('MONTH',season,month,len(batch.time),round(time.monotonic()-t,1),flush=True)
 ts=np.concatenate([p[0] for p in parts]);u=np.concatenate([p[1] for p in parts]);v=np.concatenate([p[2] for p in parts])
 expected=np.arange(np.datetime64(f'{season}-10-01T00'),np.datetime64(f'{season+1}-04-01T00'),np.timedelta64(6,'h')).astype('datetime64[ns]')
 assert np.array_equal(ts,expected) and np.isfinite(u).all() and np.isfinite(v).all()
 np.savez_compressed(dst,time=ts,u=u.astype('f4'),v=v.astype('f4'))
 print('SEASON_DONE',season,len(ts),round(time.monotonic()-t,1),flush=True)
print('REFERENCE_DONE',end-start+1,flush=True)
