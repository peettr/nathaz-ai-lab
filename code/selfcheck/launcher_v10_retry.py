import subprocess,sys,pathlib
p=pathlib.Path('/content/l26_19_selfcheck_v10_retry');p.mkdir(exist_ok=True)
with (p/'launch.lock').open('x') as f:f.write('launched')
log=(p/'worker_v10_retry.log').open('x')
child=subprocess.Popen([sys.executable,'/content/worker_v10_retry.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('LAUNCHED_PID',child.pid,flush=True)
