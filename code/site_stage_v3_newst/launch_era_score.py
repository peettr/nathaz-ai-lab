"""One-shot Colab launcher for preregistered A371 stages 4 then 5."""
import subprocess
from pathlib import Path
p=Path('/content/v3')
(p/'era_score.launch').open('x').write('claimed\n')
log=(p/'era_score.log').open('x',buffering=1)
code="""import subprocess,sys
from pathlib import Path
p=Path('/content/v3')
for stage in ('era','score'):
 r=subprocess.run(['python3','-u',str(p/'run_v3.py'),stage],stdout=sys.stdout,stderr=sys.stderr)
 (p/(stage+'.exit')).write_text(str(r.returncode))
 if r.returncode:raise SystemExit(r.returncode)
"""
child=subprocess.Popen(['python3','-u','-c',code],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(p/'era_score.pid').write_text(str(child.pid))
print('LAUNCHED',child.pid)
