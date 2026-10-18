"""Colab-only sequential Case E wall-model diagnostics."""
from pathlib import Path
import tarfile,subprocess,time,os,shutil,csv,json,traceback
R=Path('/content/luw_city_diag_not_1016'); R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(s,flush=True)
def check(path):
 if not path.exists():return None
 with path.open() as f:
  first=f.readline().strip().split(','); last=None
  for line in f:last=line.strip().split(',')
 if last is None:return None
 d=dict(zip(first,last));n=int(d['step']);v=float(d['max_u_lattice']);lo=float(d['min_rho']);hi=float(d['max_rho'])
 why=('nonfinite '+d['first_nonfinite_xyz_component'] if d['first_nonfinite_xyz_component'] else 'speed' if v>.3 else 'rho' if n>=3000 and (lo<.9 or hi>1.1) else None)
 return n,v,lo,hi,why
try:
 with tarfile.open('/content/city_diag_noT_inputs.tar.gz') as t:t.extractall(R,filter='data')
 src=R/'FluidX3D/src';p=src/'defines.hpp';s=p.read_text();assert s.count('//#define CITY_STABILITY_MONITOR')==1
 assert '#define GROUND_WALL_MODEL' in s and '#define TEMPERATURE' not in s.splitlines()
 p.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 log('BUILD '+str(b.returncode));assert b.returncode==0,(R/'build.log').read_text()[-3000:]
 for name,a in [('G0','0'),('G1','0.70'),('G2','1.0')]:
  run=R/name;run.mkdir();case=run/'case';shutil.copytree(R/'case',case,ignore=shutil.ignore_patterns('RESULTS'))
  trace=case/'RESULTS/city_stability.csv';t0=time.time();env=os.environ.copy();env['LUW_GROUND_MIX_A']=a
  with (run/'solver.log').open('w',buffering=1) as f:
   proc=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
   seen=-1;why=None
   while proc.poll() is None:
    time.sleep(8);q=check(trace)
    if q and q[0]!=seen:
     seen=q[0];(run/'latest.json').write_text(json.dumps(q))
     if seen%1000==0:log(name+' STEP '+str(q))
     if q[-1]:
      why=q[-1];log(name+' STABILITY_STOP '+str(q));proc.terminate();break
    if time.time()-t0>2700:
     why='solver timeout';proc.terminate();break
   code=proc.wait(timeout=90)
  (run/'solver.exit').write_text(str(code)+'\n'); log(name+' END exit='+str(code)+' step='+str(seen)+' reason='+str(why)+' sec='+str(int(time.time()-t0)))
  if code!=0 or why:continue
  (run/'solver_a.exit').write_text('exit=0\n');(run/'case_a').symlink_to(case,target_is_directory=True)
  shutil.copy2('/content/points_w_r7.json',run/'points_w_r7.json')
  script=Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('{run}')")
  (run/'extract_city.py').write_text(script)
  with (run/'extract.log').open('w') as f:e=subprocess.run(['python3',str(run/'extract_city.py')],cwd=run,stdout=f,stderr=subprocess.STDOUT,timeout=600)
  log(name+' EXTRACT '+str(e.returncode))
  if e.returncode:log((run/'extract.log').read_text()[-1500:])
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log('ERROR '+traceback.format_exc()[-3000:])
finally:(R/'all.done').write_text('done\n')
