from pathlib import Path
import os,tarfile,subprocess,time,traceback,shutil
R=Path('/content/luw_E1_split_1017'); R.mkdir(exist_ok=False)
def log(x):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(x)+'\n')
 print(x,flush=True)
def last(p):
 if not p.exists():return None
 with p.open() as f:
  header=f.readline().strip().split(',');line=''
  for q in f:line=q
 return dict(zip(header,line.strip().split(','))) if line else None
try:
 with tarfile.open('/content/E1_inputs.tar.gz') as t:t.extractall(R,filter='data')
 defs=R/'FluidX3D/src/defines.hpp';s=defs.read_text();assert s.count('//#define CITY_STABILITY_MONITOR')==1
 assert '#define GROUND_WALL_MODEL' in s
 assert not any(x.strip()=='#define TEMPERATURE' for x in s.splitlines())
 defs.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:ret=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 log('BUILD '+str(ret.returncode));assert ret.returncode==0,(R/'build.log').read_text()[-4000:]
 case=R/'case';trace=case/'RESULTS/city_stability.csv';start=time.monotonic();reason=None;seen=-1
 env=os.environ.copy();env['LUW_GROUND_MIX_A']='0.0';env['LUW_GROUND_Z0_SI']='0.002'
 with (R/'solver.log').open('w',buffering=1) as f:
  p=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
  while p.poll() is None:
   time.sleep(10);q=last(trace)
   if q and int(q['step'])!=seen:
    seen=int(q['step']);lo=float(q['min_rho']);hi=float(q['max_rho']);u=float(q['max_u_lattice'])
    if seen%1000==0:log(f'STEP {seen} rho=[{lo},{hi}] maxu={u}')
    if q['first_nonfinite_xyz_component'] or u>.3 or (seen>=3000 and (lo<.9 or hi>1.1)):
     reason=f'v3 exceeded step {seen}: {q}';log(reason);p.terminate();break
   if time.monotonic()-start>2350:
    reason='solver time limit 2350s';log(reason);p.terminate();break
  code=p.wait(timeout=60)
 (R/'solver.exit').write_text(f'{code} {reason}\n');log(f'EXIT {code} reason={reason} secs={int(time.monotonic()-start)}')
 if code==0 and reason is None:
  (R/'solver_a.exit').write_text('exit=0\n');(R/'case_a').symlink_to(case,target_is_directory=True)
  shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
  text=Path('/content/extract_ti.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('{R}')")
  (R/'extract_ti.py').write_text(text)
  with (R/'extract.log').open('w') as f:ret=subprocess.run(['python3',str(R/'extract_ti.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=700)
  log('EXTRACT '+str(ret.returncode));
  if ret.returncode:log((R/'extract.log').read_text()[-3000:])
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-4000:])
finally:
 if (R/'case/RESULTS/city_stability.csv').exists():shutil.copy2(R/'case/RESULTS/city_stability.csv',R/'trace.csv')
 (R/'all.done').write_text('done\n')
