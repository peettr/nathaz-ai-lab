"""Convert phase C0 NPZ or generate a complete analytic q=.5 floor into LUW CSR."""
import argparse,struct
from pathlib import Path
import numpy as np
from analytic_links import NATIVE_D3Q19

def csr(records, shape, out):
    nx,ny,nz=shape; n=nx*ny*nz
    a=np.asarray(records); cells=a['cell'].astype('<u4'); dirs=a['direction'].astype('u1'); q=a['q'].astype('<f4')
    owner=a['owner'].astype('u1') if 'owner' in a.dtype.names else np.zeros(len(cells),dtype='u1')
    order=np.lexsort((dirs,cells)); cells=cells[order]; dirs=dirs[order]; q=q[order]; owner=owner[order]
    if len(cells) and (cells.max()>=n or np.any((dirs<1)|(dirs>=19)) or np.any((q<=0)|(q>=1)) or np.any(owner>2)):raise ValueError('invalid link')
    if len(set(zip(cells.tolist(),dirs.tolist())))!=len(cells):raise ValueError('duplicate link')
    offsets=np.zeros(n+1,dtype='<u4'); offsets[1:]=np.cumsum(np.bincount(cells,minlength=n))
    with Path(out).open('xb') as f:
        f.write(struct.pack('<QQ',n,len(cells))); f.write(offsets.tobytes());f.write(dirs.tobytes());f.write(q.tobytes());f.write(owner.tobytes())
    return len(cells)

def floor(shape,q=.5):
    nx,ny,nz=shape; rows=[]
    for y in range(ny):
      for x in range(nx):
        z=1; cell=x+nx*(y+z*ny)
        for d,(dx,dy,dz) in enumerate(NATIVE_D3Q19):
          if dz==-1: rows.append((cell,d,q,2))
    return np.array(rows,dtype=[('cell','<u4'),('direction','u1'),('q','<f4'),('owner','u1')])

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--nx',type=int,default=32);p.add_argument('--ny',type=int,default=12);p.add_argument('--nz',type=int,default=10);p.add_argument('--q',type=float,default=.5);p.add_argument('--npz');a=p.parse_args();shape=(a.nx,a.ny,a.nz)
 rec=np.load(a.npz)['records'] if a.npz else floor(shape,a.q)
 print('links',csr(rec,shape,a.out))
