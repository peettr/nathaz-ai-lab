"""Colab-only split experiment; do not execute on 工作站."""
from pathlib import Path
import sys,tarfile,subprocess,time,traceback,shutil,os
TAG=sys.argv[1];assert TAG in ('E1','E05','C1G0')
R=Path('/content/luw_split_'+TAG);R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(s,flush=True)
def last_row(p):
 if not p.exists():return None
 with p.open() as f:
  h=f.readline().strip().split(',');q=''
  for x in f:q=x
 return dict(zip(h,q.strip().split(','))) if q else None
try:
 with tarfile.open('/content/'+TAG+'_inputs.tar.gz') as t:t.extractall(R,filter='data')
 defs=R/'FluidX3D/src/defines.hpp';s=defs.read_text();assert '//#define CITY_STABILITY_MONITOR' in s
 assert '#define TEMPERATURE' not in [x.strip() for x in s.splitlines()]
 defs.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:ret=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 log('BUILD '+str(ret.returncode));assert ret.returncode==0,(R/'build.log').read_text()[-3000:]
 case=R/'case';trace=case/'RESULTS/city_stability.csv';start=time.monotonic();reason=None;seen=-1
 env=os.environ.copy()
 if TAG=='C1G0':env['LUW_GROUND_MIX_A']='0'
 with (R/'solver.log').open('w',buffering=1) as f:
  proc=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
  while proc.poll() is None:
   time.sleep(8);q=last_row(trace)
   if q and int(q['step'])!=seen:
    seen=int(q['step']);lo=float(q['min_rho']);hi=float(q['max_rho']);u=float(q['max_u_lattice'])
    if seen%1000==0:log(f'STEP {seen} rho=[{lo},{hi}] umax={u}')
    if q['first_nonfinite_xyz_component'] or u>.3 or (seen>=3000 and (lo<.9 or hi>1.1)):
     reason=f'v3 exceeded step {seen}: {q}';log(reason);proc.terminate();break
    if seen>= (7000 if TAG=='E05' else 3500) and not (R/'precheck.txt').exists():
     (R/'precheck.txt').write_text(f'PASS {seen} rho=[{lo},{hi}]\n');log('PRECHECK_PASS '+str(seen))
   if time.monotonic()-start>4400:
    reason='walltime 4400s';log(reason);proc.terminate();break
  code=proc.wait(timeout=60)
 (R/'solver.exit').write_text(f'{code} {reason}\n');log(f'EXIT {code} reason={reason} secs={int(time.monotonic()-start)}')
 if code==0 and reason is None:
  (R/'solver_a.exit').write_text('exit=0\n');(R/'case_a').symlink_to(case,target_is_directory=True)
  shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
  shutil.copy2('/content/extract_'+TAG+'.py',R/'extract.py')
  with (R/'extract.log').open('w') as f:ret=subprocess.run(['python3',str(R/'extract.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=1200)
  log('EXTRACT '+str(ret.returncode))
  if ret.returncode:log((R/'extract.log').read_text()[-3000:])
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-4000:])
finally:(R/'all.done').write_text('done\n')
