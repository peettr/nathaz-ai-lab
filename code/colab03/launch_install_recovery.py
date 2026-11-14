import os,sys,subprocess,pathlib
p=pathlib.Path('/content/l264a100');p.mkdir(exist_ok=True)
fd=os.open(p/'install_py310_recovery.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('install_py310_l264.py\n')
with (p/'install_py310_recovery.log').open('x') as log:
 proc=subprocess.Popen([sys.executable,'/content/install_py310_l264.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('INSTALL_RECOVERY_PID',proc.pid,flush=True)
