import os, pathlib, subprocess, sys
p=pathlib.Path('/content/l264surface09');p.mkdir(exist_ok=True)
fd=os.open(p/'worker.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('l264surface09\n')
with (p/'worker.log').open('x') as log:
    proc=subprocess.Popen([sys.executable,'/content/l264worker09.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('WORKER_PID',proc.pid,flush=True)
