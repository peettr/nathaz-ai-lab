"""Run FP32 first-layer-only city control on Colab, once."""
from pathlib import Path
import tarfile,subprocess,time,traceback,shutil,json
r=Path('/content/luw_wp1_city_control');r.mkdir(exist_ok=False)
try:
 with tarfile.open('/content/mix00_inputs.tar.gz') as t:t.extractall(r,filter='data')
 s=r/'FluidX3D';c=r/'case';p=s/'src/defines.hpp';v=p.read_text();assert '//#define FP16C // optional' in v and '//#define GROUND_WALL_MODEL // experimental' in v
 p.write_text(v.replace('//#define GROUND_WALL_MODEL // experimental','#define GROUND_WALL_MODEL // experimental'))
 with (r/'build.log').open('w') as f:q=subprocess.run(['make','Linux','-j4'],cwd=s,stdout=f,stderr=subprocess.STDOUT,timeout=500)
 print('BUILD',q.returncode,flush=True);assert q.returncode==0,(r/'build.log').read_text()[-2000:]
 start=time.monotonic()
 with (r/'solver.log').open('w',buffering=1) as f:q=subprocess.run([str(s/'bin/FluidX3D'),str(c/'conf.luwpf')],cwd=c,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=2400)
 print('SOLVE',q.returncode,'seconds',time.monotonic()-start,flush=True);(r/'solver_a.exit').write_text('exit='+str(q.returncode)+'\n');assert q.returncode==0
 (r/'case_a').symlink_to(c,target_is_directory=True);shutil.copy2('/content/points_w_r7.json',r/'points_w_r7.json')
 v=Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')","Path('/content/luw_wp1_city_control')")
 (r/'extract.py').write_text(v)
 with (r/'extract.log').open('w') as f:q=subprocess.run(['python3',str(r/'extract.py')],cwd=r,stdout=f,stderr=subprocess.STDOUT,timeout=400)
 print('EXTRACT',q.returncode,flush=True);assert q.returncode==0,(r/'extract.log').read_text()[-2000:]
 assert len(json.loads((r/'offset_samples_a_r10.json').read_text())['rows'])==80
 (r/'done').write_text('ok\n')
except Exception:
 (r/'error').write_text(traceback.format_exc());print(traceback.format_exc(),flush=True)
finally:
 (r/'terminal').write_text('done\n')
