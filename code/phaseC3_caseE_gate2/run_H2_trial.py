from pathlib import Path
import subprocess,shutil,os,time,json,traceback
R=Path('/content/luw_c3_gate2_v2_1016');run=R/'H2_trial';run.mkdir(exist_ok=False)
def log(x):
 with (run/'progress.log').open('a',buffering=1) as f:f.write(x+'\n')
 print(x,flush=True)
try:
 src=R/'FluidX3D';d=src/'src/defines.hpp';assert '#define GROUND_WALL_MODEL' in d.read_text()
 with (run/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-B','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=900)
 log('BUILD '+str(b.returncode));assert b.returncode==0
 case=run/'case';shutil.copytree(R/'case',case)
 env=os.environ.copy();env['LUW_IBB_CSR']=str(R/'active_building_links.csr');env['LUW_GROUND_MIX_A']='0.70'
 trace=case/'RESULTS/city_stability.csv';t0=time.monotonic()
 with (run/'solver.log').open('w',buffering=1) as f:
  p=subprocess.Popen([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
  seen=-1;why=None
  while p.poll() is None:
   time.sleep(6)
   if trace.exists():
    with trace.open() as g:
     fields=g.readline().strip().split(',');last=None
     for ln in g:last=ln.strip().split(',')
    if last:
     a=dict(zip(fields,last));step=int(a['step']);u=float(a['max_u_lattice']);lo=float(a['min_rho']);hi=float(a['max_rho'])
     if step!=seen:
      seen=step
      if step%500==0:log('STEP '+str((step,u,lo,hi)))
      if a['first_nonfinite_xyz_component'] or u>.3 or (step>=3000 and (lo<.9 or hi>1.1)):
       why='stability '+str((step,u,lo,hi,a['first_nonfinite_xyz_component']));log(why);p.terminate();break
   if time.monotonic()-t0>2800:why='timeout';p.terminate();break
  code=p.wait(timeout=90)
 (run/'solver.exit').write_text(str(code));log('END '+str((code,seen,why)))
 if code==0 and not why:
  (run/'solver_a.exit').write_text('exit=0\n');(run/'case_a').symlink_to(case,target_is_directory=True)
  shutil.copy2('/content/points_w_r7.json',run/'points_w_r7.json')
  script=Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('{run}')")
  (run/'extract_city.py').write_text(script)
  with (run/'extract.log').open('w') as f:e=subprocess.run(['python3',str(run/'extract_city.py')],cwd=run,stdout=f,stderr=subprocess.STDOUT,timeout=600)
  log('EXTRACT '+str(e.returncode))
except Exception:
 (run/'error.txt').write_text(traceback.format_exc());log('ERROR '+traceback.format_exc()[-3000:])
finally:(run/'done').write_text('done')
