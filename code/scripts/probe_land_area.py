import json,numpy as np,xarray as xr
u='gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'
d=xr.open_zarr(u,storage_options={'token':'anon'},consolidated=True)
a=json.load(open('/content/ace_formal/reference/grid_and_weights.json'))
i0,i1,j0,j1=a['crop_indices'];land=d.land_sea_mask.isel(latitude=slice(721-i1,721-i0),longitude=slice(j0,j1)).values[::-1].ravel()
sy=np.asarray(a['target_latitudes']);sx=np.asarray(a['target_longitudes']);y=np.arange(-90,90.25,.25);x=np.arange(0,360,.25)
def edge(v):return np.r_[v[0]-(v[1]-v[0])/2,(v[1:]+v[:-1])/2,v[-1]+(v[-1]-v[-2])/2]
y0=edge(y);x0=edge(x);yt=edge(sy);xt=edge(sx)
for name in a['order']:
 i=a['stations'][name]['i'];j=a['stations'][name]['j']
 wy=np.maximum(0,np.sin(np.deg2rad(np.minimum(y0[i0+1:i1+1],yt[i+1])))-np.sin(np.deg2rad(np.maximum(y0[i0:i1],yt[i]))));wx=np.maximum(0,np.minimum(x0[j0+1:j1+1],xt[j+1])-np.maximum(x0[j0:j1],xt[j]));w=np.outer(wy,wx).ravel();w/=w.sum();print('AREA_LAND',name,float(w@land),flush=True)
