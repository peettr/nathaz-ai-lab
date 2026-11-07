import subprocess
from pathlib import Path
p=Path('/content/luw_nan_stage4_retry3_1016.start.log')
f=p.open('w')
proc=subprocess.Popen(['python3','/content/run_nan_remote.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('launched',proc.pid,flush=True)
