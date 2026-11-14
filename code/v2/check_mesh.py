import trimesh,numpy as np,json,pandas as pd
from pathlib import Path
P=Path('/content/l2613v2');out={}
for src in ['OpenStreetMap','Overture']:
 m=trimesh.load(P/(src+'_1m_ground0.stl'),force='mesh',process=False)
 a=np.load(P/(src+'_1.npy'),mmap_mode='r')
 def height(x,y):
  j=int(np.floor(x+250));i=int(np.floor(y+250));k=np.where(a[i,j,:]==-3)[0]
  return {'xy_official':[x,y],'xy_LUW':[x+250,y+250],'top_m':int(k.max()) if len(k) else 0,'solid_layers':len(k)}
 out[src]={'readable':True,'watertight':bool(m.is_watertight),'bounds':m.bounds.tolist(),'vertices':len(m.vertices),'faces':len(m.faces),'corners':[height(-249,-249),height(0,0),height(249,249)],'A':height(-63.3,1.6)}
print(json.dumps(out,indent=2))
(P/'mesh_checks.json').write_text(json.dumps(out,indent=2))
