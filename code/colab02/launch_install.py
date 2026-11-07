import os,sys,subprocess,pathlib
p=pathlib.Path('/content/l264a100'); p.mkdir(exist_ok=True)
fd=os.open(p/'install.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('install_l264.py\n')
with open(p/'install.log','w') as log:
    proc=subprocess.Popen([sys.executable,'/content/install_l264.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('INSTALL_PID',proc.pid,flush=True)
