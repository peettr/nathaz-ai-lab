from pathlib import Path
import os,sys,time,tarfile,subprocess,traceback,shutil,csv
T=sys.argv[1] if len(sys.argv)>1 else 'FGz2r'
R=Path('/content/luw_sponge_'+T)
R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(T,s,flush=True)
try:
 with tarfile.open('/content/'+T+'_inputs.tar.gz') as t:t.extractall(R,filter='data')
 defs=R/'FluidX3D/src/defines.hpp';s=defs.read_text();assert s.count('//#define CITY_STABILITY_MONITOR')==1;defs.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:p=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 log('BUILD '+str(p.returncode));assert p.returncode==0,(R/'build.log').read_text()[-4000:]
 case=R/'case';trace=case/'RESULTS/city_stability.csv';start=time.monotonic();seen=-1;reason=None
 env=os.environ.copy();env['LUW_GROUND_MIX_A']='0.0';env['LUW_GROUND_Z0_SI']='0.002'
 with (R/'solver.log').open('w',buffering=1) as f:
  p=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
  while p.poll() is None:
   time.sleep(10)
   if trace.exists():
    with trace.open() as tf:
     rows=list(csv.DictReader(tf));q=rows[-1] if rows else None
    if q and int(q['step'])!=seen:
     seen=int(q['step']);lo=float(q['min_rho']);hi=float(q['max_rho']);u=float(q['max_u_lattice'])
     if seen%1000==0:log(f'STEP {seen} rho=[{lo},{hi}] umax={u}')
     if q['first_nonfinite_xyz_component'] or u>0.3 or (seen>=3000 and (lo<0.9 or hi>1.1)):
      reason=f'v3 exceeded at {seen} rho=[{lo},{hi}] umax={u} bad={q["first_nonfinite_xyz_component"]}';log(reason);p.terminate();break
   if time.monotonic()-start>1550:
    reason='solver walltime limit 1550s';log(reason);p.terminate();break
  code=p.wait(timeout=60)
 (R/'solver.exit').write_text(f'{code} {reason}\n');log(f'EXIT {code} reason={reason} secs={int(time.monotonic()-start)}')
 if (case/'RESULTS/full_height_planes.csv').exists():
  shutil.copy2(case/'RESULTS/full_height_planes.csv',R/'planes.csv')
 if trace.exists():shutil.copy2(trace,R/'trace.csv')
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-4000:])
finally:
 (R/'all.done').write_text('done\n')
