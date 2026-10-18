import subprocess,os
from pathlib import Path
r=Path('/content/cache_run');r.mkdir(exist_ok=True)
with open(r/'experiment.console','w',buffering=1) as log,open('/dev/null') as nil:
 p=subprocess.Popen(['python3','-u',str(r/'experiment.py')],stdin=nil,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 (r/'experiment.pid').write_text(str(p.pid))
 print('EXPERIMENT_PID',p.pid,flush=True)
