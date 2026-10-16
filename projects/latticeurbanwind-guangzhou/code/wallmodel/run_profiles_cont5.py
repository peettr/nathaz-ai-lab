"""Colab: independent complete-height baseline and first-layer profiles."""
from pathlib import Path
import subprocess,time,shutil,json,math,mmap,struct,traceback
R=Path('/content/luw_wall_cont5profiles');R.mkdir(exist_ok=False)
base=Path('/content/luw_wall_cont5b');assert (base/'damped_profile.json').exists() and len(list((base/'damped/RESULTS/vtk').glob('*avg*.vtk')))==1
def log(s):
 print(s,flush=True)
 with (R/'progress.log').open('a') as f:f.write(s+'\n')
def extract(case,v):
 files=list((case/'RESULTS/vtk').glob('*avg*.vtk'));assert len(files)==1
 with files[0].open('rb') as f:
  hdr=[]
  for _ in range(20):
   s=f.readline().decode('ascii','replace').strip();hdr.append(s)
   if s.startswith('LOOKUP_TABLE'):break
  off=f.tell();nx,ny,nz=map(int,next(s for s in hdr if s.startswith('DIMENSIONS')).split()[1:]);org=list(map(float,next(s for s in hdr if s.startswith('ORIGIN')).split()[1:]));n=nx*ny*nz;assert (nx,ny,nz)==(500,200,270) and org[2]==-20
  m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  def field(start,name,c):
   tag=(f'SCALARS {name} float {c}\nLOOKUP_TABLE default\n').encode();assert m[start:start+len(tag)]==tag;return start+len(tag)
  rho=field(off+n*12,'rho_avg',1);fluid=field(rho+n*4,'fluid',1);tke=field(fluid+n*4,'tke',1)
  def scalar(o,x,y,z):return struct.unpack_from('>f',m,o+((z*ny+y)*nx+x)*4)[0]
  def vec(x,y,z):return struct.unpack_from('>fff',m,off+((z*ny+y)*nx+x)*12)
  profile=[tuple(map(float,line.split())) for line in (case/'wind_bc/profile.dat').read_text().splitlines()[1:]]
  def inlet(z):
   for (a,u),(b,w) in zip(profile,profile[1:]):
    if a<=z<=b:return u+(z-a)*(w-u)/(b-a)
   return None
  rows=[]
  for x in (5,50,100,200,250,300,350,400,450,495):
   for z in range(1,61):
    a=[(*vec(x,y,z+20),scalar(tke,x,y,z+20)) for y in (40,70,100,130,160)]
    av=[sum(q[i] for q in a)/len(a) for i in range(4)];speed=math.sqrt(sum(t*t for t in av[:3]))
    ref=inlet(z);rows.append(dict(x=x,z=z,speed=speed,ratio=speed/ref if ref else None,k=av[3],TI=math.sqrt(max(2*av[3]/3,0))/speed,mean_u=av))
  m.close()
 (R/f'{v}_profile.json').write_text(json.dumps(dict(grid=[nx,ny,nz],origin=org,rows=rows)))
 log('EXTRACT '+v+' '+str([(a['x'],round(a['ratio'],3)) for a in rows if a['z']==2 and a['x'] in (200,300,400)]))
for v in ('off','on_first'):
 try:
  src=R/f'src_{v}';shutil.copytree(base/'FluidX3D',src)
  p=src/'src/defines.hpp';s=p.read_text()
  if v=='on_first':s=s.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL')
  p.write_text(s)
  t=time.monotonic()
  with (R/f'build_{v}.log').open('w') as f:cp=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=300)
  log(f'BUILD {v} rc={cp.returncode} sec={time.monotonic()-t:.2f}');assert cp.returncode==0
  case=R/v;shutil.copytree(base/'damped',case,ignore=shutil.ignore_patterns('RESULTS','output','*.log'))
  t=time.monotonic()
  with (R/f'solver_{v}.log').open('w',buffering=1) as f:cp=subprocess.run([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
  log(f'SOLVE {v} rc={cp.returncode} sec={time.monotonic()-t:.2f}');assert cp.returncode==0
  extract(case,v)
 except Exception:
  log('FAIL '+v+' '+traceback.format_exc());(R/'done.txt').write_text('FAIL '+v+'\n');break
else:(R/'done.txt').write_text('COMPLETE\n')
