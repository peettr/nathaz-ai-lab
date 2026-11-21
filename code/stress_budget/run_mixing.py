from pathlib import Path
import tarfile,subprocess,time,traceback,shutil,json,sys
root=Path('/content/luw_mixing');root.mkdir(exist_ok=True)
with tarfile.open('/content/mixing_inputs.tar.gz') as t:t.extractall(root,filter='data')
src=root/'FluidX3D';case=root/'case';p=src/'src/defines.hpp';s=p.read_text();assert '#define FP16C // optional' in s;s=s.replace('#define FP16C // optional','//#define FP16C // optional').replace('//#define GROUND_WALL_MODEL // experimental','#define GROUND_WALL_MODEL // experimental');p.write_text(s)
try:
 t0=time.monotonic()
 with (root/'build.log').open('w') as f:cp=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=450)
 print('BUILD',cp.returncode,round(time.monotonic()-t0),flush=True)
 if cp.returncode:raise RuntimeError((root/'build.log').read_text()[-4000:])
 with (root/'solver.log').open('w',buffering=1) as f:cp=subprocess.run([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=3000)
 print('SOLVER',cp.returncode,round(time.monotonic()-t0),flush=True)
 if cp.returncode:raise RuntimeError((root/'solver.log').read_text()[-4000:])
 sys.path.insert(0,'/content');from extract_precision_full import extract
 extract(case,root/'mixing_profile.json');shutil.copy2(case/'RESULTS/stress_samples.csv',root/'mixing_stress_samples.csv')
 (root/'mixing.done').write_text('ok')
except Exception:
 (root/'mixing.error').write_text(traceback.format_exc());print(traceback.format_exc(),flush=True)
