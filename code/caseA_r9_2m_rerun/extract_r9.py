from pathlib import Path
import json,math,mmap,struct,itertools
r=Path('/content/luw-aij-caseA-turb-20261014')
assert r.joinpath('solver.exit').read_text().startswith('exit=0')
files=list(r.glob('caseA/RESULTS/vtk/*_avg*.vtk'));assert len(files)==1,files
vtk=files[0];obs=json.loads(Path('/content/caseA_observations_official.json').read_text())
with vtk.open('rb') as f:
 header=[]
 for _ in range(25):
  line=f.readline().decode('ascii','replace').strip();header.append(line)
  if line.startswith('LOOKUP_TABLE'):break
 offset=f.tell()
assert header[-2].startswith('SCALARS u_avg'),header
nx,ny,nz=map(int,next(t for t in header if t.startswith('DIMENSIONS')).split()[1:]);origin=list(map(float,next(t for t in header if t.startswith('ORIGIN')).split()[1:]));dx=float(next(t for t in header if t.startswith('SPACING')).split()[1]);N=nx*ny*nz
with vtk.open('rb') as f:
 m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 def field_offset(start,name,comps):
  tag=(f'SCALARS {name} float {comps}\nLOOKUP_TABLE default\n').encode();assert m[start:start+len(tag)]==tag,(name,start,m[start:start+100]);return start+len(tag)
 rho=field_offset(offset+N*12,'rho_avg',1);fluid=field_offset(rho+N*4,'fluid',1);tke=field_offset(fluid+N*4,'tke',1);assert tke+N*4==len(m)
 def scalar(off,i,j,k):return struct.unpack_from('>f',m,off+((k*ny+j)*nx+i)*4)[0]
 def vec(i,j,k):return struct.unpack_from('>fff',m,offset+((k*ny+j)*nx+i)*12)
 def interp(x,y,z):
  frac=[(a-b)/dx for a,b in zip((x,y,z),origin)];ids=[math.floor(v) for v in frac];w=[v-i for v,i in zip(frac,ids)];v=[0.,0.,0.];e=0.;nf=0
  for c in range(8):
   i=ids[0]+(c&1);j=ids[1]+((c>>1)&1);k=ids[2]+((c>>2)&1)
   assert 0<=i<nx and 0<=j<ny and 0<=k<nz,(x,y,z,ids,nx,ny,nz)
   weight=math.prod(w[d] if c&(1<<d) else 1-w[d] for d in range(3))
   q=vec(i,j,k)
   for d in range(3):v[d]+=weight*q[d]
   e+=weight*scalar(tke,i,j,k);nf+=scalar(fluid,i,j,k)>.5
  return {'uvw_mps':v,'speed_UH':math.sqrt(sum(q*q for q in v))/obs['UH'],'k_UH2':e/obs['UH']**2,'fluid_corners':nf,'sample_xyz_m':[x,y,z]}
 mask=[]
 for z in (32.,62.,64.,66.):
  k=round((z-origin[2])/dx)
  for shift in itertools.product((0.,dx),repeat=3):
   tp=fp=fn=0
   for x in range(322,384,2):
    for y in range(322,384,2):
     i=round((x-origin[0])/dx);j=round((y-origin[1])/dx)
     solid=scalar(fluid,i,j,k)<.5
     inside=(336<=x-shift[0]<368 and 336<=y-shift[1]<368 and 0<=z-shift[2]<64)
     tp+=solid and inside;fp+=solid and not inside;fn+=inside and not solid
   mask.append({'z_m':z,'shift_m':shift,'tp':tp,'fp':fp,'fn':fn,'iou':tp/(tp+fp+fn) if tp+fp+fn else None})
 groups={};alternate={}
 for key,pts in obs['groups'].items():
  label={'z8':'z4_actual','z80':'z40_actual','vertical':'vertical_actual'}[key]
  groups[label]=[{'id':p['id'],'obs_speed':p['speed'],'obs_k':p['k'],'official_xyz_m':[p['x'],p['y'],p['z']], 'no_shift':interp(p['x'],p['y'],p['z']),'plus_xy':interp(p['x']+dx,p['y']+dx,p['z']),'plus_xyz':interp(p['x']+dx,p['y']+dx,p['z']+dx)} for p in pts]
  if key in ('z8','z80'):
   altz=8. if key=='z8' else 80.;alternate[f'z{int(altz)}_diagnostic']=[{'id':p['id'],'obs_speed':p['speed'],'obs_k':p['k'],'official_xyz_m':[p['x'],p['y'],p['z']], 'no_shift':interp(p['x'],p['y'],altz),'plus_xy':interp(p['x']+dx,p['y']+dx,altz),'plus_xyz':interp(p['x']+dx,p['y']+dx,altz+dx)} for p in pts]
 m.close()
out={'vtk':str(vtk),'size':vtk.stat().st_size,'dimensions':[nx,ny,nz],'origin':origin,'spacing':dx,'mask':mask,'groups':groups,'diagnostic':alternate,'UH':obs['UH']}
r.joinpath('samples_caseA_r9_2m.json').write_text(json.dumps(out,indent=2));print('EXTRACTED',[(k,len(v)) for k,v in groups.items()],flush=True)
