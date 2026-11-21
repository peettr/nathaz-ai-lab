from pathlib import Path
import os,tarfile,hashlib,subprocess
root=Path(os.environ.get('T4_PRECHECK_ROOT','/content')).resolve()
precheck='T4_PRECHECK_ROOT' in os.environ
p=Path(os.environ.get('T4_BUNDLE_PATH',str(root/'t4_stage.tar.gz')))
h=hashlib.sha256(p.read_bytes()).hexdigest()
assert h==os.environ['T4_BUNDLE_SHA']
assert not (root/'stage_t4').exists() and not (root/'t4_out').exists()
with tarfile.open(p) as t:
 for m in t.getmembers():
  assert (m.name=='stage_t4' or m.name.startswith('stage_t4/')) and '..' not in Path(m.name).parts
  assert m.isdir() or m.isfile(),(m.name,m.type)
 t.extractall(root,filter='data')
assert (root/'stage_t4/manifest.json').is_file()
assert (root/'stage_t4/FluidX3D_on/src/kernel.cpp').is_file()
assert (root/'stage_t4/FluidX3D_off/src/kernel.cpp').is_file()
assert (root/'stage_t4/smoke/conf.luwpf').is_file()
if precheck:
 print('T4_LOCAL_EXTRACT_PASS',h,len(list((root/'stage_t4').rglob('*'))))
 raise SystemExit(0)
log=Path('/content/t4.log')
with log.open('x') as f:
 proc=subprocess.Popen(['python3','-u','/content/t4_worker.py'],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,env={**os.environ,'T4_DEADLINE':os.environ['T4_DEADLINE'],'PYTHONPATH':'/content'})
Path('/content/t4.pid').write_text(str(proc.pid)+'\n')
print('T4_LAUNCHED_PID',proc.pid)
