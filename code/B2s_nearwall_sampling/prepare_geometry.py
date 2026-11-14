from pathlib import Path
import sys,json,math,numpy as np
R=Path(__file__).resolve().parent; L=R.parents[1]
sys.path.insert(0,str(L/'wp1b_ibm/phase0_geometry'))
from ibm_geometry import read_case_e,clean_mesh,section_segments
tri,_=clean_mesh(read_case_e()); seg=section_segments(tri,2.)
base=json.loads((L/'method_study/B2u_scalar_mean/offset_samples_a_r10.json').read_text())
flags=np.load(L/'wp1b_ibm/phaseC2_caseE_prep/step4_flags_z0_90.npz')['flags']; solid=(flags&1)!=0
rows=[]
for p in base['rows']:
 x,y=[p['xls_xy'][0]+250.50008,p['xls_xy'][1]+250.60004]
 d=seg[:,1]-seg[:,0]; v=seg[:,0]; t=np.clip(np.sum((np.array([x,y])-v)*d,axis=1)/np.maximum(np.sum(d*d,axis=1),1e-16),0,1); near=v+t[:,None]*d
 j=int(np.argmin(np.linalg.norm(near-[x,y],axis=1))); q=near[j]; delta=np.array([x,y])-q; dist=float(np.linalg.norm(delta))
 if dist>1e-6: direction=delta/dist
 else:
  tangent=d[j]/np.linalg.norm(d[j]); normal=np.array([-tangent[1],tangent[0]])
  def score(n):
   pt=q+1.1*n; ix=int(round(pt[0]+1));iy=int(round(pt[1]+1));return int(not solid[22,iy,ix])
  direction=normal if score(normal)>score(-normal) else -normal
 # A near-wall point may be on solid side. Orient toward nearest accessible fluid shell.
 probe=q+1.25*direction; ix=int(round(probe[0]+1));iy=int(round(probe[1]+1))
 if solid[22,iy,ix] and not solid[22,int(round((q-1.25*direction)[1]+1)),int(round((q-1.25*direction)[0]+1))]:direction=-direction
 rows.append({'id':p['id'],'xy':[x,y],'nearest_wall_xy':q.tolist(),'wall_distance_m':dist,'fluid_normal_xy':direction.tolist(),'obs_W':p['after']})
(R/'geometry.json').write_text(json.dumps(rows,indent=2)+'\n')
print('geometry',len(rows),'near',[(r['id'],r['wall_distance_m'],r['fluid_normal_xy']) for r in rows if r['id'] in (50,51,52,54,55,74)])
