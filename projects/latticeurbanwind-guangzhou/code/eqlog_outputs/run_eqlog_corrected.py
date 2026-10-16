from pathlib import Path
import tarfile,subprocess,time,traceback,shutil,mmap,struct,json,math
R=Path('/content/luw_eqlog_corrected_20261015');R.mkdir(exist_ok=False)
def log(s):
 print(s,flush=True)
 with (R/'progress.log').open('a') as f:f.write(s+'\n')
try:
 with tarfile.open('/content/eqlog_corrected_inputs.tar.gz') as t:t.extractall(R,filter='data')
 src=R/'FluidX3D';d=src/'src/defines.hpp';s=d.read_text();assert s.count('//#define GROUND_WALL_MODEL')==1;d.write_text(s.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL'))
 t0=time.monotonic()
 with (R/'build.log').open('w') as f:cp=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=300)
 log(f'BUILD rc={cp.returncode} sec={time.monotonic()-t0:.1f}');assert cp.returncode==0
 case=R/'case';t0=time.monotonic()
 with (R/'solver.log').open('w',buffering=1) as f:cp=subprocess.run([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
 (R/'exit.txt').write_text(str(cp.returncode));log(f'SOLVE rc={cp.returncode} sec={time.monotonic()-t0:.1f}');assert cp.returncode==0
 files=list((case/'RESULTS/vtk').glob('*avg*.vtk'));assert len(files)==1
 with files[0].open('rb') as f:
  hdr=[]
  for _ in range(22):
   line=f.readline().decode('ascii','replace').strip();hdr.append(line)
   if line.startswith('LOOKUP_TABLE'):break
  off=f.tell();nx,ny,nz=map(int,next(s for s in hdr if s.startswith('DIMENSIONS')).split()[1:]);org=list(map(float,next(s for s in hdr if s.startswith('ORIGIN')).split()[1:]));n=nx*ny*nz
  assert (nx,ny,nz)==(500,200,270) and org[2]==-20
  m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  def field(start,name,c):
   tag=(f'SCALARS {name} float {c}\nLOOKUP_TABLE default\n').encode();assert m[start:start+len(tag)]==tag;return start+len(tag)
  rho=field(off+n*12,'rho_avg',1);fluid=field(rho+n*4,'fluid',1);tke=field(fluid+n*4,'tke',1)
  def scalar(o,x,y,z):return struct.unpack_from('>f',m,o+((z*ny+y)*nx+x)*4)[0]
  def vec(x,y,z):return struct.unpack_from('>fff',m,off+((z*ny+y)*nx+x)*12)
  par=json.loads(Path('/content/eqlog_parameters.json').read_text());us=par['ustar_mps'];z0=par['z0_m'];k=par['kappa'];inlet=lambda z:us/k*math.log((z+z0)/z0)
  rows=[]
  for x in (5,100,200,300,400,495):
   for z in range(1,61):
    q=[(*vec(x,y,z+20),scalar(tke,x,y,z+20)) for y in (40,70,100,130,160)]
    a=[sum(v[i] for v in q)/len(q) for i in range(4)];speed=math.sqrt(sum(t*t for t in a[:3]))
    rows.append(dict(x=x,z=z,speed=speed,ratio=speed/inlet(z),k=a[3],TI=math.sqrt(max(2*a[3]/3,0))/speed if speed else None,u=a[:3]))
  m.close()
 (R/'profile_on_corrected.json').write_text(json.dumps(dict(grid=[nx,ny,nz],origin=org,rows=rows)))
 log('EXTRACT '+str([(a['x'],round(a['ratio'],4)) for a in rows if a['z']==2]))
 (R/'done.txt').write_text('COMPLETE\n')
except Exception:
 log('FAIL '+traceback.format_exc());(R/'done.txt').write_text('FAIL\n')
