"""Compile and execute only on Colab. Persistent logs are pulled on exit."""
from pathlib import Path
import tarfile,subprocess,time,traceback
R=Path('/content/luw_nan_stage4_retry3_1016'); R.mkdir(exist_ok=False)
def log(s):
 print(s,flush=True)
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
try:
 with tarfile.open('/content/city_nan_stage4_inputs_v6.tar.gz') as t:t.extractall(R,filter='data')
 with (R/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=600)
 log('BUILD '+str(b.returncode));
 if b.returncode:raise RuntimeError((R/'build.log').read_text()[-4000:])
 case=R/'case'
 with (R/'solver.log').open('w',buffering=1) as f:
  t0=time.monotonic();p=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  while p.poll() is None:
   time.sleep(12)
   elapsed=time.monotonic()-t0
   if int(elapsed)%120<12:log('RUN elapsed='+str(int(elapsed))+' trace='+str((case/'RESULTS/nan_event.txt').exists()))
   if elapsed>1840:log('BUDGET_STOP elapsed='+str(elapsed));p.terminate();break
  code=p.wait(timeout=40)
 (R/'solver.exit').write_text(str(code)+'\n')
 log('SOLVER_EXIT '+str(code)+' elapsed='+str(time.monotonic()-t0))
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log('ERROR '+traceback.format_exc()[-3000:])
finally:(R/'all.done').write_text('done\n')
