"""Sample only evidence-selected VTK/STL shift (+1,+1,0); preserve initial result."""
from pathlib import Path
import json,math,mmap,struct
r=Path('/content/luw-aij-r5');d=json.loads((r/'offset_samples_r5.json').read_text());p=Path(d['vtk']);nx,ny,nz=d['dimensions'];org=d['origin'];dx=d['dx']
with p.open('rb') as f:
 for _ in range(25):
  if f.readline().startswith(b'LOOKUP_TABLE'):break
 off=f.tell();m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 for row in d['rows']:
  x,y=row['xls_xy'];xyz=(x+1010.50008-760+dx,y+1000.60004-750+dx,2.)
  frac=[(v-o)/dx for v,o in zip(xyz,org)];idx=[math.floor(v) for v in frac];w=[v-i for v,i in zip(frac,idx)];u=[0.,0.,0.];fluid=0
  for c in range(8):
   i=idx[0]+(c&1);j=idx[1]+((c>>1)&1);k=idx[2]+((c>>2)&1)
   assert 0<=i<nx and 0<=j<ny and 0<=k<nz
   vec=struct.unpack_from('>fff',m,off+((k*ny+j)*nx+i)*12);fluid+=int(sum(q*q for q in vec)>1e-12)
   weight=math.prod(w[t] if c&(1<<t) else 1-w[t] for t in range(3))
   for t in range(3):u[t]+=weight*vec[t]
  row['sample']['best_xy_plus_dx_z0']={'sim_ratio':math.sqrt(sum(q*q for q in u))/d['uref'],'fluid_corners':fluid}
 m.close()
(r/'offset_samples_best_r5.json').write_text(json.dumps(d,indent=2));print('BEST_SHIFT_SAMPLED',len(d['rows']),flush=True)
