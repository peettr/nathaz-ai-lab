from pathlib import Path
import os,sys,tarfile,subprocess,time,traceback,shutil
T=sys.argv[1]; assert T in ('C1','C1smoke','C1smoke2','C1wide','C05')
R=Path('/content/luw_crop_'+T); R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(s,flush=True)
def status(p):
 if not p.exists():return None
 with p.open() as f:
  h=f.readline().strip().split(',');line=''
  for q in f:line=q
 return dict(zip(h,line.strip().split(','))) if line else None
try:
 with tarfile.open('/content/crop_'+('C1v2' if T in ('C1smoke2','C1') else ('C1' if T=='C1smoke' else T))+'.tar.gz') as tar:tar.extractall(R,filter='data')
 defs=R/'FluidX3D/src/defines.hpp';s=defs.read_text();assert s.count('//#define CITY_STABILITY_MONITOR')==1
 assert '#define TEMPERATURE' not in [x.strip() for x in s.splitlines()]
 defs.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 if T.startswith('C1smoke'):
  conf=R/'case/conf.luwpf';s=conf.read_text().replace('run_nstep = 31000','run_nstep = 1').replace('purge_avg = 20000','purge_avg = 0');conf.write_text(s)
 with (R/'build.log').open('w') as f:
  ret=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 log('BUILD '+str(ret.returncode));assert ret.returncode==0,(R/'build.log').read_text()[-2000:]
 case=R/'case';trace=case/'RESULTS/city_stability.csv';start=time.monotonic()
 with (R/'solver.log').open('w',buffering=1) as f:
  proc=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  seen=-1;reason=None
  while proc.poll() is None:
   time.sleep(10);q=status(trace)
   if q and int(q['step'])!=seen:
    seen=int(q['step']);lo=float(q['min_rho']);hi=float(q['max_rho']);u=float(q['max_u_lattice'])
    if seen%1000==0:log(f'STEP {seen} rho=[{lo},{hi}] umax={u}')
    if q['first_nonfinite_xyz_component'] or u>.3 or (seen>=3000 and (lo<.9 or hi>1.1)):
     reason=f'v3 exceeded step {seen}: {q}';log(reason);proc.terminate();break
   if time.monotonic()-start>5200:
    reason='walltime 5200s';log(reason);proc.terminate();break
  code=proc.wait(timeout=60)
 (R/'solver.exit').write_text(f'{code} {reason}\n');log(f'EXIT {code} reason={reason} secs={int(time.monotonic()-start)}')
 if code==0 and reason is None and not T.startswith('C1smoke'):
  (R/'solver_a.exit').write_text('exit=0\n');(R/'case_a').symlink_to(case,target_is_directory=True)
  shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
  txt=Path('/content/extract_crop.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('{R}')")
  (R/'extract_crop.py').write_text(txt)
  with (R/'extract.log').open('w') as f:ret=subprocess.run(['python3',str(R/'extract_crop.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=900)
  log('EXTRACT '+str(ret.returncode));
  if ret.returncode:log((R/'extract.log').read_text()[-3000:])
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-4000:])
finally:(R/'all.done').write_text('done\n')
