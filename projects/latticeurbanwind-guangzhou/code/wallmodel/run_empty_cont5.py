"""On Colab: isolated damping variant, preserve prior cont4 runs."""
from pathlib import Path
import subprocess,tarfile,shutil,time,json,struct,mmap,math,traceback
r=Path('/content/luw_wall_cont5b');r.mkdir(exist_ok=False)
with tarfile.open('/content/empty_cont5b_inputs.tar.gz') as t:t.extractall(r,filter='data')
src=r/'FluidX3D';ex=r/'example_ProfileResearch_noDEM';v='damped'
def log(s):
 print(s,flush=True)
 with (r/'progress.log').open('a') as f:f.write(s+'\n')
try:
 build=r/'src_damped';shutil.copytree(src,build)
 p=build/'src/defines.hpp';s=p.read_text();assert '//#define GROUND_WALL_MODEL' in s and '//#define GROUND_WALL_SGS_DAMP' in s
 p.write_text(s.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL').replace('//#define GROUND_WALL_SGS_DAMP','#define GROUND_WALL_SGS_DAMP'))
 t=time.monotonic()
 with (r/'build_damped.log').open('w') as out:cp=subprocess.run(['make','Linux','-j4'],cwd=build,stdout=out,stderr=subprocess.STDOUT,timeout=300)
 log(f'BUILD rc={cp.returncode} seconds={time.monotonic()-t:.2f}');assert cp.returncode==0
 case=r/'damped';(case/'proj_temp').mkdir(parents=True);(case/'wind_bc').mkdir()
 for name in ('conf.luwpf','wind_bc/profile.dat','proj_temp/CaseE_PF.stl'):shutil.copy2(ex/name,case/name)
 c=case/'conf.luwpf';txt=c.read_text()
 for old,new in [('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 500.000000]'),('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]'),('angle = [0, 90, 180, 270]','angle = [270]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n','cell_size = 1.0\n')]:
  assert txt.count(old)==1,(old,txt.count(old));txt=txt.replace(old,new)
 txt+='\nrun_nstep = 31000\npurge_avg = 20000\npurge_avg_stride = 40\noutput_tke_ti_tls = [tke]\n';c.write_text(txt)
 t=time.monotonic()
 with (r/'solver_damped.log').open('w',buffering=1) as out:cp=subprocess.run([str(build/'bin/FluidX3D'),str(c)],cwd=case,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=1800)
 log(f'SOLVE rc={cp.returncode} seconds={time.monotonic()-t:.2f}');assert cp.returncode==0
 files=list((case/'RESULTS/vtk').glob('*avg*.vtk'));assert len(files)==1,files
 with files[0].open('rb') as f:
  hdr=[]
  for _ in range(20):
   s=f.readline().decode('ascii','replace').strip();hdr.append(s)
   if s.startswith('LOOKUP_TABLE'):break
  offset=f.tell();nx,ny,nz=map(int,next(s for s in hdr if s.startswith('DIMENSIONS')).split()[1:]);org=list(map(float,next(s for s in hdr if s.startswith('ORIGIN')).split()[1:]));n=nx*ny*nz
  assert (nx,ny,nz)==(500,200,270) and org[2]==-20
  m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  def field(off,name,c):
   tag=(f'SCALARS {name} float {c}\nLOOKUP_TABLE default\n').encode();assert m[off:off+len(tag)]==tag;return off+len(tag)
  rho=field(offset+n*12,'rho_avg',1);fluid=field(rho+n*4,'fluid',1);tke=field(fluid+n*4,'tke',1)
  def scalar(off,x,y,z):return struct.unpack_from('>f',m,off+((z*ny+y)*nx+x)*4)[0]
  def vec(x,y,z):return struct.unpack_from('>fff',m,offset+((z*ny+y)*nx+x)*12)
  profile=[tuple(map(float,line.split())) for line in (case/'wind_bc/profile.dat').read_text().splitlines()[1:]]
  def inlet(z):
   for (a,u),(b,w) in zip(profile,profile[1:]):
    if a<=z<=b:return u+(z-a)*(w-u)/(b-a)
   raise ValueError(z)
  rows=[]
  for x in (5,50,100,200,250,300,350,400,450,495):
   for z in range(1,61):
    samples=[]
    for y in (40,70,100,130,160):samples.append((*vec(x,y,z+20),scalar(tke,x,y,z+20)))
    avg=[sum(a[i] for a in samples)/len(samples) for i in range(4)]
    speed=math.sqrt(sum(t*t for t in avg[:3]));rows.append(dict(x=x,z=z,speed=speed,ratio=speed/inlet(z),k=avg[3],TI=math.sqrt(max(2*avg[3]/3,0))/speed,mean_u=avg))
  m.close()
 (r/'damped_profile.json').write_text(json.dumps(dict(grid=[nx,ny,nz],origin=org,rows=rows)))
 log('EXTRACT '+str([(v['x'],round(v['ratio'],3),round(v['TI'],3)) for v in rows if v['z']==2 and v['x'] in (200,300,400)]))
 (r/'done.txt').write_text('COMPLETE\n')
except Exception:
 log('FAIL '+traceback.format_exc());(r/'done.txt').write_text('FAIL\n')
