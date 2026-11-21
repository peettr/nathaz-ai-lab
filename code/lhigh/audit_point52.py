import json,math,numpy as np
from pathlib import Path
R=Path(__file__).resolve().parent
P=R.parent.parent/'phaseC2_caseE_prep/step4_native_v2_links_sparse.npz'
a=np.load(P)['records']
x=a['cell']%500;y=a['cell']//500%500;z=a['cell']//250000
q=json.loads((R.parent/'offline_audit.json').read_text())['wall_points']['52']['raw_registered']
# The documented registered q-index coordinate is fractional. Evaluate all eight corners;
# z is exactly integral, so upper z corners have zero interpolation weight.
result={'registered_q_index':q,'corners':[],'warnings':['Use audited registration; verify VTK-to-q-index offset with source before physical interpretation.']}
for dz in (0,1):
 for dy in (0,1):
  for dx in (0,1):
   i=math.floor(q[0])+dx;j=math.floor(q[1])+dy;k=math.floor(q[2])+dz
   w=np.prod([(q[d]-math.floor(q[d])) if b else 1-(q[d]-math.floor(q[d])) for d,b in enumerate((dx,dy,dz))])
   m=(abs(x-i)<=1)&(abs(y-j)<=1)&(abs(z-k)<=1)
   own={str(int(o)):int(n) for o,n in zip(*np.unique(a['owner'][m],return_counts=True))}
   active=int(np.sum(m&(a['owner']==1)&(abs(a['q']-.5)>1e-7)))
   result['corners'].append({'q_cell':[i,j,k],'weight':float(w),'owner_counts_3x3x3':own,'active_ibb_links_3x3x3':active})
(R/'point52_eight_corners.json').write_text(json.dumps(result,indent=2)+'\n')
print(result)
