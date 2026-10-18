from pathlib import Path
import subprocess
r=Path('/content/luw-aij-r3'); assert not (r/'fine2.exit').exists()
code='''from pathlib import Path
import subprocess,time
r=Path('/content/luw-aij-r3');case=r/'case_fine2';bin=r/'repo/core/cfd_core/FluidX3D/bin/FluidX3D';t=time.time();(r/'fine2.start').write_text(str(t))
with (r/'fine2.log').open('w',buffering=1) as f:
 p=subprocess.Popen([str(bin),str(case/'conf.luwpf')],cwd=case,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 peak=0
 while p.poll() is None:
  z=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True)
  try:peak=max(peak,int(z.stdout.splitlines()[0].strip()))
  except (ValueError,IndexError):pass
  (r/'fine2.metrics').write_text(f'elapsed_s={time.time()-t:.1f} peak_gpu_memory_MiB={peak} pid={p.pid}\\n')
  time.sleep(15)
 (r/'fine2.exit').write_text(f'exit={p.returncode} wall_s={time.time()-t:.2f} peak_gpu_memory_MiB={peak}\\n')
'''
(r/'fine2_wrapper.py').write_text(code);f=(r/'fine2_wrapper.log').open('w');p=subprocess.Popen(['python3',str(r/'fine2_wrapper.py')],stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print('launched',p.pid)
