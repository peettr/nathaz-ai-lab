from pathlib import Path
import numpy as np,re,json
root=Path('/content/luw-aij'); case=root/'case_avg2'
assert (root/'avg2.exit').exists(), 'Run not finished'
print((root/'avg2.exit').read_text())
files=list((case/'RESULTS/vtk').glob('*_avg*.vtk'))
assert len(files)==1,files
p=files[0]
with p.open('rb') as f:
 header=[]
 for i in range(11):
  line=f.readline().decode('ascii','replace').strip(); header.append(line)
  if line.startswith('LOOKUP_TABLE'):break
 offset=f.tell()
print('file',p.name,p.stat().st_size,'header',header,'data_offset',offset,flush=True)
dim=list(map(int,next(s for s in header if s.startswith('DIMENSIONS')).split()[1:]))
origin=list(map(float,next(s for s in header if s.startswith('ORIGIN')).split()[1:]))
dx=float(next(s for s in header if s.startswith('SPACING')).split()[1])
assert header[-2].startswith('SCALARS u_avg') and header[-1].startswith('LOOKUP_TABLE')
nx,ny,nz=dim; data=np.memmap(p,dtype='>f4',mode='r',offset=offset,shape=(nz,ny,nx,3))
z=2.0; k=np.clip((z-origin[2])/dx,0,nz-1); k0=int(np.floor(k)); k1=min(k0+1,nz-1); w=k-k0
plane=((1-w)*np.asarray(data[k0],dtype=np.float32)+w*np.asarray(data[k1],dtype=np.float32)).astype(np.float32)
# Save only one pedestrian-height slice, never download full VTK.
out=root/'caseE_N_avg_z2_slice.npz'; np.savez_compressed(out,u=plane,origin=np.array(origin),spacing=np.float32(dx),dimensions=np.array(dim),z=np.float32(z),k=np.float32(k))
print('slice',out,out.stat().st_size,'k',k,'speed range',np.nanmin(np.linalg.norm(plane,axis=2)),np.nanmax(np.linalg.norm(plane,axis=2)),flush=True)
