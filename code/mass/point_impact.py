from pathlib import Path
import json,numpy as np
R=Path(__file__).parent;d=json.loads((R.parent/'offline_audit.json').read_text())
records=np.load(R.parent.parent/'phaseC2_caseE_prep/step4_native_v2_links_sparse.npz')['records']
rec=records[(records['owner']==1)&(records['q']!=np.float32(.5))]
cell=rec['cell'].astype(np.int64);counts=np.bincount(cell,minlength=500*500*470)
res={}
for key,v in d['wall_points'].items():
 x,y,z=v['sample_center_approx'];near=[]
 for zz in range(z-1,z+2):
  for yy in range(y-1,y+2):
   for xx in range(x-1,x+2):
    idx=xx+500*(yy+500*zz)
    if counts[idx]:near.append((xx,yy,zz,int(counts[idx])))
 res[key]={'links':sum(n[-1] for n in near),'fallback_N3':sum(n[-1] for n in near if n[-1]>=3),'cells':near}
(R/'M2_point_impact.json').write_text(json.dumps(res,indent=2));print({k:(v['links'],v['fallback_N3']) for k,v in res.items()})
