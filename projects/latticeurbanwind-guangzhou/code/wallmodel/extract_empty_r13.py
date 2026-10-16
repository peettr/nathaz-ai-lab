"""Extract small empty-field centerline profiles and inlet/outlet momentum proxies."""
from pathlib import Path
import mmap,struct,json,math
r=Path('/content/luw_wall_empty_r13');out={}
profile=[]
for line in (r/'case_off/wind_bc/profile.dat').read_text().splitlines()[1:]:
 z,u=map(float,line.split());profile.append((z,u))
def inlet(z):
 for (a,u),(b,v) in zip(profile,profile[1:]):
  if a<=z<=b:return u+(z-a)*(v-u)/(b-a)
 raise ValueError(z)
for variant in ('off','on','onfixed'):
 assert (r/f'{variant}.exit').read_text().startswith('exit=0')
 files=list((r/f'case_{variant}/RESULTS/vtk').glob('*avg*.vtk'));assert len(files)==1,files
 path=files[0]
 with path.open('rb') as f:
  header=[]
  for _ in range(15):
   s=f.readline().decode('ascii','replace').strip();header.append(s)
   if s.startswith('LOOKUP_TABLE'):break
  offset=f.tell();nx,ny,nz=map(int,next(s for s in header if s.startswith('DIMENSIONS')).split()[1:]);origin=list(map(float,next(s for s in header if s.startswith('ORIGIN')).split()[1:]));dx=float(next(s for s in header if s.startswith('SPACING')).split()[1]);n=nx*ny*nz
  assert (nx,ny,nz)==(500,64,270) and dx==1 and origin[2]==-20
  m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  def field(off,name,c):
   tag=(f'SCALARS {name} float {c}\nLOOKUP_TABLE default\n').encode();assert m[off:off+len(tag)]==tag,(name,m[off:off+150]);return off+len(tag)
  rho=field(offset+n*12,'rho_avg',1);fluid=field(rho+n*4,'fluid',1);tke=field(fluid+n*4,'tke',1)
  def s(off,x,y,z):return struct.unpack_from('>f',m,off+((z*ny+y)*nx+x)*4)[0]
  def vec(x,y,z):return struct.unpack_from('>fff',m,offset+((z*ny+y)*nx+x)*12)
  def sample(x,y,h):
   zz=h-origin[2];k=int(zz);w=zz-k;v0=vec(x,y,k);v1=vec(x,y,k+1);v=[a*(1-w)+b*w for a,b in zip(v0,v1)];kv=s(tke,x,y,k)*(1-w)+s(tke,x,y,k+1)*w;return [*v,kv]
  rows=[]
  for x in (5,25,50,100,200,300,400,450,475,495):
   for h in (2.,5.,15.9):
    sample_rows=[sample(x,y,h) for y in (16,24,32,40,48)]
    mean=[sum(v[i] for v in sample_rows)/len(sample_rows) for i in range(4)];speed=math.sqrt(sum(v*v for v in mean[:3]));ti=math.sqrt(max(2*mean[3]/3,0))/speed if speed else None
    rows.append(dict(x=x,z=h,mean_u=mean,speed=speed,k=mean[3],TI_isotropic=ti,inlet_speed=inlet(h),ratio=speed/inlet(h)))
  # Approximate cross-section mean advective and pressure proxies, not full momentum budget.
  proxies=[]
  for x in (5,100,250,450,495):
   count=0;adv=0.;p=0.;mean_ux=0.
   for z in range(21,268):
    for y in range(1,ny-1):
     if s(fluid,x,y,z)<.5:continue
     u=vec(x,y,z)[0];rr=s(rho,x,y,z);adv+=rr*u*u;p+=(rr-1)/3;mean_ux+=u;count+=1
   proxies.append(dict(x=x,n=count,advective_flux_proxy=adv,pressure_proxy=p,mean_ux=mean_ux/count))
  out[variant]=dict(vtk=str(path),size_bytes=path.stat().st_size,grid=[nx,ny,nz],origin=origin,rows=rows,proxies=proxies)
  m.close()
(r/'empty_profiles_fixed_r13.json').write_text(json.dumps(out,indent=2));print('EXTRACT_DONE',[(v,len(out[v]['rows']),out[v]['proxies']) for v in out],flush=True)
