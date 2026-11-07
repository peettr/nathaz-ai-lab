"""Generate DFG D80 analytical cylinder links; geometry only, no solver."""
import math, struct
from pathlib import Path
import numpy as np
D=80; nx=22*D+1; ny=round(4.1*D)+2; nz=4
cx=cy=2*D+.5; R=D/2
V=((0,0,0),(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),(1,1,0),(-1,-1,0),(1,0,1),(-1,0,-1),(0,1,1),(0,-1,-1),(1,-1,0),(-1,1,0),(1,0,-1),(-1,0,1),(0,1,-1),(0,-1,1))
solid=lambda x,y:(x-cx)**2+(y-cy)**2<=R**2
rows=[]
for y in range(1,ny-1):
 for x in range(1,nx-1):
  if solid(x,y):continue
  for d,(dx,dy,dz) in enumerate(V):
   if not (dx or dy) or not solid(x+dx,y+dy):continue
   bx=x-cx;by=y-cy; B=2*(bx*dx+by*dy);A=dx*dx+dy*dy;C=bx*bx+by*by-R*R
   disc=B*B-4*A*C
   if disc<0:continue
   qs=[q for q in ((-B-math.sqrt(disc))/(2*A),(-B+math.sqrt(disc))/(2*A)) if 1e-6<q<1-1e-6]
   if qs:
    for z in range(nz):rows.append((x+nx*(y+ny*z),d,min(qs),1))
a=np.array(rows,dtype=[('cell','<u4'),('direction','u1'),('q','<f4'),('owner','u1')]);a.sort(order=['cell','direction']);N=nx*ny*nz
off=np.empty(N+1,dtype='<u4');off[0]=0;off[1:]=np.cumsum(np.bincount(a['cell'].astype(np.int64),minlength=N),dtype=np.uint32)
p=Path(__file__).with_name('dfg_D80.csr')
with p.open('wb') as f:
 f.write(struct.pack('<QQ',N,len(a)));f.write(off.tobytes());f.write(a['direction'].tobytes());f.write(a['q'].tobytes());f.write(a['owner'].tobytes())
print('N,links,bytes,qrange',N,len(a),p.stat().st_size,float(a['q'].min()),float(a['q'].max()))
