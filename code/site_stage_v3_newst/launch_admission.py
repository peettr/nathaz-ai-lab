"""One-shot Colab detached admission launcher; never rerun if marker exists."""
import os, subprocess
from pathlib import Path
p=Path('/content/v3/admission.launch')
with p.open('x') as f: f.write('launch claimed\n')
log=open('/content/v3/admission.log','x',buffering=1)
code="import subprocess; from pathlib import Path; p=subprocess.run(['python3','-u','/content/v3/run_v3.py','admission'],stdout=__import__('sys').stdout,stderr=__import__('sys').stderr); Path('/content/v3/admission.exit').write_text(str(p.returncode)); raise SystemExit(p.returncode)"
x=subprocess.Popen(['python3','-u','-c',code],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
Path('/content/v3/admission.pid').write_text(str(x.pid))
print('PID',x.pid)
