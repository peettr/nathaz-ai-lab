from pathlib import Path
import tarfile,subprocess,time,traceback,shutil,mmap,struct,json,math
R=Path('/content/luw_eqlog_20261015');R.mkdir(exist_ok=False)
def log(s):
 print(s,flush=True)
 with (R/'progress.log').open('a') as f:f.write(s+'\n')
def extract(case,label):
 files=list((case/'RESULTS/vtk').glob('*avg*.vtk'));assert len(files)==1,files
 with files[0].open('rb') as f:
  hdr=[]
  for _ in range(22):
   s=f.readline().decode('ascii','replace').strip();hdr.append(s)
   if s.startswith('LOOKUP_TABLE'):break
  off=f.tell();nx,ny,nz=map(int,next(s for s in hdr if s.startswith('DIMENSIONS')).split()[1:]);org=list(map(float,next(s for s in hdr if s.startswith('ORIGIN')).split()[1:]));n=nx*ny*nz
  assert (nx,ny,nz)==(500,200,270) and org[2]==-20,(nx,ny,nz,org)
  m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  def field(start,name,c):
   tag=(f'SCALARS {name} float {c}\nLOOKUP_TABLE default\n').encode();assert m[start:start+len(tag)]==tag;return start+len(tag)
  rho=field(off+n*12,'rho_avg',1);fluid=field(rho+n*4,'fluid',1);tke=field(fluid+n*4,'tke',1)
  def scalar(o,x,y,z):return struct.unpack_from('>f',m,o+((z*ny+y)*nx+x)*4)[0]
  def vec(x,y,z):return struct.unpack_from('>fff',m,off+((z*ny+y)*nx+x)*12)
  params=json.loads(Path('/content/eqlog_parameters.json').read_text());us=params['ustar_mps'];z0=params['z0_m'];k=params['kappa']
  inlet=lambda z:us/k*math.log((z+z0)/z0)
  rows=[]
  for x in (5,100,200,300,400,495):
   for z in range(1,61):
    samples=[(*vec(x,y,z+20),scalar(tke,x,y,z+20)) for y in (40,70,100,130,160)]
    a=[sum(q[i] for q in samples)/len(samples) for i in range(4)];speed=math.sqrt(sum(t*t for t in a[:3]))
    rows.append(dict(x=x,z=z,speed=speed,ratio=speed/inlet(z),k=a[3],TI=math.sqrt(max(2*a[3]/3,0))/speed if speed else None,u=a[:3]))
  # approximate resolved mean advective and pressure fluxes over x=100/400 and top z=60 (diagnostic only)
  # pressure requires rho and EOS, but unknown t=mean(rho*u*u) Reynolds stress; do not assert closure.
  boundaries={}
  for x in (100,400):
   for z in (2,5,16,60):
    samples=[(vec(x,y,z+20),scalar(rho,x,y,z+20)) for y in (40,70,100,130,160)]
    boundaries[f'{x},{z}']={'mean_u':[sum(q[0][i] for q in samples)/len(samples) for i in range(3)],'mean_rho':sum(q[1] for q in samples)/len(samples)}
  m.close()
 (R/f'profile_{label}.json').write_text(json.dumps(dict(grid=[nx,ny,nz],origin=org,rows=rows,boundary_samples=boundaries)))
 log('EXTRACT '+label+' '+str([(a['x'],round(a['ratio'],4)) for a in rows if a['z']==2]))
try:
 with tarfile.open('/content/eqlog_inputs.tar.gz') as t:t.extractall(R,filter='data')
 for label in ('off','on'):
  source=R/f'src_{label}';shutil.copytree(R/'FluidX3D',source)
  if label=='on':
   d=source/'src/defines.hpp';s=d.read_text();assert s.count('//#define GROUND_WALL_MODEL')==1;d.write_text(s.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL'))
  t0=time.monotonic()
  with (R/f'build_{label}.log').open('w') as f:cp=subprocess.run(['make','Linux','-j4'],cwd=source,stdout=f,stderr=subprocess.STDOUT,timeout=300)
  log(f'BUILD {label} rc={cp.returncode} sec={time.monotonic()-t0:.1f}');assert cp.returncode==0
  case=R/f'case_{label}';shutil.copytree(R/'case',case)
  t0=time.monotonic()
  with (R/f'solver_{label}.log').open('w',buffering=1) as f:cp=subprocess.run([str(source/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
  (R/f'exit_{label}.txt').write_text(str(cp.returncode));log(f'SOLVE {label} rc={cp.returncode} sec={time.monotonic()-t0:.1f}');assert cp.returncode==0
  extract(case,label)
 (R/'done.txt').write_text('COMPLETE\n')
except Exception:
 log('FAIL '+traceback.format_exc());(R/'done.txt').write_text('FAIL\n')
