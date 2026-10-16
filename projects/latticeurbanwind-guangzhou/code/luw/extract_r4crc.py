"""Sample finished LUW binary VTK on CRC without importing large arrays."""
from pathlib import Path
import json,math,mmap,struct,sys
root=Path(sys.argv[1]);assert (root/'exit.code').read_text().strip()=='0'
files=list((root/'case_west/RESULTS/vtk').glob('*_avg*.vtk'));assert len(files)==1,files
p=files[0]
with p.open('rb') as f:
 header=[]
 for _ in range(25):
  line=f.readline().decode('ascii','replace').strip();header.append(line)
  if line.startswith('LOOKUP_TABLE'):break
 offset=f.tell()
assert header[-2].startswith('SCALARS u_avg') and header[-1].startswith('LOOKUP_TABLE'),header
nx,ny,nz=map(int,next(x for x in header if x.startswith('DIMENSIONS')).split()[1:])
origin=list(map(float,next(x for x in header if x.startswith('ORIGIN')).split()[1:]));dx=float(next(x for x in header if x.startswith('SPACING')).split()[1])
assert p.stat().st_size>=offset+nx*ny*nz*12,(p.stat().st_size,offset,nx,ny,nz)
pts=json.loads((root/'points_w_r4crc.json').read_text());assert len(pts['rows'])==80
with p.open('rb') as f:
 m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 def vec(i,j,k):
  assert 0<=i<nx and 0<=j<ny and 0<=k<nz,(i,j,k)
  return struct.unpack_from('>fff',m,offset+((k*ny+j)*nx+i)*12)
 def interpolate(x,y,z):
  frac=[(val-org)/dx for val,org in zip((x,y,z),origin)]
  idx=[math.floor(v) for v in frac];w=[v-i for v,i in zip(frac,idx)]
  out=[0.,0.,0.];corners=[]
  for c in range(8):
   ii=idx[0]+(c&1);jj=idx[1]+((c>>1)&1);kk=idx[2]+((c>>2)&1)
   weight=math.prod([w[d] if c&(1<<d) else 1-w[d] for d in range(3)])
   v=vec(ii,jj,kk);corners.append(math.sqrt(sum(q*q for q in v)))
   for d in range(3):out[d]+=weight*v[d]
  return math.sqrt(sum(q*q for q in out)),corners
 for row in pts['rows']:
  u,corners=interpolate(*row['local_xy'],2.0);row['sim_ratio']=u/pts['uref'];row['fluid_corners']=sum(q>1e-7 for q in corners)
 up=[]
 for x in (10.,100.,300.,450.):
  for z in (2.,15.9):
   speed=[interpolate(x,200+y*25,z)[0] for y in range(13)]
   up.append({'x_m':x,'z_m':z,'mean_speed_mps':sum(speed)/len(speed),'fraction_input':(sum(speed)/len(speed))/(2.964 if z==2 else pts['uref'])})
 m.close()
out={'file':str(p),'file_size':p.stat().st_size,'dimensions':[nx,ny,nz],'origin':origin,'dx':dx,'uref':pts['uref'],'rows':pts['rows'],'upstream':up,'registration':pts['registration']}
(root/'samples_r4crc.json').write_text(json.dumps(out,indent=2));print('EXTRACTED',len(pts['rows']),up)
