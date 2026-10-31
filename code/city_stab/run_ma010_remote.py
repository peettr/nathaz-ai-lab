"""Runs only on Colab; preserves evidence before runtime stop."""
from pathlib import Path
import subprocess, tarfile, time, traceback, sys
root=Path('/content/luw_city_ma010_1016')
root.mkdir(exist_ok=False)
deadline=float(Path('/content/ma010_deadline_epoch.txt').read_text())
def log(x):
 print(x,flush=True)
 with (root/'progress.log').open('a',buffering=1) as f:f.write(str(x)+'\n')
try:
 with tarfile.open('/content/city_ma010_inputs.tar.gz') as t:t.extractall(root,filter='data')
 with (root/'build.log').open('w') as f:
  p=subprocess.run(['make','Linux','-j4'],cwd=root/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=400)
 log('BUILD '+str(p.returncode))
 if p.returncode:raise RuntimeError((root/'build.log').read_text()[-4000:])
 case=root/'case'
 with (root/'solver.log').open('w',buffering=1) as f:
  p=subprocess.Popen([str(root/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  last=0
  while p.poll() is None:
   time.sleep(10)
   if time.time()-last>=55:
    last=time.time()
    import re
    txt=(root/'solver.log').read_bytes()[-6000:].decode(errors='replace')
    found=re.findall(r'(?:STEP|Step|step)[^\n\r]{0,100}',txt)
    log('RUN remaining_s='+str(round(deadline-time.time()))+' '+(found[-1] if found else 'initializing'))
   if time.time()>=deadline:
    log('BUDGET_STOP');p.terminate();break
  try:code=p.wait(timeout=35)
  except subprocess.TimeoutExpired:p.kill();code=p.wait()
 (root/'solver.exit').write_text(str(code)+'\n')
 log('SOLVER_EXIT '+str(code))
except Exception:
 (root/'error.txt').write_text(traceback.format_exc());log('ERROR '+traceback.format_exc()[-3000:])
finally:
 (root/'all.done').write_text('done\n')
