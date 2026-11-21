import os, pathlib, subprocess
root=pathlib.Path('/content/try8_fix2_diag')
assert not root.exists(), 'exclusive remote diagnostic root already exists'
log=open('/content/try8_fix2_controller.log','x')
p=subprocess.Popen(['python3','/content/try8_fix2_worker.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=os.environ.copy())
print('STARTED',p.pid,flush=True)
