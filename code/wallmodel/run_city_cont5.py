"""Colab: R10a wall-only diagnostic; no city run uses SGS damping."""
from pathlib import Path
import tarfile,subprocess,time,traceback,json,shutil
r=Path('/content/luw_wall_cont5city');r.mkdir(exist_ok=False)
def log(s):
 print(s,flush=True)
 with (r/'progress.log').open('a') as f:f.write(s+'\n')
try:
 with tarfile.open('/content/caseE_cont5_inputs.tar.gz') as t:t.extractall(r,filter='data')
 src=r/'FluidX3D';case=r/'case';p=src/'src/defines.hpp';s=p.read_text();assert '//#define GROUND_WALL_MODEL' in s;s=s.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL');assert '//#define GROUND_WALL_SGS_DAMP' in s;p.write_text(s)
 t=time.monotonic()
 with (r/'build_city.log').open('w') as f:cp=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=300)
 log(f'BUILD rc={cp.returncode} sec={time.monotonic()-t:.2f}');assert cp.returncode==0
 t=time.monotonic()
 with (r/'solver_city.log').open('w',buffering=1) as f:cp=subprocess.run([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
 log(f'SOLVE rc={cp.returncode} sec={time.monotonic()-t:.2f}');(r/'solver_a.exit').write_text(f'exit={cp.returncode}\n');assert cp.returncode==0
 # Reuse audited r10 extractor with only paths changed; leave full VTK in Colab.
 (r/'case_a').symlink_to(case,target_is_directory=True)
 shutil.copy2('/content/points_w_r7.json',r/'points_w_r7.json')
 code=Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')","Path('/content/luw_wall_cont5city')").replace("r/'case_a/", "r/'case_a/")
 (r/'extract_city.py').write_text(code)
 with (r/'extract_city.log').open('w') as f:cp=subprocess.run(['python3',str(r/'extract_city.py')],cwd=r,stdout=f,stderr=subprocess.STDOUT,timeout=300)
 log(f'EXTRACT rc={cp.returncode}');assert cp.returncode==0
 log('POINTS '+str(len(json.loads((r/'offset_samples_a_r10.json').read_text())['rows'])))
 (r/'done.txt').write_text('COMPLETE\n')
except Exception:
 log('FAIL '+traceback.format_exc());(r/'done.txt').write_text('FAIL\n')
