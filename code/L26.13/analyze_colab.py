import os,time,json,hashlib,traceback,math
from pathlib import Path
import numpy as np,pandas as pd,trimesh,requests
from PIL import Image,ImageDraw
from scipy.ndimage import label,distance_transform_edt,map_coordinates,binary_erosion
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize
from skimage.measure import marching_cubes
P=Path('/content/l2613'); D={}; t0=time.time()
def save(): (P/'analysis.json').write_text(json.dumps(D,indent=2,ensure_ascii=False,default=str))
try:
 while not (P/'run.done').exists(): time.sleep(10)
 M=json.loads((P/'metrics.json').read_text()); D['base_run']=M
 # binary official STL (model metres) and original source points
 for f in ('BD_caseE.stl','RS_caseE.csv'):
  if not (P/f).exists():
   u=f'https://zenodo.org/records/15429018/files/{f}?download=1'
   r=requests.get(u,timeout=180);r.raise_for_status();(P/f).write_bytes(r.content)
 mesh=trimesh.load(P/'BD_caseE.stl',force='mesh',process=False)
 v=np.asarray(mesh.vertices)*250
 D['official']={'source':'Zenodo 15429018','raw_bounds':np.asarray(mesh.bounds).tolist(),'prototype_bounds':np.array([v.min(0),v.max(0)]).tolist(),'triangles':len(mesh.faces),'watertight':bool(mesh.is_watertight)}
 df=pd.read_csv(P/'RS_caseE.csv');D['RS_columns']=list(df.columns);D['RS_cases']=df['case'].value_counts(dropna=False).to_dict()
 pts=df[df['case']=='ac']; cols={str(c).strip().lower():c for c in df.columns}
 xcol=cols.get('x');ycol=cols.get('y');D['RS_unique_coordinates']=int(len(pts[[xcol,ycol]].drop_duplicates())) if xcol and ycol else None
 # official roof triangles to 0.25m 2D raster, 200m radius
 faces=v[mesh.faces]; n=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]); n/=np.linalg.norm(n,axis=1,keepdims=True)+1e-20
 roofs=(np.abs(n[:,2])>.9)&(faces[:,:,2].min(axis=1)>.5)
 tris=faces[roofs]; step=.25; half=205; N=int(2*half/step)
 image=Image.new('1',(N,N));draw=ImageDraw.Draw(image)
 for tri in tris: draw.polygon([((x+half)/step,(y+half)/step) for x,y,z in tri],fill=1)
 official=np.asarray(image,dtype=bool); rad=np.hypot(*np.meshgrid((np.arange(N)+.5)*step-half,(np.arange(N)+.5)*step-half,indexing='xy'))<=200
 D['official']['roof_triangles']=len(tris);D['official']['roof_components']=int(label(official)[1]);save()
 # fixed rotation official->world -1deg; inverse rotate world->official +1deg
 c,s=np.cos(np.deg2rad(-1)),np.sin(np.deg2rad(-1))
 def world(x,y): return c*x-s*y,s*x+c*y
 def official_xy(x,y): return c*x+s*y,-s*x+c*y
 # north-aligned downloaded grid; x axis east, y north
 for src in ('OpenStreetMap','Overture'):
  for res in (1,.5):
   key=f'{src}_{res:g}m'
   if key not in M or 'error' in M[key]:continue
   z=np.load(P/(key+'.npz'));bh=z['heights'];ids=z['ids'];src2=z['slice2'].astype(bool)
   ni=500 if res==1 else 1000
   yy,xx=np.meshgrid((np.arange(ni)+.5)*res-250,(np.arange(ni)+.5)*res-250,indexing='ij')
   # Source array is [east,north] from raster core, origin world -255, -255
   wx,wy=world(xx,yy)
   u=(wx+255)/res-.5; w=(wy+255)/res-.5
   localh=map_coordinates(bh,[u,w],order=0,mode='constant',cval=0)
   local2=map_coordinates(src2.astype('uint8'),[u,w],order=0,mode='constant',cval=0).astype(bool)
   D[key]={'generated_original_shape':bh.shape,'local_shape':localh.shape,'rotated_nonzero':int((localh>0).sum()),'local_height_max':float(localh.max()),'postprocess':'nearest-neighbor rotation and 500m crop; external, not VoxCity native'}
   if res==1:
    # points relative to official origin; true z=2m
    if xcol and ycol:
     q=pts[[xcol,ycol]].drop_duplicates().astype(float).to_numpy()
     ix=np.floor((q[:,0]+250)/res).astype(int);iy=np.floor((q[:,1]+250)/res).astype(int)
     good=(ix>=0)&(ix<ni)&(iy>=0)&(iy<ni)
     D[key]['RS_points_in_building_z2']=int(np.count_nonzero(good & local2[np.clip(iy,0,ni-1),np.clip(ix,0,ni-1)]))
     D[key]['RS_points_total']=len(q)
    # create own binary voxel STL with marching cubes, cap 50 MB checked
    occ=np.zeros((ni+2,ni+2,13),dtype=np.uint8)
    for k in range(10): occ[1:-1,1:-1,k+1]=(localh>k+.5)
    verts,faces_stl,_,_=marching_cubes(occ,level=.5,spacing=(1,1,1));verts[:,0]-=1;verts[:,1]-=1;verts[:,2]-=1
    # coords mesh array [north,east,z], move to [east,north,z]
    verts=verts[:,[1,0,2]]
    stl=trimesh.Trimesh(vertices=verts,faces=faces_stl,process=False)
    fpath=P/(src+'_1m.stl'); stl.export(fpath)
    D[key]['stl']={'bytes':fpath.stat().st_size,'sha256':hashlib.sha256(fpath.read_bytes()).hexdigest(),'watertight':bool(trimesh.load(fpath,force='mesh').is_watertight),'bounds':np.asarray(stl.bounds).tolist(),'written':time.time(),'method':'own marching cubes of VoxCity height raster; not native OBJ->STL'}
    # official 2m roof proxy raster vs source 2m slice in central circle
    xg,yg=np.meshgrid((np.arange(N)+.5)*step-half,(np.arange(N)+.5)*step-half,indexing='xy')
    ox=np.floor((xg+250)).astype(int);oy=np.floor((yg+250)).astype(int)
    vc=local2[np.clip(oy,0,ni-1),np.clip(ox,0,ni-1)]
    oa=official&rad;va=vc&rad
    ob=oa^binary_erosion(oa);vb=va^binary_erosion(va)
    if ob.any() and vb.any():
     a=np.argwhere(ob)*step;b=np.argwhere(vb)*step
     d1=cKDTree(b).query(a,k=1)[0];d2=cKDTree(a).query(b,k=1)[0]
     D[key]['boundary_bidirectional_median_m']=float(np.median(np.r_[d1,d2]))
    sk=skeletonize((~official)&rad); dist=distance_transform_edt(~official)*step
    narrow=sk&(dist*2<4)&rad; seg,nseg=label(narrow)
    keep=np.zeros_like(narrow)
    for k in range(1,nseg+1):
     if (seg==k).sum()*step>=10:keep|=(seg==k)
    D[key]['narrow_proxy']={'skeleton_pixels':int(keep.sum()),'segments':int(len(set(seg[keep]))-(1 if 0 in seg[keep] else 0)),'width_median_abs_error_m':float(np.median(abs(2*dist[keep]-2*distance_transform_edt(~vc)[keep]*step))) if keep.any() else None,'blocked_samples':int((keep&vc).sum()),'caveat':'roof footprint proxy, not prescribed STL z=2 slice; connectivity not established'}
   save()
 D['end']=time.time();D['seconds']=D['end']-t0;save()
except Exception as e:
 D['error']=repr(e);D['traceback']=traceback.format_exc();save()
finally:
 (P/'analysis.done').write_text(str(time.time()))
 print('analysis done',D.get('error','ok'),flush=True)
