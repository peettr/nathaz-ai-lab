"""Detach bounded solve with periodic exit, wall and VRAM checkpoint files."""
from pathlib import Path
import subprocess
r=Path('/content/luw-aij-r10');assert not (r/'solver_c.exit').exists();assert not (r/'solver_c.lock').exists();(r/'solver_c.lock').open('x').close()
code='''from pathlib import Path
import subprocess,time
r=Path('/content/luw-aij-r10');case=r/'case_c';binary=r/'repo/core/cfd_core/FluidX3D/bin/FluidX3D';t=time.time();(r/'solver_c.start').write_text(str(t))
with (r/'solver_c.log').open('w',buffering=1) as f:
 p=subprocess.Popen([str(binary),str(case/'conf.luwpf')],cwd=case,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 peak=0
 while p.poll() is None:
  z=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True)
  try:peak=max(peak,int(z.stdout.splitlines()[0].strip()))
  except (ValueError,IndexError):pass
  (r/'solver_c.metrics').write_text(f'elapsed_s={time.time()-t:.1f} peak_gpu_memory_MiB={peak} pid={p.pid}\\n')
  time.sleep(15)
 (r/'solver_c.exit').write_text(f'exit={p.returncode} wall_s={time.time()-t:.2f} peak_gpu_memory_MiB={peak}\\n')
'''
(r/'solver_wrapper_c.py').write_text(code);f=(r/'solver_wrapper_c.log').open('w');p=subprocess.Popen(['python3',str(r/'solver_wrapper_c.py')],stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print('launched',p.pid,flush=True)
