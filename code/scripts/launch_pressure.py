"""Launch pressure auxiliary after wind reference completes; no duplicate starts."""
from pathlib import Path
import subprocess,sys,time
r=Path('/content/ace_formal/reference')
assert (r/'batch.exit.json').exists() and __import__('json').loads((r/'batch.exit.json').read_text())['returncode']==0
assert len(list(r.glob('cold_*.npz')))==30
assert not (r/'pressure.lock').exists() and not (r/'pressure.exit.json').exists()
(r/'pressure.lock').open('x').write(str(time.time()))
f=(r/'pressure.log').open('x')
code='import subprocess,sys,json,time; t=time.monotonic(); p=subprocess.run([sys.executable,"-u","/content/ace_formal/extract_pressure_new.py"],stdout=sys.stdout,stderr=subprocess.STDOUT); open("/content/ace_formal/reference/pressure.exit.json","x").write(json.dumps({"returncode":p.returncode,"wall_s":time.monotonic()-t}));sys.exit(p.returncode)'
p=subprocess.Popen([sys.executable,'-u','-c',code],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
(r/'pressure.pid').open('x').write(str(p.pid));print('PRESSURE_STARTED',p.pid)
