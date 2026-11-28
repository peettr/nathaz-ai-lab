"""Prepare reproducible q tables for LUW channel gate 0, no solver on 工作站."""
from pathlib import Path
import numpy as np
from prepare_ibb import csr, floor
from analytic_links import NATIVE_D3Q19
p=Path(__file__).resolve().parent
for nz in (10,20,22):
 for q in (.25,.75):
  path=p/f'gate0_bottom_z{nz}_q{str(q).replace(".","p")}.csr'
  if not path.exists(): print(path.name,csr(floor((32,12,nz),q),(32,12,nz),path))
# closed asymmetrical two-wall q=.3/.7, force=0 baseline for conservation
nz=20
r=list(floor((32,12,nz),.3));
for y in range(12):
 for x in range(32):
  cell=x+32*(y+(nz-2)*12)
  for d,(dx,dy,dz) in enumerate(NATIVE_D3Q19):
   if dz==1:r.append((cell,d,.7,2))
r=np.array(r,dtype=floor((32,12,nz)).dtype)
path=p/'gate0_closed_z20.csr'
if not path.exists():print(path.name,csr(r,(32,12,nz),path))
