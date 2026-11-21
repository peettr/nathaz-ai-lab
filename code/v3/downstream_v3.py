"""PLATEAU post-gate diagnostics; identical geometric definitions to v2."""
import time,json,traceback,hashlib
from pathlib import Path
P=Path('/content/l2613v3');G=json.loads((P/'generation.json').read_text());assert G['gate_pass'] and not G.get('error'),'Gate required'
D={'start':time.time(),'source':'PLATEAU','gate':G['gate']}
def save(): (P/'downstream.json').write_text(json.dumps(D,indent=2,ensure_ascii=False,default=str))
def log(*x):print(time.strftime('%H:%M:%S'),*x,flush=True);D['stage']=' '.join(map(str,x));save()
try:
 import numpy as np,pandas as pd,geopandas as gpd,trimesh,requests
 from pyproj import CRS,Transformer
 from shapely.ops import transform,polygonize
 from shapely.geometry import Polygon,LineString
 from scipy.ndimage import label,distance_transform_edt,binary_erosion
 from scipy.spatial import cKDTree
 from skimage.morphology import skeletonize
 from rasterio.features import rasterize
 from affine import Affine
 lat,lon=37.92943,139.05260;theta=np.deg2rad(-1);c,s=np.cos(theta),np.sin(theta)
 ll=CRS.from_epsg(4326);ae=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs');fwd=Transformer.from_crs(ll,ae,always_xy=True)
 def tooff(x,y):
  e,n=fwd.transform(x,y);return c*e+s*n,-s*e+c*n
 def mask(gs,step=.25,half=205):
  n=round(2*half/step);return rasterize([(g,1) for g in gs if g is not None and not g.is_empty],out_shape=(n,n),transform=Affine(step,0,-half,0,step,-half),dtype='uint8').astype(bool)
 g=gpd.read_file(P/'PLATEAU.gpkg').to_crs(ll);offs=[transform(tooff,z) for z in g.geometry];off=mask(offs,1,250)
 a=np.load(P/'PLATEAU_1.npy',mmap_mode='r');v=np.asarray(a[:,:,2]==-3)
 h1=np.load(P/'PLATEAU_1_heights.npy',mmap_mode='r')
 h05=np.load(P/'PLATEAU_0.5_heights.npy',mmap_mode='r')
 D['height_grid_shape']={'1':h1.shape,'.5':h05.shape};D['height_grid_max']={'1':float(np.nanmax(h1)),'.5':float(np.nanmax(h05))};save()
 log('official slice')
 p=P/'BD_caseE.stl'
 if not p.exists():
  r=requests.get('https://zenodo.org/records/15429018/files/BD_caseE.stl?download=1',timeout=180);r.raise_for_status();p.write_bytes(r.content)
 mesh=trimesh.load(p,force='mesh',process=False);mesh.apply_scale(250)
 sec=mesh.section(plane_origin=[0,0,2],plane_normal=[0,0,1]);assert sec is not None
 seg=sec.discrete;polys=list(polygonize([LineString(q[:,:2]) for q in seg if len(q)>2]));assert polys
 official=mask(polys);xy=(np.arange(1640)+.5)*.25-205;xx,yy=np.meshgrid(xy,xy);rad=np.hypot(xx,yy)<200
 D['official']={'section_paths':len(seg),'polygons':len(polys),'bounds':mesh.bounds.tolist()}
 ix=np.clip(np.floor(xx+250).astype(int),0,499);iy=np.clip(np.floor(yy+250).astype(int),0,499)
 vv=v[iy,ix];uu=off[iy,ix];oa=official&rad;va=vv&rad;ua=uu&rad
 def boundary(x,y):
  aa=np.argwhere(x^binary_erosion(x));bb=np.argwhere(y^binary_erosion(y));return float(np.median(np.r_[cKDTree(bb).query(aa)[0],cKDTree(aa).query(bb)[0]])*.25)
 D['boundary_voxel_official_m']=boundary(oa,va);D['boundary_upstream_official_m']=boundary(oa,ua)
 dist=distance_transform_edt(~official)*.25;sk=skeletonize((~official)&rad)&(dist*2<4)
 groups,num=label(sk,structure=np.ones((3,3),dtype=int));segments=[]
 for n in range(1,num+1):
  pts=np.argwhere(groups==n);length=len(pts)*.25
  if length>=10:segments.append((n,pts,length))
 D['segment_count']=len(segments);dv=distance_transform_edt(~vv)*.25;du=distance_transform_edt(~uu)*.25
 rows=[];width_err=[]
 for sid,pts,length in segments:
  rr,cc=pts.T;ofw=2*dist[rr,cc];vow=2*dv[rr,cc];width_err.extend(abs(ofw-vow).tolist())
  corridor=distance_transform_edt(groups!=sid)*.25<=2;components,_=label(corridor&~vv,structure=np.ones((3,3),dtype=int));e0=components[rr[0],cc[0]];e1=components[rr[-1],cc[-1]];connected=bool(e0 and e0==e1)
  rows.append({'source':'PLATEAU','segment':sid,'length_m':length,'official_width_m':float(np.median(ofw)),'voxel_width_m':float(np.median(vow)),'connected':connected,'upstream_centerline_blocked':bool(np.any(uu[rr,cc])),'upstream_width_m':float(np.median(2*du[rr,cc]))})
 pd.DataFrame(rows).to_csv(P/'streets_v3.csv',index=False);D['width_abs_median_m']=float(np.median(width_err));D['blocked_count']=sum(not x['connected'] for x in rows);D['upstream_centerline_blocked_count']=sum(x['upstream_centerline_blocked'] for x in rows)
 log('points')
 pt=pd.read_csv(P/'RS_caseE.csv');pt=pt[pt['case']=='ac'].drop_duplicates(['x(m)','y(m)']);assert len(pt)==80
 prow=[]
 for _,q in pt.iterrows():
  x=float(q['x(m)']);y=float(q['y(m)']);i=int(np.floor(y+250));j=int(np.floor(x+250));r=int(np.floor((y+205)/.25));col=int(np.floor((x+205)/.25))
  prow.append({'source':'PLATEAU','point_id':q['No.'],'x_m':x,'y_m':y,'voxel':bool(v[i,j]),'official':bool(official[r,col]) if 0<=r<1640 and 0<=col<1640 else False,'upstream':bool(off[i,j])})
 pd.DataFrame(prow).to_csv(P/'points_v3.csv',index=False)
 D['points']={k:sum(x[k] for x in prow) for k in ['voxel','official','upstream']}
 log('official roof components')
 roof=pd.read_csv(P/'official_roofs_reference.csv');assert len(roof)>0
 def colheight(arr,x,y,r):
  i=int(np.floor((y+250)/r));j=int(np.floor((x+250)/r))
  if not(0<=i<arr.shape[0] and 0<=j<arr.shape[1]):return 0.
  # voxel top: k starts with solid floor at index 1, i.e. voxel top=(max_k+0)*r
  k=np.where(arr[i,j,:]==-3)[0];return float(k.max()*r) if len(k) else 0.
 roof['PLATEAU_height_m']=[colheight(a,x,y,1) for x,y in zip(roof.x_m,roof.y_m)]
 roof['PLATEAU_absdiff_m']=(roof.roof_m-roof.PLATEAU_height_m).abs();roof.to_csv(P/'official_roofs_v3.csv',index=False)
 D['roofs']=len(roof)
 D['A']={'x':-63.3,'y':1.6,'official_m':60,'voxel_1m':colheight(a,-63.3,1.6,1),'voxel_0.5m':colheight(np.load(P/'PLATEAU_0.5.npy',mmap_mode='r'),-63.3,1.6,.5)}
 # ID correspondence: rasterized raw source footprints and voxel individual IDs;
 # positive ID encodes rasterized feature; measure polygon IoU against each ID in its bounding box.
 log('height correspondence')
 ids=np.load(P/'PLATEAU_1_ids.npy',allow_pickle=True);D['ids_grid_dtype']=str(ids.dtype);D['ids_grid_shape']=ids.shape
 # Rely on spatial association only, and demand mutual-best IoU≥0.5. A generated grid ID may be different from raw index.
 # Slice candidate IDs by footprint bbox then compare each ID mask with its source footprint mask in a padded local box.
 matches=[]
 if ids.ndim==2 and ids.dtype.kind in 'iu':
  uniq,counts=np.unique(ids,return_counts=True);D['id_sample']=list(zip(uniq[:12].tolist(),counts[:12].tolist()))
  source_masks=[]; candidates={};n=len(g)
  for k,geom in enumerate(offs):
   if geom is None or geom.is_empty:continue
   bounds=geom.bounds;j0=max(0,int(np.floor(bounds[0]+250))-2);j1=min(500,int(np.ceil(bounds[2]+250))+2);i0=max(0,int(np.floor(bounds[1]+250))-2);i1=min(500,int(np.ceil(bounds[3]+250))+2)
   if j1<=j0 or i1<=i0:continue
   raw=rasterize([(geom,1)],out_shape=(i1-i0,j1-j0),transform=Affine(1,0,j0-250,0,1,i0-250),dtype='uint8').astype(bool)
   idloc=ids[i0:i1,j0:j1];source_masks.append((k,(i0,i1,j0,j1),int(raw.sum())))
   for val in np.unique(idloc[raw]):
    if val<0:continue
    # global size for this feature ID to avoid inflated IoU on a cropped grid
    intersection=int(((idloc==val)&raw).sum());union=int(counts[np.searchsorted(uniq,val)])+int(raw.sum())-intersection
    ratio=intersection/union if union else 0
    if ratio>0:candidates[(k,int(val))]=ratio
  best_raw={};best_id={}
  for (k,id_),score in candidates.items():
   if score>best_raw.get(k,(-1,None))[0]:best_raw[k]=(score,id_)
   if score>best_id.get(id_,(-1,None))[0]:best_id[id_]=(score,k)
  for k,(score,id_) in best_raw.items():
   if score<.5 or best_id[id_][1]!=k:continue
   geom=offs[k];x,y=geom.representative_point().coords[0];src_height=float(g.iloc[k]['height_direct'])
   measured={r:colheight(np.load(P/f'PLATEAU_{r:g}.npy',mmap_mode='r'),x,y,r) for r in [1,.5]}
   matches.append({'index':k,'building_id':str(g.iloc[k].get('building_id')),'voxel_id':id_,'iou':score,'measuredHeight_m':src_height,'voxel_1m':measured[1],'voxel_0.5m':measured[.5],'absdiff_1m':abs(measured[1]-src_height),'absdiff_0.5m':abs(measured[.5]-src_height)})
 else:D['height_match_issue']='ID grid is not 2D integer array'
 pd.DataFrame(matches).to_csv(P/'height_matches_v3.csv',index=False)
 D['matches']=len(matches);D['unmatched_fraction']=1-len(matches)/G['direct_height_count'] if G['direct_height_count'] else None
 D['median_absdiff_1m']=float(np.median([m['absdiff_1m'] for m in matches])) if matches else None
 D['median_absdiff_0.5m']=float(np.median([m['absdiff_0.5m'] for m in matches])) if matches else None
 D['A']['measuredHeight']=next((float(g.iloc[k]['height_direct']) for k,geom in enumerate(offs) if geom.contains(__import__('shapely').geometry.Point(-63.3,1.6))),None)
 D['end']=time.time();log('finished')
except Exception as e:
 D['error']=repr(e);D['traceback']=traceback.format_exc();log('ERROR',repr(e))
finally:
 D['end']=time.time();save();(P/'downstream.done').write_text('done');print('DOWNSTREAM_DONE',D.get('error','ok'),flush=True)
