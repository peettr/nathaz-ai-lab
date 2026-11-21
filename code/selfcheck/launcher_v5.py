import subprocess,sys,pathlib
p=pathlib.Path('/content/l26_19_selfcheck_v5');p.mkdir(exist_ok=True)
with (p/'launch.lock').open('x') as f:f.write('launched')
log=(p/'worker_v5.log').open('x')
child=subprocess.Popen([sys.executable,'/content/worker_v5.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('LAUNCHED_PID',child.pid,flush=True)
