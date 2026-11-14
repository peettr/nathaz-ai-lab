import os,subprocess,pathlib,sys
p=pathlib.Path('/content/l264a100');fd=os.open(p/'static_probe_retry.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('eccodes and static probe\n')
code="uv pip install --python /content/l264a100/venv/bin/python eccodes==2.44.0 && /content/l264a100/venv/bin/python /content/static_probe_l264.py"
with (p/'static_probe_retry.log').open('x') as log:
 proc=subprocess.Popen(['/bin/bash','-lc',code],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('STATIC_RETRY_PID',proc.pid)
