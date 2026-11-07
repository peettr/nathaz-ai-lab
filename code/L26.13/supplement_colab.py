import json,math,zipfile,hashlib,time
from pathlib import Path
import numpy as np,pandas as pd,trimesh
from PIL import Image,ImageDraw
from scipy.ndimage import label,map_coordinates
P=Path('/content/l2613');R={};M=json.loads((P/'metrics.json').read_text())
m=trimesh.load(P/'BD_caseE.stl',force='mesh',process=False);tri=np.asarray(m.vertices)[m.faces]*250
n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n=n/(np.linalg.norm(n,axis=1,keepdims=True)+1e-30)
roof=tri[(np.abs(n[:,2])>.9)&(tri[:,:,2].min(axis=1)>.5)]
S=1000; pix=.5; half=250
im=Image.new('1',(S,S));draw=ImageDraw.Draw(im)
for t in roof:draw.polygon([((x+half)/pix,(y+half)/pix) for x,y,z in t],fill=1)
a=np.asarray(im,dtype=bool);lab,count=label(a)
# components are roof-connected, not individual buildings; triangle centroids establish each component height
comps=[]
for k in range(1,count+1):
 inds=np.argwhere(lab==k);area=len(inds)*pix*pix
 if area<1:continue
 center=inds.mean(axis=0);comps.append({'roof_component':k,'area_m2':round(area,2),'x_m':round(center[1]*pix-half,2),'y_m':round(center[0]*pix-half,2),'official_roof_height_m':None})
byid={c['roof_component']:c for c in comps}
for t in roof:
 xy=t[:,:2].mean(axis=0);ix=int((xy[0]+half)/pix);iy=int((xy[1]+half)/pix)
 if 0<=ix<S and 0<=iy<S:
  k=int(lab[iy,ix]);
  if k in byid:byid[k]['official_roof_height_m']=max(byid[k]['official_roof_height_m'] or 0,round(float(t[:,2].mean()),3))
R['roof_components']=len(comps);R['roof_height_histogram']=pd.Series([x['official_roof_height_m'] for x in comps]).value_counts().to_dict()
# RS coordinate columns and independent coordinate IDs
rs=pd.read_csv(P/'RS_caseE.csv');ac=rs[rs['case']=='ac'].drop_duplicates(['x(m)','y(m)']); q=ac[['x(m)','y(m)']].to_numpy()
R['ac_unique_points']=len(q);R['ac_rows']=len(rs[rs['case']=='ac']);R['wind_directions']=rs['Wind_direction'].nunique()
for src in ('OpenStreetMap','Overture'):
 z=np.load(P/(src+'_1m.npz'));bh=z['heights'];sl=z['slice2'].astype(bool)
 # Source north grid [east,north], origin -255; rotate by -1°
 theta=np.deg2rad(-1);c,s=np.cos(theta),np.sin(theta)
 def sample(x,y,A):
  wx=c*x-s*y;wy=s*x+c*y
  ix=np.floor(wx+255).astype(int);iy=np.floor(wy+255).astype(int)
  good=(ix>=0)&(ix<A.shape[0])&(iy>=0)&(iy<A.shape[1])
  out=np.zeros(len(ix),dtype=A.dtype);out[good]=A[ix[good],iy[good]];return out
 hit=sample(q[:,0],q[:,1],sl)
 R[src+'_points']={'inside_count':int(hit.sum()),'total':len(q),'inside_ids':ac.loc[hit,'No.'].astype(int).tolist()}
 for co in comps:
  top=sample(np.array([co['x_m']]),np.array([co['y_m']]),bh)[0]
  co[src+'_roof_centroid_voxel_m']=float(top)
  if co['official_roof_height_m'] is not None:co[src+'_height_diff_m']=round(abs(float(top)-co['official_roof_height_m']),3)
 R[src+'_height_diff_descriptive_median_m']=float(np.median([co[src+'_height_diff_m'] for co in comps if src+'_height_diff_m' in co]))
 # compressed transfer; binary STL kept on Colab, no raw STL published into live lab
 stl=P/(src+'_1m.stl');zipname=P/(src+'_1m.stl.zip')
 with zipfile.ZipFile(zipname,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zz:zz.write(stl,arcname=stl.name)
 R[src+'_stl_zip']={'bytes':zipname.stat().st_size,'sha256':hashlib.sha256(zipname.read_bytes()).hexdigest(),'raw_stl_bytes':stl.stat().st_size,'raw_stl_sha256':hashlib.sha256(stl.read_bytes()).hexdigest()}
R['ABC_candidates']=[x for x in comps if x['official_roof_height_m'] and x['official_roof_height_m']>=17]
pd.DataFrame(comps).to_csv(P/'official_roof_components.csv',index=False)
(P/'supplement.json').write_text(json.dumps(R,indent=2,ensure_ascii=False,default=str))
print(json.dumps({k:v for k,v in R.items() if k not in ('ABC_candidates','roof_height_histogram')},ensure_ascii=False))
