from pathlib import Path
import tarfile,subprocess,time,traceback,os
R=Path('/content/luw_wale_floor_short3');R.mkdir(exist_ok=False)
def log(x):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(x)+'\n')
 print(x,flush=True)
try:
 with tarfile.open('/content/floor_short3_inputs.tar.gz') as t:t.extractall(R,filter='data')
 p=R/'FluidX3D/src/defines.hpp';s=p.read_text();assert '//#define CITY_STABILITY_MONITOR' in s;p.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=800)
 log('BUILD '+str(b.returncode));assert b.returncode==0,(R/'build.log').read_text(errors='replace')[-4000:]
 case=R/'case';st=time.monotonic();seen=0;reason=None
 with (R/'solver.log').open('w',buffering=1) as f:
  p=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  while p.poll() is None:
   time.sleep(5)
   t=case/'RESULTS/city_stability.csv';rows=t.read_text().splitlines() if t.exists() else []
   if len(rows)>1:
    row=dict(zip(rows[0].split(','),rows[-1].split(',')));step=int(row['step'])
    if step!=seen:
     seen=step
     if step%500==0:log('STEP '+str(step)+' rho '+row['min_rho']+' '+row['max_rho'])
     if float(row['max_u_lattice'])>.3 or (step>=3000 and (float(row['min_rho'])<.9 or float(row['max_rho'])>1.1)) or row['first_nonfinite_xyz_component']:
      reason='v3 '+str(row);log('STOP '+reason);p.terminate();break
   if time.monotonic()-st>1200:reason='timeout';p.terminate();break
  code=p.wait(timeout=60)
 (R/'solver.exit').write_text(str(code)+' '+str(reason));log('EXIT '+str(code)+' step '+str(seen)+' reason '+str(reason))
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-4000:])
finally:(R/'all.done').write_text('done\n')
