"""DFG 2D-2 analytic cylinder fluid-to-solid link table; only geometry on 工作站."""
import argparse,math
import numpy as np
from pathlib import Path
from analytic_links import NATIVE_D3Q19
from prepare_ibb import csr
p=argparse.ArgumentParser();p.add_argument('--D',type=int,required=True);p.add_argument('--out',required=True);a=p.parse_args()
D=a.D; nx=22*D+1; ny=int(round(4.1*D))+2; nz=4
cx=2*D+.5;cy=2*D+.5; R=D/2
rows=[]; solid=lambda x,y:(x-cx)**2+(y-cy)**2<=R**2
for y in range(1,ny-1):
 for x in range(1,nx-1):
  if solid(x,y):continue
  for d,(dx,dy,dz) in enumerate(NATIVE_D3Q19):
   if not (dx or dy) or not solid(x+dx,y+dy):continue
   bx=x-cx;by=y-cy; B=2*(bx*dx+by*dy);A=dx*dx+dy*dy;C=bx*bx+by*by-R*R
   roots=[(-B-math.sqrt(B*B-4*A*C))/(2*A),(-B+math.sqrt(B*B-4*A*C))/(2*A)]
   valid=[q for q in roots if 1e-6<q<1-1e-6]
   if valid:
    for z in range(nz):rows.append((x+nx*(y+ny*z),d,min(valid),1))
records=np.array(rows,dtype=[('cell','<u4'),('direction','u1'),('q','<f4'),('owner','u1')]);out=Path(a.out)
print('DFG',D,(nx,ny,nz),'links',csr(records,(nx,ny,nz),out),'q_range',float(records['q'].min()),float(records['q'].max()))
