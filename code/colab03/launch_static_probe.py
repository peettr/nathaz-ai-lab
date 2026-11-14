import os,subprocess,pathlib
p=pathlib.Path('/content/l264a100');fd=os.open(p/'static_probe.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('static_probe_l264.py\n')
with (p/'static_probe.log').open('x') as log:
 proc=subprocess.Popen(['/content/l264a100/venv/bin/python','/content/static_probe_l264.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('STATIC_PROBE_PID',proc.pid)
