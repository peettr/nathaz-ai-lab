"""Colab: three immutable 500x200x270 empty-field variants."""
from pathlib import Path
import subprocess, tarfile, shutil, time, struct, traceback, json, math, mmap
r=Path('/content/luw_wall_cont4');r.mkdir(exist_ok=False)
with tarfile.open('/content/empty_cont4_inputs.tar.gz') as tar:tar.extractall(r,filter='data')
source=r/'FluidX3D'; ex=r/'example_ProfileResearch_noDEM'
variants=('off','on_first','on_second')
def log(s):
 print(s,flush=True)
 with (r/'progress.log').open('a') as f:f.write(s+'\n')
def extract(v):
 import mmap
 files=list((r/v/'RESULTS/vtk').glob('*avg*.vtk'));assert len(files)==1,files
 path=files[0]
 with path.open('rb') as f:
  hdr=[]
  for _ in range(20):
   s=f.readline().decode('ascii','replace').strip();hdr.append(s)
   if s.startswith('LOOKUP_TABLE'):break
  offset=f.tell();nx,ny,nz=map(int,next(s for s in hdr if s.startswith('DIMENSIONS')).split()[1:]);origin=list(map(float,next(s for s in hdr if s.startswith('ORIGIN')).split()[1:]));n=nx*ny*nz
  assert (nx,ny,nz)==(500,200,270) and origin[2]==-20,(nx,ny,nz,origin)
  m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  def field(off,name,c):
   tag=(f'SCALARS {name} float {c}\nLOOKUP_TABLE default\n').encode();assert m[off:off+len(tag)]==tag,(name,m[off:off+120]);return off+len(tag)
  rho=field(offset+n*12,'rho_avg',1);fluid=field(rho+n*4,'fluid',1);tke=field(fluid+n*4,'tke',1)
  def s(off,x,y,z):return struct.unpack_from('>f',m,off+((z*ny+y)*nx+x)*4)[0]
  def vec(x,y,z):return struct.unpack_from('>fff',m,offset+((z*ny+y)*nx+x)*12)
  prof=[tuple(map(float,line.split())) for line in (r/v/'wind_bc/profile.dat').read_text().splitlines()[1:]]
  def inlet(z):
   for (a,u),(b,w) in zip(prof,prof[1:]):
    if a<=z<=b:return u+(z-a)*(w-u)/(b-a)
   raise ValueError(z)
  rows=[]
  for x in (5,50,100,200,250,300,350,400,450,495):
   for h in (2.,5.,15.9):
    z=h-origin[2];lo=int(z);w=z-lo
    samples=[]
    for y in (40,70,100,130,160):
     a,b=vec(x,y,lo),vec(x,y,lo+1)
     uv=[p*(1-w)+q*w for p,q in zip(a,b)]
     k=s(tke,x,y,lo)*(1-w)+s(tke,x,y,lo+1)*w
     samples.append((*uv,k))
    avg=[sum(a[i] for a in samples)/len(samples) for i in range(4)]
    speed=math.sqrt(sum(t*t for t in avg[:3]))
    rows.append(dict(x=x,z=h,speed=speed,ratio=speed/inlet(h),k=avg[3],TI=math.sqrt(max(2*avg[3]/3,0))/speed,mean_u=avg))
  m.close()
 (r/f'{v}_profile.json').write_text(json.dumps(dict(grid=[nx,ny,nz],origin=origin,rows=rows),indent=2))
 log('EXTRACT '+v+' '+str([(a['x'],round(a['ratio'],3),round(a['TI'],3)) for a in rows if a['z']==2 and a['x'] in (200,300,400)]))
for v in variants:
 try:
  src=r/('src_'+v);shutil.copytree(source,src)
  defines=src/'src/defines.hpp';dt=defines.read_text()
  if v!='off':dt=dt.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL')
  if v=='on_second':dt=dt.replace('//#define GROUND_WALL_SECOND_LAYER','#define GROUND_WALL_SECOND_LAYER')
  defines.write_text(dt)
  t=time.monotonic()
  with (r/f'build_{v}.log').open('w') as out:cp=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=out,stderr=subprocess.STDOUT,timeout=300)
  log('BUILD '+v+' rc='+str(cp.returncode)+' sec='+str(round(time.monotonic()-t,2)))
  assert cp.returncode==0
  case=r/v;(case/'proj_temp').mkdir(parents=True);(case/'wind_bc').mkdir()
  for rel in ('conf.luwpf','wind_bc/profile.dat','proj_temp/CaseE_PF.stl'):
   shutil.copy2(ex/rel,case/rel)
  c=case/'conf.luwpf';txt=c.read_text()
  for old,new in [('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 500.000000]'),('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]'),('angle = [0, 90, 180, 270]','angle = [270]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n','cell_size = 1.0\n')]:
   assert txt.count(old)==1,(old,txt.count(old));txt=txt.replace(old,new)
  txt+='\nrun_nstep = 31000\npurge_avg = 20000\npurge_avg_stride = 40\noutput_tke_ti_tls = [tke]\n'
  c.write_text(txt)
  t=time.monotonic()
  with (r/f'solver_{v}.log').open('w',buffering=1) as out:
   cp=subprocess.run([str(src/'bin/FluidX3D'),str(c)],cwd=case,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=1800)
  log('SOLVE '+v+' rc='+str(cp.returncode)+' sec='+str(round(time.monotonic()-t,2)))
  assert cp.returncode==0
  extract(v)
 except Exception:
  log('FAIL '+v+' '+traceback.format_exc());(r/'done.txt').write_text('FAIL '+v+'\n');break
else:(r/'done.txt').write_text('COMPLETE\n')
