from pathlib import Path
import os,subprocess
p=Path('/content/try13_main_smoke_fix2.lock')
with p.open('x') as f:f.write('exclusive\n')
log=Path('/content/try13_main_smoke_fix2.log')
with log.open('x') as f:
 proc=subprocess.Popen(['python3','-u','/content/try13_main_smoke_fix2_worker_fix2.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('MAIN_SMOKE_PID',proc.pid)
