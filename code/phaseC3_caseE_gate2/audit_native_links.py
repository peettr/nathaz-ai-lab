"""Offline Case E native-mask link ownership audit; no solver execution."""
from pathlib import Path
import sys,json
import numpy as np
from scipy import ndimage
R=Path(__file__).resolve().parent
B=R.parent/'phaseC2_caseE_prep'
C=R.parent/'phaseC0_links'
sys.path.insert(0,str(C))
from link_q import DIRS
F=np.load(B/'step4_flags_z0_90.npz')['flags']
A=np.load(B/'step4_native_v2_links_sparse.npz')['records']
assert F.shape==(91,500,500) and len(A)==2120413
assert not np.any(F[81:91]==1), 'solid above z80: truncated flags unsafe'
# Target cell for each native direction is source + DIRS (direction map from C1).
sys.path.insert(0,str(R.parent/'phaseC1_gate01'))
from analytic_links import NATIVE_D3Q19
v=np.asarray(NATIVE_D3Q19,dtype=np.int64)[A['direction']]
s=A['cell'].astype(np.int64)
z=s//250000;y=(s//500)%500;x=s%500
xt=x+v[:,0];yt=y+v[:,1];zt=z+v[:,2]
assert np.all((xt>=0)&(xt<500)&(yt>=0)&(yt<500)&(zt>=0)&(zt<91))
unknown=A['owner']==3
solid=F==1
lab,n=ndimage.label(solid,structure=ndimage.generate_binary_structure(3,1))
ids=lab[zt[unknown],yt[unknown],xt[unknown]]
assert np.all(ids>0)
cnt=np.bincount(ids,minlength=n+1);volume=np.bincount(lab.ravel(),minlength=n+1)
sl=ndimage.find_objects(lab)
leaders=np.argsort(cnt[1:])[::-1][:10]+1
components=[]
for i in leaders:
 if cnt[i]==0:continue
 ss=sl[i-1];components.append({'id':int(i),'unknown_links':int(cnt[i]),'solid_voxels':int(volume[i]),'bbox_xyz_min':[int(ss[2].start),int(ss[1].start),int(ss[0].start)],'bbox_xyz_max_exclusive':[int(ss[2].stop),int(ss[1].stop),int(ss[0].stop)]})
# Observation points, as registered by phase0 and R11; grid index transform x+2,y+2,z+21.
P=R.parent/'phase0_geometry/ibm_geometry.py'
import re
text=P.read_text();match=re.search(r'points\s*=\s*(.+)',text)
from ibm_geometry import read_case_e,clean_mesh
tri,_=clean_mesh(read_case_e());tri+=np.array([2.,2.,21.]);bounds=[tri.min((0,1)).tolist(),tri.max((0,1)).tolist()]
# Existing point table lives in the full r7 file; parse via phase0's same source.
import csv
from ibm_geometry import R11
points={int(r['id']):r for r in csv.DictReader((R11/'CaseE_W_points_full_r7.csv').open())}
near={}
for pid in (50,51,52,54):
 p=points[pid];xx=float(p['x'])+1010.50008-760+2;yy=float(p['y'])+1000.60004-750+2
 # R11 +1m sampling: centre index +/- 1 around rounded sample-grid x,y; z=23 for physical 2m.
 ix=int(round(xx+1));iy=int(round(yy+1));iz=23
 m=(abs(x-ix)<=1)&(abs(y-iy)<=1)&(abs(z-iz)<=1)
 o,c=np.unique(A['owner'][m],return_counts=True)
 near[str(pid)]={'sample_center_approx':[ix,iy,iz],'raw_registered':[xx,yy,23],'links_in_3x3x3':int(m.sum()),'owner_counts':{str(int(k)):int(v) for k,v in zip(o,c)},'effective_ibb_q':int(np.sum(m&(A['owner']==1)&(abs(A['q']-.5)>1e-7)))}
out={'flags_solid_z81_90':int(np.sum(F[81:91]==1)),'unknown_links':int(unknown.sum()),'solid_components':int(n),'top10_components':components,'clean_stl_bbox_xyz':bounds,'wall_points':near,'direction_convention':NATIVE_D3Q19}
(R/'offline_audit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ('flags_solid_z81_90','unknown_links','top10_components','wall_points')},indent=2))
