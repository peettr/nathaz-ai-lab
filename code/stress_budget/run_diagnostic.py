from pathlib import Path
import tarfile,subprocess,os,time,traceback,shutil,json
root=Path('/content/luw_stress');root.mkdir(exist_ok=True)
with tarfile.open('/content/stress_inputs.tar.gz') as t:t.extractall(root,filter='data')
r=root/'diagnostic';r.mkdir();src=r/'FluidX3D';case=r/'case';shutil.copytree(root/'FluidX3D',src);shutil.copytree(root/'case',case)
p=src/'src/defines.hpp';s=p.read_text();assert '#define FP16C // optional' in s;s=s.replace('#define FP16C // optional','//#define FP16C // optional').replace('//#define GROUND_WALL_MODEL // experimental','#define GROUND_WALL_MODEL // experimental');p.write_text(s)
try:
 t0=time.monotonic()
 with (r/'build.log').open('w') as f:cp=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=450)
 print('BUILD',cp.returncode,round(time.monotonic()-t0),flush=True)
 if cp.returncode:raise RuntimeError((r/'build.log').read_text()[-4000:])
 with (r/'solver.log').open('w',buffering=1) as f:cp=subprocess.run([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=3000)
 print('SOLVER',cp.returncode,round(time.monotonic()-t0),flush=True)
 if cp.returncode:raise RuntimeError((r/'solver.log').read_text()[-4000:])
 import sys;sys.path.insert(0,'/content');from extract_precision_full import extract
 extract(case,root/'diagnostic_profile.json')
 shutil.copy2(case/'RESULTS/stress_samples.csv',root/'stress_samples.csv')
 (root/'diagnostic.done').write_text('ok')
except Exception:
 (root/'diagnostic.error').write_text(traceback.format_exc());print(traceback.format_exc(),flush=True)
