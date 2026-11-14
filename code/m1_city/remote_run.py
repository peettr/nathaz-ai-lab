from pathlib import Path
import os,tarfile,subprocess,time,csv,zipfile,traceback,hashlib,shutil,struct
import numpy as np
TAG=os.environ['RUN_TAG']; assert TAG in ('D80','H1','H2')
R=Path('/content/m1city_'+TAG);R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(s,flush=True)
def status(path):
 if not path.exists():return None
 with path.open() as f:
  header=f.readline().strip().split(',');tail=None
  for line in f:tail=line.strip().split(',')
 if not tail:return None
 d=dict(zip(header,tail));step=int(d['step']);u=float(d['max_u_lattice']);lo=float(d['min_rho']);hi=float(d['max_rho'])
 why='nonfinite' if d.get('first_nonfinite_xyz_component') else 'speed' if u>.3 else 'rho' if step>=3000 and (lo<.9 or hi>1.1) else None
 return step,u,lo,hi,why
try:
 if TAG=='D80':
  with tarfile.open('/content/reg.tar.gz') as t:t.extractall(R,filter='data')
  src=R/'dfg_laminar_stage_FluidX3D'
  with (R/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=700)
  log('BUILD '+str(b.returncode));assert b.returncode==0,(R/'build.log').read_text()[-1500:]
  env=os.environ.copy();env.update(IBB_TEST_KIND='dfg',DFG_D='80',DFG_STEPS=str(round(100/.018*80)),DFG_OUT=str(R/'lam_D80_ibb_full.csv'),LUW_IBB_CSR='/content/dfg_D80.csr')
  start=time.monotonic()
  with (R/'solver.log').open('w',buffering=1) as f:p=subprocess.run([str(src/'bin/FluidX3D')],cwd=src,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
  log('DFG exit='+str(p.returncode)+' seconds='+str(round(time.monotonic()-start)));(R/'solver.exit').write_text(str(p.returncode));assert p.returncode==0
 else:
  with tarfile.open('/content/city.tar.gz') as t:t.extractall(R,filter='data')
  stage=R/'stage';src=stage/'FluidX3D';case=stage/'case';conf=case/'conf.luwpf';assert 'run_nstep = 31000' in conf.read_text()
  profile=hashlib.sha256((case/'wind_bc/profile.dat').read_bytes()).hexdigest();log('profile '+profile);assert profile.startswith('4fc0eede')
  records=np.load('/content/step4_native_v2_links_sparse.npz')['records'];rec=np.sort(records[(records['owner']==1)&(records['q']!=np.float32(.5))],order=['cell','direction'])
  assert len(rec)==131569
  n=500*500*470;off=np.empty(n+1,dtype='<u4');off[0]=0;off[1:]=np.cumsum(np.bincount(rec['cell'].astype(np.int64),minlength=n),dtype=np.uint32)
  csr=R/'active.csr'
  with csr.open('wb') as f:f.write(struct.pack('<QQ',n,len(rec)));f.write(off.tobytes());f.write(rec['direction'].tobytes());f.write(rec['q'].tobytes());f.write(rec['owner'].tobytes())
  s=(src/'src/defines.hpp').read_text();assert '#define LINK_IBB' in s and '#define TEMPERATURE' not in s.splitlines()
  if TAG=='H2':
   assert '#undef GROUND_WALL_MODEL // no ground model in Case E bisect' in s
   (src/'src/defines.hpp').write_text(s.replace('#undef GROUND_WALL_MODEL // no ground model in Case E bisect','#define GROUND_WALL_MODEL // fixed a=0.70',1))
  with (R/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-B','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=900)
  log('BUILD '+str(b.returncode));assert b.returncode==0,(R/'build.log').read_text()[-2500:]
  env=os.environ.copy();env.update(LUW_IBB_CSR=str(csr),LUW_GROUND_MIX_A='0.70' if TAG=='H2' else '0')
  trace=case/'RESULTS/city_stability.csv';t0=time.monotonic()
  with (R/'solver.log').open('w',buffering=1) as f:
   p=subprocess.Popen([str(src/'bin/FluidX3D'),str(conf)],cwd=case,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
   seen=-1;why=None
   while p.poll() is None:
    time.sleep(8);q=status(trace)
    if q and q[0]!=seen:
     seen=q[0]
     if seen%1000==0:log('STEP '+str(q))
     if q[-1]:why=q[-1];log('STOP '+str(q));p.terminate();break
    if time.monotonic()-t0>2700:why='timeout';p.terminate();break
   code=p.wait(timeout=120)
  log('END '+str((code,seen,why,round(time.monotonic()-t0))));(R/'solver.exit').write_text(str(code));(R/'stop_reason.txt').write_text(str(why))
  if code==0 and not why:
   (R/'solver_a.exit').write_text('exit=0\n');(R/'case_a').symlink_to(case,target_is_directory=True)
   shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
   script=Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('{R}')")
   (R/'extract_city.py').write_text(script)
   with (R/'extract.log').open('w') as f:e=subprocess.run(['python3',str(R/'extract_city.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=600)
   log('EXTRACT '+str(e.returncode))
   if e.returncode:log((R/'extract.log').read_text()[-1200:])
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log('ERROR '+traceback.format_exc()[-2800:])
finally:
 with zipfile.ZipFile('/content/m1city_'+TAG+'.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
  for p in R.rglob('*'):
   if p.is_file() and p.name in ('progress.log','solver.log','build.log','solver.exit','stop_reason.txt','extract.log','offset_samples_a_r10.json','city_stability.csv','f0_minimum.csv','lam_D80_ibb_full.csv','error.txt'):
    z.write(p,str(p.relative_to(R)))
 (R/'all.done').write_text('done\n')
