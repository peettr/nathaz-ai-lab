import numpy as np,csv,io,zipfile,json,collections
from pathlib import Path
R=Path(__file__).parent
with zipfile.ZipFile(R/'D_evidence.zip') as z:
 rows=list(csv.DictReader(io.StringIO(z.read('stage/case/RESULTS/mass_extrema.csv').decode())))
records=np.load(R.parent.parent/'phaseC2_caseE_prep/step4_native_v2_links_sparse.npz')['records']
rec=records[(records['owner']==1)&(records['q']!=np.float32(.5))];cells=rec['cell'].astype(np.int64)
counts=np.bincount(cells,minlength=500*500*470)
indices={}
for r in rows:
 if int(r['step'])<4000:continue
 t=tuple(int(r[k]) for k in ('x','y','z'));indices[t]=int(r['step'])
out=[]
for (x,y,z),t in indices.items():
 n=x+500*(y+500*z); nearby=[]
 for zz in range(max(0,z-1),min(470,z+2)):
  for yy in range(max(0,y-1),min(500,y+2)):
   for xx in range(max(0,x-1),min(500,x+2)):
    j=xx+500*(yy+500*zz)
    if counts[j]: nearby.append((xx,yy,zz,int(counts[j]),[(int(a['direction']),float(a['q']),int(a['owner'])) for a in rec[cells==j]]))
 out.append(dict(x=x,y=y,z=z,last_step=t,links=int(counts[n]),neighborhood=nearby))
(R/'D_extrema_join.json').write_text(json.dumps(out,indent=2))
print('late extrema positions',len(out),[(x['x'],x['y'],x['z'],x['links'],len(x['neighborhood'])) for x in out]);print('active cell counts histogram',dict(zip(*np.unique(counts[counts>0],return_counts=True))))
