import os,pathlib,subprocess
p=pathlib.Path('/content/l264a100');assert p.joinpath('pilot.done').exists()
fd=os.open(p/'full.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('full.py 10x00Z\n')
with (p/'full.log').open('w') as log:
 proc=subprocess.Popen([str(p/'venv/bin/python'),'/content/full_l264.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('FULL_PID',proc.pid,flush=True)
