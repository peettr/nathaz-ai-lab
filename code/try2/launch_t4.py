from pathlib import Path
import os,tarfile,hashlib,subprocess
p=Path('/content/t4_stage.tar.gz');h=hashlib.sha256(p.read_bytes()).hexdigest()
assert h==os.environ['T4_BUNDLE_SHA']
assert not Path('/content/stage_t4').exists() and not Path('/content/t4_out').exists()
with tarfile.open(p) as t:
 for m in t.getmembers():
  assert m.name.startswith('stage_t4/') and '..' not in Path(m.name).parts
 t.extractall('/content',filter='data')
log=Path('/content/t4.log')
with log.open('x') as f:
 proc=subprocess.Popen(['python3','-u','/content/t4_worker.py'],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,env={**os.environ,'T4_DEADLINE':os.environ['T4_DEADLINE'],'PYTHONPATH':'/content'})
Path('/content/t4.pid').write_text(str(proc.pid)+'\n')
print('T4_LAUNCHED_PID',proc.pid)
