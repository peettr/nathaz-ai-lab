"""Height-specific one-to-one matching; float IDs encode exact integers (0=empty)."""
import json,time
from pathlib import Path
import numpy as np,pandas as pd,geopandas as gpd
from pyproj import CRS,Transformer
from shapely.ops import transform
from shapely.geometry import Point
from rasterio.features import rasterize
from affine import Affine
P=Path('/content/l2613v3');D={'start':time.time()}
g=gpd.read_file(P/'PLATEAU.gpkg').to_crs('EPSG:4326')
lat,lon=37.92943,139.05260;theta=np.deg2rad(-1);c,s=np.cos(theta),np.sin(theta)
ae=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs');fwd=Transformer.from_crs('EPSG:4326',ae,always_xy=True)
def tooff(x,y):
 e,n=fwd.transform(x,y);return c*e+s*n,-s*e+c*n
offs=[transform(tooff,x) for x in g.geometry]
idsraw=np.load(P/'PLATEAU_1_ids.npy');assert np.all(np.isfinite(idsraw)) and np.all(idsraw==np.floor(idsraw))
ids=idsraw.astype(np.int32);uniq,counts=np.unique(ids,return_counts=True);size=dict(zip(uniq.tolist(),counts.tolist()))
D['id_range']=[int(uniq.min()),int(uniq.max())];D['zero_background_cells']=size.get(0,0);D['input_buildings']=len(g)
bests={};idbests={}
for k,geom in enumerate(offs):
 if geom is None or geom.is_empty:continue
 b=geom.bounds;j0=max(0,int(np.floor(b[0]+250))-2);j1=min(500,int(np.ceil(b[2]+250))+2);i0=max(0,int(np.floor(b[1]+250))-2);i1=min(500,int(np.ceil(b[3]+250))+2)
 if i1<=i0 or j1<=j0:continue
 raw=rasterize([(geom,1)],out_shape=(i1-i0,j1-j0),transform=Affine(1,0,j0-250,0,1,i0-250),dtype='uint8').astype(bool)
 if not raw.any():continue
 sub=ids[i0:i1,j0:j1];labels,n=np.unique(sub[raw],return_counts=True)
 for val,intersect in zip(labels,n):
  if val==0:continue
  intersection=int(intersect);union=int(raw.sum())+size[int(val)]-intersection
  score=intersection/union if union else 0.
  if score>bests.get(k,(-1,None))[0]:bests[k]=(score,int(val))
  if score>idbests.get(int(val),(-1,None))[0]:idbests[int(val)]=(score,k)
arrs={r:np.load(P/f'PLATEAU_{r:g}.npy',mmap_mode='r') for r in (1.,.5)}
def height(arr,x,y,r):
 i=int(np.floor((y+250)/r));j=int(np.floor((x+250)/r))
 if not(0<=i<arr.shape[0] and 0<=j<arr.shape[1]):return 0
 z=np.where(arr[i,j,:]==-3)[0];return float(z.max()*r) if len(z) else 0.
rows=[]
for k,(score,val) in bests.items():
 if score<.5 or idbests[val][1]!=k:continue
 x,y=offs[k].representative_point().coords[0];src=float(g.iloc[k]['height_direct'])
 d={'source_index':k,'building_id':str(g.iloc[k]['building_id']),'voxel_id':val,'iou':score,'measuredHeight_m':src,'x_m':x,'y_m':y}
 for r in (1.,.5):
  h=height(arrs[r],x,y,r);d[f'voxel_{r:g}m']=h;d[f'absdiff_{r:g}m']=abs(h-src);d[f'reldiff_{r:g}m']=abs(h-src)/src if src>0 else np.nan
 rows.append(d)
assert rows,'No mutual-best polygon matches'
pd.DataFrame(rows).to_csv(P/'height_matches_v3_fixed.csv',index=False)
D['matches']=len(rows);D['unmatched_fraction']=1-len(rows)/len(g)
for r in (1.,.5):
 D[f'{r:g}m']={'median_absdiff_m':float(np.median([d[f'absdiff_{r:g}m'] for d in rows])),'median_relative_diff':float(np.median([d[f'reldiff_{r:g}m'] for d in rows])),'max_absdiff_m':float(max(d[f'absdiff_{r:g}m'] for d in rows))}
a=Point(-63.3,1.6);near=[(k,z) for k,z in enumerate(offs) if z.covers(a)]
D['A_sources']=[{'building_id':str(g.iloc[k]['building_id']),'measuredHeight_m':float(g.iloc[k]['height_direct']),'voxel_1m':height(arrs[1.],-63.3,1.6,1.),'voxel_0.5m':height(arrs[.5],-63.3,1.6,.5)} for k,_ in near]
D['end']=time.time();(P/'height_v3.json').write_text(json.dumps(D,indent=2));(P/'height_v3.done').write_text('done');print('HEIGHT_DONE',D,flush=True)
