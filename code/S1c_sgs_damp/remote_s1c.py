from pathlib import Path
import os,tarfile,subprocess,time,traceback,shutil,csv,json,hashlib
R=Path('/content/s1b_case'); R.mkdir(exist_ok=False)
def log(x):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(x)+'\n')
 print(x,flush=True)
def status(p):
 if not p.exists():return None
 with p.open() as f:
  h=f.readline().strip().split(',');last=''
  for q in f:last=q
 return dict(zip(h,last.strip().split(','))) if last else None
try:
 with tarfile.open('/content/S1b_inputs.tar.gz') as tar:tar.extractall(R,filter='data')
 defs=R/'FluidX3D/src/defines.hpp';s=defs.read_text();assert s.count('//#define CITY_STABILITY_MONITOR')==1
 defs.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:ret=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 log('BUILD '+str(ret.returncode));assert ret.returncode==0,(R/'build.log').read_text()[-4000:]
 case=R/'case';trace=case/'RESULTS/city_stability.csv';start=time.monotonic();reason=None
 with (R/'case_solver.log').open('w',buffering=1) as f:
  proc=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  seen=-1
  while proc.poll() is None:
   time.sleep(5);q=status(trace)
   if q and int(q['step'])!=seen:
    seen=int(q['step']);lo=float(q['min_rho']);hi=float(q['max_rho']);u=float(q['max_u_lattice'])
    if seen%1000==0:log(f'STEP {seen} rho=[{lo},{hi}] umax={u}')
    if q['first_nonfinite_xyz_component'] or u>.3 or (seen>=3000 and (lo<.9 or hi>1.1)):
     reason=f'v3 exceeded step {seen}: {q}';log(reason);proc.terminate();break
   if time.monotonic()-start>2250:
    reason='walltime limit';log(reason);proc.terminate();break
  code=proc.wait(timeout=60)
 (R/'solver.exit').write_text(f'{code} {reason}\n');log(f'EXIT {code} reason={reason} secs={int(time.monotonic()-start)}');assert code==0 and reason is None
 (R/'solver_a.exit').write_text('exit=0\n');(R/'case_a').symlink_to(case,target_is_directory=True)
 shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
 text=Path('/content/extract_ti.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('{R}')")
 (R/'extract_ti.py').write_text(text)
 with (R/'extract.log').open('w') as f:ret=subprocess.run(['python3',str(R/'extract_ti.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=600)
 log('EXTRACT '+str(ret.returncode));assert ret.returncode==0,(R/'extract.log').read_text()[-4000:]
 p=R/'offset_samples_a_r10.json';assert p.stat().st_size>1000
 a=json.loads(p.read_text());assert len(a['rows'])==80
 (R/'result.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  offset_samples_a_r10.json\n')
 log('RESULT VERIFIED '+str(p.stat().st_size)+' '+(R/'result.sha256').read_text().strip())
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-4000:])
finally:(R/'all.done').write_text('done\n')
