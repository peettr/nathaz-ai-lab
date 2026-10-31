"""Executed only on Colab A100; two sequential independent Case E runs."""
from pathlib import Path
import subprocess,tarfile,time,traceback,json,sys,shutil
R=Path('/content/luw_wp1_city_v2');R.mkdir(exist_ok=False)
def note(s):
 print(s,flush=True)
 with (R/'progress.log').open('a') as f:f.write(s+'\n')
for tag in ('mix07','mix10'):
 try:
  root=R/tag;root.mkdir(exist_ok=False)
  with tarfile.open('/content/'+tag+'_inputs.tar.gz') as t:t.extractall(root,filter='data')
  src=root/'FluidX3D';case=root/'case'
  p=src/'src/defines.hpp';s=p.read_text();assert '//#define FP16C // optional' in s and '//#define GROUND_WALL_MODEL // experimental' in s
  s=s.replace('//#define GROUND_WALL_MODEL // experimental','#define GROUND_WALL_MODEL // experimental');p.write_text(s)
  with (root/'build.log').open('w') as f:cp=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=500)
  note(tag+' BUILD '+str(cp.returncode));assert cp.returncode==0,(root/'build.log').read_text()[-3000:]
  t=time.monotonic()
  with (root/'solver.log').open('w',buffering=1) as f:cp=subprocess.run([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=2400)
  note(tag+f' SOLVE {cp.returncode} seconds {time.monotonic()-t:.2f}')
  (root/'solver_a.exit').write_text(f'exit={cp.returncode}\n');assert cp.returncode==0
  (root/'case_a').symlink_to(case,target_is_directory=True)
  shutil.copy2('/content/points_w_r7.json',root/'points_w_r7.json')
  code=Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('/content/luw_wp1_city_v2/{tag}')")
  (root/'extract_city.py').write_text(code)
  with (root/'extract.log').open('w') as f:cp=subprocess.run(['python3',str(root/'extract_city.py')],cwd=root,stdout=f,stderr=subprocess.STDOUT,timeout=400)
  note(tag+' EXTRACT '+str(cp.returncode));assert cp.returncode==0,(root/'extract.log').read_text()[-3000:]
  data=json.loads((root/'offset_samples_a_r10.json').read_text());assert len(data['rows'])==80
  shutil.copy2(root/'offset_samples_a_r10.json',R/(tag+'_samples.json'))
  (R/(tag+'.done')).write_text('ok\n')
  note(tag+' COMPLETE')
 except Exception:
  e=traceback.format_exc();(R/(tag+'.error')).write_text(e);note(tag+' FAILED '+e[-2000:]);break
(R/'all.done').write_text('terminal\n')
