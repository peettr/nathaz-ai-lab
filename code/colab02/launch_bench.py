import os,pathlib,subprocess
p=pathlib.Path('/content/l264a100');assert p.joinpath('full.done').exists()
fd=os.open(p/'bench.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('bench_driver.py\n')
with (p/'bench.log').open('w') as log:
 proc=subprocess.Popen([str(p/'venv/bin/python'),'/content/bench_driver_l264.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('BENCH_PID',proc.pid,flush=True)
