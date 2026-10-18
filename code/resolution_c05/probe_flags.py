"""Colab-only init-stage probe; stop before advancing C05 timesteps."""
from pathlib import Path
import tarfile,subprocess,time,traceback
R=Path('/content/luw_resolution_c05_flags_v1');R.mkdir(exist_ok=False)
try:
 with tarfile.open('/content/C05_inputs.tar.gz') as t:t.extractall(R,filter='data')
 d=R/'FluidX3D/src/defines.hpp';s=d.read_text();assert '//#define CITY_STABILITY_MONITOR' in s;d.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:r=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 assert r.returncode==0,(R/'build.log').read_text()[-2000:]
 with (R/'solver.log').open('w',buffering=1) as f:
  p=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(R/'case/conf.luwpf')],cwd=R/'case',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  target=R/'case/RESULTS/native_flags_z0_90.bin';start=time.monotonic()
  while p.poll() is None and time.monotonic()-start<180:
   if target.exists() and target.stat().st_size==600*500*91:
    print('FLAGS_READY',target.stat().st_size,flush=True);p.terminate();break
   time.sleep(1)
  print('EXIT',p.wait(timeout=30),flush=True)
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());print(traceback.format_exc(),flush=True)
finally:(R/'all.done').write_text('done\n')
