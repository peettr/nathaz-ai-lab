"""Extract 8 small neighbourhoods, actual fluid flags, u/v/w, resolved k."""
from pathlib import Path
import json,mmap,struct,math,numpy as np
r=Path('/content/luw-aij-r12');assert r.joinpath('solver.exit').read_text().split()[0]=='exit=0'
files=list(r.glob('case_a/RESULTS/vtk/*_avg*.vtk'));assert len(files)==1,files
vtk=files[0]
with vtk.open('rb') as f:
 h=[]
 for _ in range(25):
  line=f.readline().decode('ascii','replace').strip();h.append(line)
  if line.startswith('LOOKUP_TABLE'):break
 off=f.tell()
assert h[-2].startswith('SCALARS u_avg') and h[-1].startswith('LOOKUP_TABLE'),h
nx,ny,nz=map(int,next(x for x in h if x.startswith('DIMENSIONS')).split()[1:]);org=list(map(float,next(x for x in h if x.startswith('ORIGIN')).split()[1:]));dx=float(next(x for x in h if x.startswith('SPACING')).split()[1]);assert abs(dx-1)<1e-6
N=nx*ny*nz
with vtk.open('rb') as f:
 m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 def field(start,name,nc):
  tag=(f'SCALARS {name} float {nc}\nLOOKUP_TABLE default\n').encode();assert m[start:start+len(tag)]==tag,(name,start,m[start:start+100]);return start+len(tag)
 rho=field(off+N*12,'rho_avg',1);fluid=field(rho+N*4,'fluid',1);tke=field(fluid+N*4,'tke',1);assert tke+N*4==len(m)
 def idx(i,j,k):return ((k*ny+j)*nx+i)
 def v(i,j,k):return struct.unpack_from('>fff',m,off+idx(i,j,k)*12)
 def sc(base,i,j,k):return struct.unpack_from('>f',m,base+idx(i,j,k)*4)[0]
 pts=json.loads((r/'points_w_r7.json').read_text());ids=(50,51,52,54,44,75,4,39);byid={q['id']:q for q in pts['rows']}
 result={'vtk':str(vtk),'file_size':vtk.stat().st_size,'dimensions':[nx,ny,nz],'origin':org,'dx':dx,'uref':pts['uref'],'points':{}}
 for pid in ids:
  p=byid[pid];x=p['xls_xy'][0]+1010.50008-760+dx;y=p['xls_xy'][1]+1000.60004-750+dx
  # integer nodes ±7 around shifted physical point and z physical 0..6 inclusive
  ix=list(range(math.floor(x)-7,math.ceil(x)+8));iy=list(range(math.floor(y)-7,math.ceil(y)+8));iz=[round((z-org[2])/dx) for z in range(0,7)]
  assert min(ix)>=0 and max(ix)<nx and min(iy)>=0 and max(iy)<ny and min(iz)>=0 and max(iz)<nz
  shape=(len(iz),len(iy),len(ix));vel=np.empty(shape+(3,),dtype=np.float32);karr=np.empty(shape,dtype=np.float32);flags=np.empty(shape,dtype=np.uint8)
  for a,kk in enumerate(iz):
   for b,jj in enumerate(iy):
    for c,ii in enumerate(ix):
     vel[a,b,c]=v(ii,jj,kk);karr[a,b,c]=sc(tke,ii,jj,kk);flags[a,b,c]=int(sc(fluid,ii,jj,kk)>.5)
  name=f'roi_{pid}_r12.npz';np.savez_compressed(r/name,x=np.array(ix,dtype=float)*dx+org[0],y=np.array(iy,dtype=float)*dx+org[1],z=np.array(iz,dtype=float)*dx+org[2],u=vel,k=karr,fluid=flags)
  result['points'][str(pid)]={'xls_xy':p['xls_xy'],'sample_vtk_xy':[x,y],'after':p['after'],'before':p['before'],'roi_file':name,'shape':list(shape),'fluid_z2':int(flags[2].sum())}
 m.close()
(r/'extract_manifest_r12.json').write_text(json.dumps(result,indent=2));print('EXTRACTED',result,flush=True)
