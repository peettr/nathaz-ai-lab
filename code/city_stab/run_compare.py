"""Runs exclusively on Colab A100. Preserve every stage's log on VM."""
from pathlib import Path
import tarfile, subprocess, time, os, json, hashlib, traceback
R=Path('/content/luw_citystab_v1');R.mkdir(exist_ok=False)
Path('/content/.colab_owner').write_text('city_stab researchos-uwind-luw')
def log(s):
 print(s,flush=True)
 with (R/'progress.log').open('a') as f:f.write(s+'\n')
def call(command,cwd,logpath,timeout=900,env=None):
 with logpath.open('w') as f:
  p=subprocess.Popen(command,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  start=time.time()
  while p.poll() is None:
   time.sleep(20);log(f'{logpath.name}: elapsed {time.time()-start:.0f}s')
   if time.time()-start>timeout:p.kill();break
  return p.wait()
try:
 for tag,archive in [('head','city_head_inputs'),('off','city_clean_inputs')]:
  root=R/tag;root.mkdir()
  with tarfile.open('/content/'+archive+'.tar.gz') as t:t.extractall(root,filter='data')
  src=root/'FluidX3D';case=root/'case'
  if tag=='head':
   s=(src/'src/defines.hpp').read_text();assert '#define FP16C // optional' in s;(src/'src/defines.hpp').write_text(s.replace('#define FP16C // optional','//#define FP16C // optional'))
  conf=(case/'conf.luwpf').read_text().replace('run_nstep = 31000','run_nstep = 200').replace('purge_avg = 20000','purge_avg = 0')
  (case/'conf.luwpf').write_text(conf)
  code=call(['make','Linux','-j4'],src,root/'build.log',timeout=600);log(tag+' build '+str(code));assert code==0
  env=os.environ.copy();env['LUW_GROUND_MIX_A']='0.0'
  code=call([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],case,root/'solver.log',timeout=1000,env=env)
  (root/'exit.txt').write_text(str(code));log(tag+' solver '+str(code));assert code==0
  files={str(p.relative_to(case)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (case/'RESULTS').rglob('*') if p.is_file() and p.stat().st_size<500_000_000}
  (root/'hashes.json').write_text(json.dumps(files,indent=2))
 a=json.loads((R/'head/hashes.json').read_text());b=json.loads((R/'off/hashes.json').read_text())
 common=sorted(set(a)&set(b));diff=[k for k in common if a[k]!=b[k]]
 (R/'compare.json').write_text(json.dumps({'head':a,'off':b,'common':common,'mismatch':diff},indent=2))
 log('COMMON '+repr(common)+' MISMATCH '+repr(diff))
except Exception:
 (R/'failure.txt').write_text(traceback.format_exc());log('ERROR '+traceback.format_exc()[-2000:])
finally:
 (R/'terminal.done').write_text('done')
