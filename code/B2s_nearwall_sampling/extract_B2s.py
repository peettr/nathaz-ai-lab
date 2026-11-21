from pathlib import Path
import json,math,struct,numpy as np
R=Path('/content/b2s_case'); vtk=next((R/'case/RESULTS/vtk').glob('*_avg*.vtk'))
with vtk.open('rb') as f:
 header=[]
 while True:
  line=f.readline().decode('ascii','replace').strip();header.append(line)
  if line.startswith('LOOKUP_TABLE'):break
 offset=f.tell()
nx,ny,nz=map(int,next(x for x in header if x.startswith('DIMENSIONS')).split()[1:]);org=np.array(list(map(float,next(x for x in header if x.startswith('ORIGIN')).split()[1:])))
assert (nx,ny,nz)==(500,500,270) and tuple(org)==(0.,0.,-20.)
count=nx*ny*nz
with vtk.open('rb') as f:
 def field(off,name):
  f.seek(off); line=f.readline();lookup=f.readline();assert line.startswith(('SCALARS '+name).encode()) and lookup.startswith(b'LOOKUP_TABLE'),(off,line,lookup);return f.tell()
 rho=field(offset+count*12,'rho_avg');fluid=field(rho+count*4,'fluid');k=field(fluid+count*4,'tke');su=field(k+count*4,'speed_mean');su2=field(su+count*4,'speed2_mean')
 assert vtk.stat().st_size==su2+count*4
u=np.memmap(vtk,mode='r',dtype='>f4',offset=offset,shape=(nz,ny,nx,3));fm=np.memmap(vtk,mode='r',dtype='>f4',offset=fluid,shape=(nz,ny,nx));km=np.memmap(vtk,mode='r',dtype='>f4',offset=k,shape=(nz,ny,nx));sm=np.memmap(vtk,mode='r',dtype='>f4',offset=su,shape=(nz,ny,nx))
geo=json.loads(Path('/content/geometry.json').read_text());ref=json.loads(Path('/content/b2u_reference.json').read_text());uref=ref['uref']
native=np.load('/content/native_flags_z20_30.npz')['flags'];assert native.shape==(11,ny,nx)
for iz in (21,22,23):
 assert np.array_equal((native[iz-20]&1)==0,np.asarray(fm[iz]>.5)),('native/VTK mask differs',iz)
def interp(x,y,z):
 a=np.array([x,y,z])-org; i=np.floor(a).astype(int);frac=a-i
 assert all(i>=0) and i[0]<nx-1 and i[1]<ny-1 and i[2]<nz-1,(a,i)
 v=np.zeros(3);s=0.;t=0.;nf=0;ws=0.
 for b in range(8):
  ix=i[0]+(b&1);iy=i[1]+((b>>1)&1);iz=i[2]+((b>>2)&1)
  wt=np.prod([frac[j] if b&(1<<j) else 1-frac[j] for j in range(3)])
  v+=wt*u[iz,iy,ix];s+=wt*sm[iz,iy,ix];t+=wt*km[iz,iy,ix]
  if fm[iz,iy,ix]>.5:nf+=1
  else:ws+=wt
 return {'S':float(np.linalg.norm(v)/uref),'Su':float(s/uref),'k':float(t),'fluid_corners':nf,'solid_weight':float(ws),'uv_mps':v.tolist()}
rows=[]
for p in geo:
 x,y=p['xy'];q=np.array(p['nearest_wall_xy']);n=np.array(p['fluid_normal_xy']);line=[]
 for d in (.25,.5,.75,1.,1.5,2.,3.):
  point=q+n*d;rec=interp(point[0]+1,point[1]+1,2.);line.append({'distance_m':d,'xy':point.tolist(),**rec})
 ix=int(round(x+1));iy=int(round(y+1));iz=22
 center={'xyz_native':[ix,iy,iz],'u_mps':u[iz,iy,ix].astype(float).tolist(),'Su':float(sm[iz,iy,ix]/uref),'S':float(np.linalg.norm(u[iz,iy,ix])/uref),'k':float(km[iz,iy,ix]),'fluid':bool(fm[iz,iy,ix]>.5)}
 base=interp(x+1,y+1,2.);rows.append({**p,'original':base,'nearest_center':center,'line':line})
(R/'nearwall_80.json').write_text(json.dumps(rows,indent=2)+'\n')
# Small local boxes: six near-wall, plus four agreement controls at 2-5m wall distance.
controls=[]
for p in geo:
 if 2<=p['wall_distance_m']<=5:
  q=ref['rows'][p['id']-1];v=q['sample']['plus_dx']['Su_ratio'];w=q['after'];controls.append((abs(v-w),p['id']))
controls=[id for _,id in sorted(controls)[:4]]
ids=[50,51,52,54,55,74]+controls
for pid in ids:
 p=geo[pid-1];x,y=p['xy'];ix=int(round(x+1));iy=int(round(y+1));x0=max(0,ix-15);x1=min(nx,ix+16);y0=max(0,iy-15);y1=min(ny,iy+16)
 sl=np.s_[20:31,y0:y1,x0:x1]
 np.savez_compressed(R/f'local_{pid}.npz',u_avg=np.asarray(u[sl],dtype='f4'),Su=np.asarray(sm[sl],dtype='f4'),k=np.asarray(km[sl],dtype='f4'),flags=np.asarray(native[:,y0:y1,x0:x1],dtype='u1'),native_origin_xyz=[x0,y0,20],physical_origin_xyz=[x0-1,y0-1,0])
 assert (R/f'local_{pid}.npz').stat().st_size<5_000_000
for z in (1,2,3):
 iz=z+20;np.savez_compressed(R/f'plane_z{z}.npz',u_avg=np.asarray(u[iz],dtype='f4'),Su=np.asarray(sm[iz],dtype='f4'),k=np.asarray(km[iz],dtype='f4'),flags=np.asarray(native[iz-20],dtype='u1'),native_z=iz,physical_z_m=z,physical_xy_origin=[-1,-1]);assert (R/f'plane_z{z}.npz').stat().st_size<50_000_000
(R/'extract_manifest.json').write_text(json.dumps({'dimensions':[nx,ny,nz],'origin':org.tolist(),'controls':controls,'local_ids':ids,'files':{f.name:f.stat().st_size for f in R.glob('*.npz')},'points':len(rows)},indent=2)+'\n')
print('EXTRACT OK',controls,[(f.name,f.stat().st_size) for f in R.glob('*.npz')],flush=True)
