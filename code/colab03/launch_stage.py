"""Run as short Colab exec cell to start an exclusive detached stage worker."""
import os, subprocess,sys,pathlib
p=pathlib.Path('/content/l264a100');p.mkdir(exist_ok=True)
lock=p/'stage.started'
fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('stage.py\n')
log=open(p/'stage.log','w')
proc=subprocess.Popen([sys.executable,'/content/stage_l264.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('STAGE_PID',proc.pid,flush=True)
