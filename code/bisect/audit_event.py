import numpy as np, zipfile, csv, json, io
from pathlib import Path
p=Path(__file__).parent
rec=np.load(p/'../../phaseC2_caseE_prep/step4_native_v2_links_sparse.npz')['records']
rec=rec[(rec['owner']==1)&(rec['q']!=np.float32(.5))]
rec=np.sort(rec,order=['cell','direction'])
flags=np.load(p/'../../phaseC2_caseE_prep/step4_flags_z0_90.npz')['flags']
out={}
with zipfile.ZipFile(p/'bisect_v5_evidence.zip') as z:
 for name in ('B0','B1','B2','B3','B4'):
  rows=list(csv.DictReader(io.StringIO(z.read(name+'/event.csv').decode())))
  if not rows:continue
  e=rows[0];x,y,zz=[int(e[k]) for k in ('x','y','z')]
  local=[]
  for dz in range(-2,3):
   for dy in range(-2,3):
    for dx in range(-2,3):
     a,b,c=x+dx,y+dy,zz+dz
     if not(0<=a<500 and 0<=b<500 and 0<=c<91):continue
     ix=a+500*(b+500*c)
     l=np.searchsorted(rec['cell'],ix,'left');h=np.searchsorted(rec['cell'],ix,'right')
     for v in rec[l:h]:
      q=float(v['q']);active=name in ('B0','B4') or (name=='B1' and q>=.5) or (name=='B2' and q<.5) or (name=='B3' and .1<=q<=.9)
      if active:local.append([a,b,c,int(flags[c,b,a]),int(v['direction']),q])
  out[name]={'event':e,'neighborhood_active_links':len(local),'links':local[:30], 'q_minmax':[min([a[-1] for a in local],default=None),max([a[-1] for a in local],default=None)]}
(p/'event_neighborhood.json').write_text(json.dumps(out,indent=2))
print(json.dumps({k:{'event':v['event'],'nlinks':v['neighborhood_active_links'],'q_minmax':v['q_minmax'],'links_first10':v['links'][:10]} for k,v in out.items()},indent=2))
