"""Read-only Case E VTK vs STL mask at three heights, plus 80-point offsets and upstream."""
from pathlib import Path
import json,math,mmap,struct,itertools
r=Path('/content/luw-aij-r7');assert r.joinpath('solver.exit').read_text().split()[0]=='exit=0'
files=list(r.glob('case_west/RESULTS/vtk/*_avg*.vtk'));assert len(files)==1,files
vtk=files[0];stl=r/'case_west/proj_temp/CaseE_PF.stl'
with vtk.open('rb') as f:
 header=[]
 for _ in range(25):
  line=f.readline().decode('ascii','replace').strip();header.append(line)
  if line.startswith('LOOKUP_TABLE'):break
 offset=f.tell()
assert header[-2].startswith('SCALARS u_avg') and header[-1].startswith('LOOKUP_TABLE'),header
nx,ny,nz=map(int,next(x for x in header if x.startswith('DIMENSIONS')).split()[1:]);org=list(map(float,next(x for x in header if x.startswith('ORIGIN')).split()[1:]));dx=float(next(x for x in header if x.startswith('SPACING')).split()[1]);assert .95<dx<1.05
assert vtk.stat().st_size>=offset+nx*ny*nz*12
points_count=nx*ny*nz
def field_offset(m, start, name, components):
    tag=(f'SCALARS {name} float {components}\nLOOKUP_TABLE default\n').encode()
    assert m[start:start+len(tag)]==tag,(name,start,m[start:start+120])
    return start+len(tag)
with stl.open('rb') as f:
 f.read(80);count=struct.unpack('<I',f.read(4))[0];tri=[struct.unpack_from('<9f',f.read(50),12) for _ in range(count)]
assert count==9210;tri=tri[:-12]
points=json.loads(r.joinpath('points_w_r7.json').read_text());assert len(points['rows'])==80
profile=[]
for line in (r/'case_west/wind_bc/profile.dat').read_text().splitlines()[1:]:
    z,u=map(float,line.split());profile.append((z,u))
def input_u(z):
    for (z0,u0),(z1,u1) in zip(profile,profile[1:]):
        if z0<=z<=z1:return u0+(u1-u0)*(z-z0)/(z1-z0)
    raise ValueError(z)
assert abs(input_u(15.9)-points['uref'])<0.001,(input_u(15.9),points['uref'])

def sections(z):
 seg={}
 for t in tri:
  v=[t[i:i+3] for i in (0,3,6)];p=[]
  for a,b in ((0,1),(1,2),(2,0)):
   za,zb=v[a][2],v[b][2]
   if (za<=z<zb) or (zb<=z<za):
    q=(z-za)/(zb-za);p.append((v[a][0]+q*(v[b][0]-v[a][0]),v[a][1]+q*(v[b][1]-v[a][1])))
  if len(p)==2 and math.dist(*p)>1e-5:
   key=tuple(sorted(tuple(round(c,4) for c in a) for a in p));seg[key]=p
 return list(seg.values())
def mask(ys,xs,z):
 seg=sections(z);bits=[]
 for y in ys:
  crossing=[]
  for (x0,y0),(x1,y1) in seg:
   if (y0<=y<y1) or (y1<=y<y0):crossing.append(x0+(x1-x0)*(y-y0)/(y1-y0))
  crossing.sort();assert len(crossing)%2==0,(z,y,len(crossing))
  parity=0;j=0
  for x in xs:
   while j<len(crossing) and crossing[j]<x:parity^=1;j+=1
   bits.append(bool(parity))
 return bits,len(seg)
with vtk.open('rb') as f:
 m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 rho_header=offset+points_count*12
 rho_offset=field_offset(m,rho_header,'rho_avg',1)
 fluid_offset=field_offset(m,rho_offset+points_count*4,'fluid',1)
 tke_offset=field_offset(m,fluid_offset+points_count*4,'tke',1)
 assert tke_offset+points_count*4==len(m),(tke_offset,len(m))
 def vec(i,j,k):
  assert 0<=i<nx and 0<=j<ny and 0<=k<nz,(i,j,k)
  return struct.unpack_from('>fff',m,offset+((k*ny+j)*nx+i)*12)
 def scalar(off,i,j,k):
  return struct.unpack_from('>f',m,off+((k*ny+j)*nx+i)*4)[0]
 def interp(x,y,z):
  frac=[(v-o)/dx for v,o in zip((x,y,z),org)];ids=[math.floor(v) for v in frac];w=[v-i for v,i in zip(frac,ids)];out=[0.,0.,0.];fluid=0;tke=0.
  for c in range(8):
   i=ids[0]+(c&1);j=ids[1]+((c>>1)&1);k=ids[2]+((c>>2)&1);v=vec(i,j,k);fluid+=int(scalar(fluid_offset,i,j,k)>.5)
   weight=math.prod(w[d] if c&(1<<d) else 1-w[d] for d in range(3))
   for d in range(3):out[d]+=weight*v[d]
   tke+=weight*scalar(tke_offset,i,j,k)
  return math.sqrt(sum(q*q for q in out)),max(tke,0.),fluid
 fit=[];ix=range(max(1,math.ceil((35-org[0])/dx)),min(nx-2,math.floor((465-org[0])/dx))+1);iy=range(max(1,math.ceil((35-org[1])/dx)),min(ny-2,math.floor((465-org[1])/dx))+1)
 xs=[org[0]+i*dx for i in ix];ys=[org[1]+j*dx for j in iy]
 for ztarget in (2.,10.,20.):
  k=round((ztarget-org[2])/dx);z=org[2]+k*dx;actual=[sum(q*q for q in vec(i,j,k))<1e-12 for j in iy for i in ix]
  for shift in itertools.product((0.,dx),repeat=3):
   predicted,nseg=mask([y-shift[1] for y in ys],[x-shift[0] for x in xs],z-shift[2]);tp=sum(a and b for a,b in zip(actual,predicted));na=sum(actual);np=sum(predicted)
   fit.append({'z_vtk':z,'offset_xyz':shift,'iou':tp/(na+np-tp) if na+np-tp else None,'actual_zero':na,'predicted_solid':np,'tp':tp,'nsegments':nseg})
 rows=[]
 for p in points['rows']:
  physical=[p['xls_xy'][0]+1010.50008-760,p['xls_xy'][1]+1000.60004-750,2.]
  samples={}
  for label,shift in (('no_offset',(0.,0.,0.)),('plus_dx',(dx,dx,0.))):
   speed,tke,nfluid=interp(*[v+s for v,s in zip(physical,shift)]);samples[label]={'sim_ratio':speed/points['uref'],'exp_ratio':math.sqrt(speed*speed+2*tke)/points['uref'],'tke_m2s2':tke,'fluid_corners':nfluid}
  rows.append({'id':p['id'],'xls_xy':p['xls_xy'],'before':p['before'],'after':p['after'],'sample':samples})
 # West/upwind strip excluding building (local x=0..49); 10 points in y=100..400.
 upstream=[]
 for x in (5.,15.,25.,35.,42.):
  for z in (2.,5.,10.,15.9):
   values=[interp(x,float(y),z)[0] for y in range(100,401,30)]
   upstream.append({'x_local_m':x,'z_m':z,'n':len(values),'mean_speed_mps':sum(values)/len(values),'input_mps':input_u(z),'fraction_input':sum(values)/len(values)/input_u(z)})
 m.close()
out={'vtk':str(vtk),'file_size':vtk.stat().st_size,'dimensions':[nx,ny,nz],'origin':org,'dx':dx,'quantity':'|interpolated time-mean vector| at physical z=2m / inflow U(15.9m)','mask_note':'Exact-zero mean-speed proxy for solid; base 12 triangles excluded; 0 and +dx per axis','mask_fit':fit,'rows':rows,'upstream':upstream,'uref':points['uref']}
r.joinpath('offset_samples_r7.json').write_text(json.dumps(out,indent=2));print('EXTRACTED',len(rows),'points',len(fit),'mask fits',upstream,flush=True)
for z in sorted(set(q['z_vtk'] for q in fit)):
 print('MASK_BEST',z,sorted((q for q in fit if q['z_vtk']==z),key=lambda q:q['iou'] or -1,reverse=True)[:4],flush=True)
