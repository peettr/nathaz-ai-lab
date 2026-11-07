"""Launch HF staging detached from the Colab exec request."""
from pathlib import Path
import subprocess, sys, time
root=Path('/content/ace_formal'); root.mkdir(exist_ok=True)
lock=root/'staging_2010.lock'
if lock.exists() or (root/'staging_2010.done').exists():
    raise RuntimeError('staging already launched/completed; inspect before retry')
lock.open('x').write(str(time.time()))
log=(root/'staging_2010.log').open('x')
p=subprocess.Popen([sys.executable,'-u',str(root/'stage_2010.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(root/'staging_2010.pid').open('x').write(str(p.pid))
print('STAGING_STARTED',p.pid,flush=True)
