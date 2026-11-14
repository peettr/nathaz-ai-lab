from pathlib import Path
import os,time,tarfile,subprocess,shutil,json,csv,traceback,struct,zipfile
import numpy as np
NAME=os.environ['CITY_GROUP']; assert NAME in ('H1','H2')
R=Path('/content/lhigh_city_'+NAME);R.mkdir(exist_ok=False)
def log(x):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(x)+'\n')
 print(x,flush=True)
def trace_check(path):
 if not path.exists():return None
 with path.open() as f:
  names=f.readline().strip().split(',');last=None
  for line in f:last=line.strip().split(',')
 if not last:return None
 d=dict(zip(names,last));n=int(d['step']);u=float(d['max_u_lattice']);lo=float(d['min_rho']);hi=float(d['max_rho'])
 why='nonfinite' if d.get('first_nonfinite_xyz_component') else 'speed' if u>.3 else 'rho' if n>=3000 and (lo<.9 or hi>1.1) else None
 return n,u,lo,hi,why
try:
 with tarfile.open('/content/bisect_stage_linear.tar.gz') as t:t.extractall(R,filter='data')
 stage=R/'stage';src=stage/'FluidX3D';d=src/'src/defines.hpp';s=d.read_text()
 assert '#define LINK_IBB' in s and '#undef GROUND_WALL_MODEL' in s and '#define TEMPERATURE' not in s.splitlines()
 assert 'reflected=outgoing/(2.0f*q)+(2.0f*q-1.0f)/(2.0f*q)*ibb_post[off+ibb_sample_ref2[k]]' in (src/'src/kernel.cpp').read_text()
 case=stage/'case';conf=case/'conf.luwpf';assert 'run_nstep = 31000' in conf.read_text() and 'purge_avg = 20000' in conf.read_text()
 import hashlib
 log('profile sha '+hashlib.sha256((case/'wind_bc/profile.dat').read_bytes()).hexdigest())
 assert hashlib.sha256((case/'wind_bc/profile.dat').read_bytes()).hexdigest().startswith('4fc0eede')
 records=np.load('/content/step4_native_v2_links_sparse.npz')['records'];base=records[(records['owner']==1)&(records['q']!=np.float32(.5))]
 rec=np.sort(base,order=['cell','direction']);N=500*500*470
 off=np.empty(N+1,dtype='<u4');off[0]=0;off[1:]=np.cumsum(np.bincount(rec['cell'].astype(np.int64),minlength=N),dtype=np.uint32)
 csr=R/'active_building_links.csr'
 with csr.open('wb') as f:
  f.write(struct.pack('<QQ',N,len(rec)));f.write(off.tobytes());f.write(rec['direction'].tobytes());f.write(rec['q'].tobytes());f.write(rec['owner'].tobytes())
 assert len(rec)==131569;log('CSR '+str(len(rec))+' bytes '+str(csr.stat().st_size))
 if NAME=='H2':
  assert '#undef GROUND_WALL_MODEL // no ground model in Case E bisect' in s
  d.write_text(s.replace('#undef GROUND_WALL_MODEL // no ground model in Case E bisect','#define GROUND_WALL_MODEL // H2 fixed a=0.70',1))
 with (R/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-B','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=700)
 log('BUILD '+str(b.returncode))
 if b.returncode:raise RuntimeError((R/'build.log').read_text()[-2500:])
 env=os.environ.copy();env['LUW_IBB_CSR']=str(csr);env['LUW_GROUND_MIX_A']='0.70' if NAME=='H2' else '0'
 trace=case/'RESULTS/city_stability.csv';t0=time.monotonic()
 with (R/'solver.log').open('w',buffering=1) as f:
  p=subprocess.Popen([str(src/'bin/FluidX3D'),str(conf)],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
  seen=-1;why=None
  while p.poll() is None:
   time.sleep(6);q=trace_check(trace)
   if q and q[0]!=seen:
    seen=q[0];(R/'latest.json').write_text(json.dumps(q))
    if seen%1000==0:log('STEP '+str(q))
    if q[-1]:why=q[-1];log('STOP '+str(q));p.terminate();break
   if time.monotonic()-t0>2400:why='timeout';p.terminate();break
  code=p.wait(timeout=90)
 (R/'solver.exit').write_text(str(code)+'\n');log('END '+str((code,seen,why,round(time.monotonic()-t0))))
 if code==0 and not why:
  (R/'solver_a.exit').write_text('exit=0\n');(R/'case_a').symlink_to(case,target_is_directory=True)
  shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
  script=Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('{R}')")
  (R/'extract_city.py').write_text(script)
  with (R/'extract.log').open('w') as f:e=subprocess.run(['python3',str(R/'extract_city.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=600)
  log('EXTRACT '+str(e.returncode))
  if e.returncode:log((R/'extract.log').read_text()[-1500:])
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log('ERROR '+traceback.format_exc()[-3000:])
finally:
 with zipfile.ZipFile('/content/lhigh_city_'+NAME+'_evidence.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
  for p in R.rglob('*'):
   if p.is_file() and p.name in ('progress.log','solver.log','build.log','solver.exit','latest.json','extract.log','offset_samples_a_r10.json','city_stability.csv','error.txt'):
    z.write(p,str(p.relative_to(R)))
 (R/'all.done').write_text('done\n')
