from pathlib import Path
import hashlib,time
r=Path('/content/luw-c38-cased-r2-20261115')
print('STATUS',time.time(),'done',(r/'run.done').exists(),'failed',(r/'run.failed').exists(),'result',(r/'result.zip').stat().st_size if (r/'result.zip').exists() else None,flush=True)
if (r/'run.log').exists(): print('LOGTAIL',r.joinpath('run.log').read_text()[-1600:],flush=True)
if (r/'run.failed').exists():print('ERROR',r.joinpath('run.failed').read_text()[-1800:],flush=True)
if (r/'run.done').exists():
 h=hashlib.sha256()
 with (r/'result.zip').open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 print('RESULT_SHA256',h.hexdigest(),flush=True)
