from pathlib import Path
import tarfile,subprocess,time,traceback,shutil,os
R=Path('/content/luw_wale_FW');R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(s,flush=True)
try:
 with tarfile.open('/content/FW_inputs.tar.gz') as t:t.extractall(R,filter='data')
 defs=R/'FluidX3D/src/defines.hpp';s=defs.read_text();assert '//#define CITY_STABILITY_MONITOR' in s;defs.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=800)
 log('BUILD '+str(b.returncode));assert b.returncode==0,(R/'build.log').read_text(errors='replace')[-4000:]
 case=R/'case';trace=case/'RESULTS/city_stability.csv';st=time.monotonic();seen=-1;reason=None
 with (R/'solver.log').open('w',buffering=1) as f:
  p=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  while p.poll() is None:
   time.sleep(8)
   if trace.exists():
    with trace.open() as q:
     h=q.readline().strip().split(',');v=''
     for v in q:pass
    if v:
     row=dict(zip(h,v.strip().split(',')));step=int(row['step'])
     if step!=seen:
      seen=step
      if step%1000==0:log('STEP '+str(step)+' rho '+row['min_rho']+' '+row['max_rho'])
      if row['first_nonfinite_xyz_component'] or float(row['max_u_lattice'])>.3 or (step>=3000 and (float(row['min_rho'])<.9 or float(row['max_rho'])>1.1)):
       reason='v3 '+str(row);log('STOP '+reason);p.terminate();break
   if time.monotonic()-st>2100:reason='timeout';p.terminate();break
  code=p.wait(timeout=60)
 (R/'solver.exit').write_text(str(code)+' '+str(reason));log('EXIT '+str(code)+' step '+str(seen)+' reason '+str(reason))
 if code==0 and reason is None:
  (R/'solver_a.exit').write_text('exit=0\n');(R/'case_a').symlink_to(case,target_is_directory=True)
  shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
  script=Path('/content/extract_full.py').read_text().replace('/content/luw_split_E1',str(R));(R/'extract.py').write_text(script)
  with (R/'extract.log').open('w') as f:x=subprocess.run(['python3',str(R/'extract.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=800)
  log('EXTRACT '+str(x.returncode));
  if x.returncode:log((R/'extract.log').read_text(errors='replace')[-2000:])
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-4000:])
finally:(R/'all.done').write_text('done\n')
