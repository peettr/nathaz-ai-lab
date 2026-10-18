"""Run two Case E variants only on Colab A100; use a fresh /content root."""
from pathlib import Path
import os,time,tarfile,subprocess,shutil,json,csv,traceback,struct
import numpy as np
R=Path('/content/luw_c3_gate2_v2_1016');R.mkdir(exist_ok=False)
def log(x):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(x)+'\n')
 print(x,flush=True)
def trace_check(path):
 if not path.exists():return None
 with path.open() as f:
  first=f.readline().strip().split(',');last=None
  for line in f:last=line.strip().split(',')
 if not last:return None
 d=dict(zip(first,last));n=int(d['step']);u=float(d['max_u_lattice']);lo=float(d['min_rho']);hi=float(d['max_rho'])
 why=('nonfinite '+d['first_nonfinite_xyz_component'] if d['first_nonfinite_xyz_component'] else 'speed' if u>.3 else 'rho' if n>=3000 and (lo<.9 or hi>1.1) else None)
 return n,u,lo,hi,why
try:
 with tarfile.open('/content/c3_inputs_v2.tar.gz') as t:t.extractall(R,filter='data')
 records=np.load('/content/step4_native_v2_links_sparse.npz')['records']
 # q=0.5 is exactly native TYPE_S only when not overlaid. All unknown/ground/endpoint stay native.
 mask=(records['owner']==1)&(records['q']!=np.float32(.5))
 rec=np.sort(records[mask],order=['cell','direction']);N=500*500*470
 assert len(rec)>100000 and rec['cell'].max()<N and np.all(rec['owner']==1)
 off=np.empty(N+1,dtype='<u4');off[0]=0;off[1:]=np.cumsum(np.bincount(rec['cell'].astype(np.int64),minlength=N),dtype=np.uint32)
 csr=R/'active_building_links.csr'
 with csr.open('wb') as f:
  f.write(struct.pack('<QQ',N,len(rec)));f.write(off.tobytes());f.write(rec['direction'].tobytes());f.write(rec['q'].tobytes());f.write(rec['owner'].tobytes())
 del off
 log('CSR active='+str(len(rec))+' bytes='+str(csr.stat().st_size)+' inactive_half='+str(len(records)-len(rec)))
 src=R/'FluidX3D/src';text=(src/'defines.hpp').read_text()
 assert '#define LINK_IBB' in text and '#define TEMPERATURE' not in text.splitlines()
 for name,ground,a in [('H1',False,'0'),('H2',True,'0.70')]:
  run=R/name;run.mkdir();case=run/'case';shutil.copytree(R/'case',case)
  env=os.environ.copy();env['LUW_IBB_CSR']=str(csr);env['LUW_GROUND_MIX_A']=a
  # Same binary, but ground model enabled/disabled by runtime ground factor only if compiled. H1 needs true no ground model:
  # Build H1 without ground macro; H2 rebuild with it.
  d=src/'defines.hpp';s=d.read_text()
  if ground: assert '#define GROUND_WALL_MODEL' in s
  else:
   assert '#define GROUND_WALL_MODEL' in s
   d.write_text(s.replace('#define GROUND_WALL_MODEL //','#undef GROUND_WALL_MODEL //',1))
  with (run/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-B','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
  log(name+' BUILD '+str(b.returncode));assert b.returncode==0,(run/'build.log').read_text()[-4000:]
  if not ground:d.write_text(s)
  trace=case/'RESULTS/city_stability.csv';t0=time.monotonic()
  with (run/'solver.log').open('w',buffering=1) as f:
   proc=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
   seen=-1;why=None
   while proc.poll() is None:
    time.sleep(6);q=trace_check(trace)
    if q and q[0]!=seen:
     seen=q[0];(run/'latest.json').write_text(json.dumps(q))
     if seen%1000==0:log(name+' STEP '+str(q))
     if q[-1]: why=q[-1];log(name+' STOP '+str(q));proc.terminate();break
    if time.monotonic()-t0>2800:why='solver timeout';proc.terminate();break
   code=proc.wait(timeout=90)
  (run/'solver.exit').write_text(str(code)+'\n');log(name+' END '+str((code,seen,why,round(time.monotonic()-t0))))
  if code!=0 or why:break
  (run/'solver_a.exit').write_text('exit=0\n');(run/'case_a').symlink_to(case,target_is_directory=True)
  shutil.copy2('/content/points_w_r7.json',run/'points_w_r7.json')
  script=Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('{run}')")
  (run/'extract_city.py').write_text(script)
  with (run/'extract.log').open('w') as f:e=subprocess.run(['python3',str(run/'extract_city.py')],cwd=run,stdout=f,stderr=subprocess.STDOUT,timeout=600)
  log(name+' EXTRACT '+str(e.returncode))
  if e.returncode:log((run/'extract.log').read_text()[-1600:])
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log('ERROR '+traceback.format_exc()[-5000:])
finally:(R/'all.done').write_text('done\n')
