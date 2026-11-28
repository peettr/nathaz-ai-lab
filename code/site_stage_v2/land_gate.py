"""ACE2 Gaussian cell land fraction from WB2 ERA5 0.25 degree land_sea_mask."""
import csv,json,numpy as np,xarray as xr
from pathlib import Path
root=Path('/content/site_stage_v2');rows=list(csv.DictReader((root/'geography.csv').open()))
u='gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'
s=xr.open_zarr(u,storage_options={'token':'anon'},consolidated=True)
v=s['land_sea_mask'];print('lsm dims',v.dims,'attrs',dict(v.attrs),flush=True)
if 'time' in v.dims:v=v.isel(time=0)
lat=np.asarray(s.latitude.values);lon=np.asarray(s.longitude.values)
if lat[0]>lat[-1]:lat=lat[::-1];v=v.isel(latitude=slice(None,None,-1))
mlat=np.sort(np.rad2deg(np.arcsin(np.polynomial.legendre.leggauss(180)[0])));mlon=np.arange(360)+.5
def edge(x,clip=False):
 e=np.empty(len(x)+1);e[1:-1]=(x[1:]+x[:-1])/2;e[0]=x[0]-(x[1]-x[0])/2;e[-1]=x[-1]+(x[-1]-x[-2])/2
 if clip:e[0]=max(-90,e[0]);e[-1]=min(90,e[-1])
 return e
sy=edge(lat,True);sx=edge(lon);ty=edge(mlat,True);tx=edge(mlon)
for r in rows:
 try:
  iy=int(np.argmin(abs(mlat-float(r['lat']))));jx=int(np.argmin(abs(((mlon-float(r['lon']))+180)%360-180)));jy=int(np.argmin(abs(lon-mlon[jx])));
  i0=max(0,np.searchsorted(sy,ty[iy])-1);i1=min(len(lat),np.searchsorted(sy,ty[iy+1])+1);j0=max(0,np.searchsorted(sx,tx[jx])-1);j1=min(len(lon),np.searchsorted(sx,tx[jx+1])+1)
  yy=np.maximum(0,np.sin(np.deg2rad(np.minimum(sy[i0+1:i1+1],ty[iy+1])))-np.sin(np.deg2rad(np.maximum(sy[i0:i1],ty[iy]))))
  xx=np.maximum(0,np.minimum(sx[j0+1:j1+1],tx[jx+1])-np.maximum(sx[j0:j1],tx[jx]))
  w=yy[:,None]*xx[None,:];block=v.isel(latitude=slice(i0,i1),longitude=slice(j0,j1)).values
  if block.ndim!=2:raise ValueError(('land mask dims',block.shape))
  frac=float(np.sum(block*w)/w.sum());r.update(ace_lat=str(mlat[iy]),ace_lon=str(mlon[jx]),ace_iy=str(iy),ace_ix=str(jx),land_fraction=str(frac),land_ok=str(frac>=.5).lower())
 except Exception as e:r['land_error']=repr(e)
fields=list(rows[0]);fields+=['ace_lat','ace_lon','ace_iy','ace_ix','land_fraction','land_ok','land_error']
with (root/'static_gates.csv').open('w',newline='') as f:w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
for g in ('plains','other'):
 q=[r for r in rows if r['region']==g and all(r.get(k)=='true' for k in ('instrument_ok','relocation_ok','elevation_ok','geog_ok','land_ok'))];print(g,len(q),[(r['station'],round(float(r['land_fraction']),3)) for r in q],flush=True)
print('errors',[(r['station'],r.get('land_error')) for r in rows if r.get('land_error')],flush=True)
