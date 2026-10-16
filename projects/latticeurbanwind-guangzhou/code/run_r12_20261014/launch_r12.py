from pathlib import Path
import subprocess
r=Path('/content/luw-aij-r12');assert not (r/'solver.exit').exists();(r/'solver.lock').open('x').close()
code='''from pathlib import Path
import subprocess,time
r=Path('/content/luw-aij-r12');case=r/'case_a';binary=r/'repo/core/cfd_core/FluidX3D/bin/FluidX3D';t=time.time();(r/'solver.start').write_text(str(t))
with (r/'solver.log').open('w',buffering=1) as f:
 p=subprocess.Popen([str(binary),str(case/'conf.luwpf')],cwd=case,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 peak=0
 while p.poll() is None:
  z=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True)
  try:peak=max(peak,int(z.stdout.splitlines()[0].strip()))
  except (ValueError,IndexError):pass
  (r/'solver.metrics').write_text(f'elapsed_s={time.time()-t:.1f} peak_gpu_memory_MiB={peak} pid={p.pid}\\n')
  time.sleep(15)
 (r/'solver.exit').write_text(f'exit={p.returncode} wall_s={time.time()-t:.2f} peak_gpu_memory_MiB={peak}\\n')
'''
(r/'solver_wrapper.py').write_text(code);f=(r/'solver_wrapper.log').open('w');p=subprocess.Popen(['python3',str(r/'solver_wrapper.py')],stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print('launched',p.pid,flush=True)
