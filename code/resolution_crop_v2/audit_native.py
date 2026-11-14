"""Offline audit of native cropped flags against full-domain flags."""
from pathlib import Path
import numpy as np,json,math
R=Path(__file__).resolve().parent
full=np.load(R.parent/'phaseC2_caseE_prep/step4_flags_z0_90.npz')['flags']
pts={50:(205.00008,205.60004),51:(226.00008,231.10004),52:(219.50008,227.10004),54:(230.50008,220.10004)}
out={}
for name,nx,ny,y0 in [('C1v2',300,250,80),('C1widev2',330,280,65)]:
 a=np.fromfile(R/(name+'_flags_z0_90.bin'),dtype=np.uint8).reshape(91,ny,nx)
 ref=full[:,y0:y0+ny,:nx]
 faces={k:int(((v&3)==1).sum()) for k,v in [('in',a[21:,:,0]),('out',a[21:,:,-1]),('south',a[21:,0,:]),('north',a[21:,-1,:])]}
 keep=json.loads((R/(name+'_geometry.json')).read_text());wall=[]
 for pid,(x,y) in pts.items():
  # VTK sampling is +1 m in x,y; compare all 8 trilinear corners at z=2 and 3.
  ix=math.floor(x+1);iy=math.floor(y+1-y0); iz=22
  inds=[(z,j,i) for z in (iz,iz+1) for j in (iy,iy+1) for i in (ix,ix+1)]
  assert all(0<=i<nx and 0<=j<ny for z,j,i in inds)
  equal=all(a[z,j,i]==ref[z,j,i] for z,j,i in inds)
  wall.append({'id':pid,'physical_xy':[x,y],'crop_corner_ijk':[[i,j,z] for z,j,i in inds],'flags_equal_all_8':equal,'solid_corners':sum((a[z,j,i]&3)==1 for z,j,i in inds),'nearest_deleted_bbox_m':keep['wall_to_nearest_deleted_bbox_m'][[50,51,52,54].index(pid)]})
 # retained central region around points and upstream buildings; avoid deleted peripheral comps
 sub=a[21:81,100-y0:265-y0,75:250];subref=ref[21:81,100-y0:265-y0,75:250]
 out[name]={'solid_open_faces_above_ground':faces,'wall_points':wall,'central_flags_difference':int(np.count_nonzero(sub!=subref)),'central_cells':int(sub.size),'total_flags_difference':int(np.count_nonzero(a!=ref)),'deleted_components':keep['deleted_components'],'deleted_triangles':keep['deleted_triangles'],'retained_triangles':keep['retained_building_triangles'],'grid':[nx,ny,180 if name=='C1v2' else 160]}
(R/'native_mask_audit.json').write_text(json.dumps(out,indent=2,default=lambda v: int(v) if isinstance(v,np.integer) else float(v))+'\n');print(json.dumps(out,indent=2,default=lambda v: int(v) if isinstance(v,np.integer) else float(v)))
